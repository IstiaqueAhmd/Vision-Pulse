"""
Stripe service — handles checkout sessions, webhook events, and subscription management.
"""
import json
import logging
import stripe
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.payments import Payment
from app.models.credit import CreditPackage, UserCreditSubscription, CreditTransaction
from app.models.user import User

# Initialise Stripe with the secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Checkout Session
# ---------------------------------------------------------------------------

def create_checkout_session(plan: SubscriptionPlan, user: User) -> str:
    """
    Create a Stripe Checkout Session for the given subscription plan and user.
    Returns the hosted checkout URL to redirect the user to.
    """
    if not plan.stripe_price_id:
        raise ValueError(
            f"Plan '{plan.name}' does not have a Stripe Price ID configured. "
            "An admin must set stripe_price_id on this plan before it can be purchased."
        )

    # Build client_reference_id so we can link the Stripe session back to our DB
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[
            {
                "price": plan.stripe_price_id,
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.id),
        customer_email=user.email,
        metadata={
            "plan_id": str(plan.id),
            "user_id": str(user.id),
        },
        success_url=settings.STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=settings.STRIPE_CANCEL_URL,
    )
    return session.url


# ---------------------------------------------------------------------------
# Credit Package Checkout Session
# ---------------------------------------------------------------------------

def create_credit_checkout_session(package: CreditPackage, user: User) -> str:
    """
    Create a Stripe Checkout Session for a credit package.

    - plan_type == "one_time"          → mode="payment"       (credits added once)
    - plan_type == "monthly" / "yearly" → mode="subscription"  (credits added each cycle)

    Returns the hosted checkout URL to redirect the user to.
    """
    if not package.stripe_price_id:
        raise ValueError(
            f"Credit package '{package.name}' does not have a Stripe Price ID configured. "
            "An admin must set stripe_price_id on this package before it can be purchased."
        )

    plan_type = (package.plan_type or "one_time").lower()
    stripe_mode = "payment" if plan_type == "one_time" else "subscription"

    session = stripe.checkout.Session.create(
        mode=stripe_mode,
        line_items=[
            {
                "price": package.stripe_price_id,
                "quantity": 1,
            }
        ],
        client_reference_id=str(user.id),
        customer_email=user.email,
        metadata={
            "package_id": str(package.id),
            "user_id": str(user.id),
            "purchase_type": "credit_package",
        },
        success_url=settings.STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=settings.STRIPE_CANCEL_URL,
    )
    return session.url


# ---------------------------------------------------------------------------
# Credit Purchase Fulfillment  (checkout.session.completed — credit_package)
# ---------------------------------------------------------------------------

def fulfill_credit_purchase(session_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `checkout.session.completed` for a one-time credit purchase.
    Credits the user's account and records Payment + CreditTransaction rows.

    Idempotent: if a Payment row for this session already exists the call is a no-op.
    """
    try:
        session_id  = session_data.get("id", "")
        user_id     = int(session_data.get("metadata", {}).get("user_id", 0))
        package_id  = int(session_data.get("metadata", {}).get("package_id", 0))

        logger.info(
            "[Stripe] credit checkout.session.completed received "
            "session_id=%s user_id=%s package_id=%s",
            session_id, user_id, package_id,
        )

        if not user_id or not package_id:
            logger.warning("[Stripe] Missing user_id or package_id in metadata — skipping.")
            return

        # --- Idempotency guard ------------------------------------------------
        already_processed = db.query(Payment).filter(
            Payment.transaction_id == session_id
        ).first()
        if already_processed:
            logger.info("[Stripe] Session %s already processed — skipping duplicate.", session_id)
            return
        # -----------------------------------------------------------------------

        user    = db.query(User).filter(User.id == user_id).first()
        package = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()

        if not user:
            logger.error("[Stripe] User id=%s not found in DB.", user_id)
            return
        if not package:
            logger.error("[Stripe] CreditPackage id=%s not found in DB.", package_id)
            return

        credits_before = user.credits
        user.credits  += package.credits
        logger.info(
            "[Stripe] Crediting user id=%d: %d -> %d (+%d) via credit package '%s'",
            user.id, credits_before, user.credits, package.credits, package.name,
        )

        amount_cents = session_data.get("amount_total", 0) or 0

        credit_tx = CreditTransaction(
            user_id=user_id,
            amount=package.credits,
            type="purchase",
            source="stripe_payment",
            reference_id=session_id,
        )
        db.add(credit_tx)

        payment = Payment(
            user=user.email,
            payment_type="credit_package",
            amount=int(amount_cents),
            credits=package.credits,
            transaction_id=session_id,
            status="completed",
        )
        db.add(payment)

        db.commit()
        db.refresh(user)
        logger.info(
            "[Stripe] Credit purchase fulfilled for user id=%d. Credits after commit: %d",
            user.id, user.credits,
        )

    except Exception:
        logger.exception("[Stripe] fulfill_credit_purchase raised an unexpected error — rolling back.")
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Credit Subscription Activation  (checkout.session.completed — monthly/yearly)
# ---------------------------------------------------------------------------

def activate_credit_subscription(session_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `checkout.session.completed` for a recurring credit package.
    - Creates a UserCreditSubscription record.
    - Grants the first cycle's credits immediately.
    - Records Payment + CreditTransaction.

    Idempotent: skipped if a Payment row for this session already exists.
    """
    try:
        session_id             = session_data.get("id", "")
        user_id                = int(session_data.get("metadata", {}).get("user_id", 0))
        package_id             = int(session_data.get("metadata", {}).get("package_id", 0))
        stripe_subscription_id = session_data.get("subscription")
        stripe_customer_id     = session_data.get("customer")

        logger.info(
            "[Stripe] credit subscription checkout.session.completed "
            "session_id=%s user_id=%s package_id=%s stripe_sub=%s",
            session_id, user_id, package_id, stripe_subscription_id,
        )

        if not user_id or not package_id:
            logger.warning("[Stripe] Missing user_id or package_id in metadata — skipping.")
            return

        # --- Idempotency guard ------------------------------------------------
        already_processed = db.query(Payment).filter(
            Payment.transaction_id == session_id
        ).first()
        if already_processed:
            logger.info("[Stripe] Session %s already processed — skipping duplicate.", session_id)
            return
        # -----------------------------------------------------------------------

        user    = db.query(User).filter(User.id == user_id).first()
        package = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()

        if not user:
            logger.error("[Stripe] User id=%s not found in DB.", user_id)
            return
        if not package:
            logger.error("[Stripe] CreditPackage id=%s not found in DB.", package_id)
            return

        now      = datetime.utcnow()
        end_date = now + timedelta(days=30)   # fallback
        renewal_date = None

        if stripe_subscription_id:
            try:
                stripe_sub   = stripe.Subscription.retrieve(stripe_subscription_id)
                period_end   = getattr(stripe_sub, "current_period_end", None)
                if period_end:
                    end_date     = datetime.utcfromtimestamp(period_end)
                    renewal_date = end_date
            except Exception as e:
                logger.warning("[Stripe] Could not retrieve credit Stripe subscription: %s", e)

        # Deactivate any existing active credit subscription for the same package
        existing = db.query(UserCreditSubscription).filter(
            UserCreditSubscription.user_id == user_id,
            UserCreditSubscription.package_id == package_id,
            UserCreditSubscription.status == "active",
        ).all()
        for sub in existing:
            sub.status   = "expired"
            sub.end_date = now

        new_credit_sub = UserCreditSubscription(
            user_id=user_id,
            package_id=package_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            start_date=now,
            end_date=end_date,
            renewal_date=renewal_date,
            status="active",
        )
        db.add(new_credit_sub)

        # Grant first cycle's credits
        credits_before = user.credits
        user.credits  += package.credits
        logger.info(
            "[Stripe] First-cycle credit grant for user id=%d: %d -> %d (+%d) package='%s'",
            user.id, credits_before, user.credits, package.credits, package.name,
        )

        amount_cents = session_data.get("amount_total", 0) or 0

        credit_tx = CreditTransaction(
            user_id=user_id,
            amount=package.credits,
            type="purchase",
            source="stripe_payment",
            reference_id=stripe_subscription_id or session_id,
        )
        db.add(credit_tx)

        payment = Payment(
            user=user.email,
            payment_type="credit_package",
            amount=int(amount_cents),
            credits=package.credits,
            transaction_id=session_id,
            status="completed",
        )
        db.add(payment)

        db.commit()
        db.refresh(user)
        logger.info(
            "[Stripe] Credit subscription activated for user id=%d. Credits: %d",
            user.id, user.credits,
        )

    except Exception:
        logger.exception("[Stripe] activate_credit_subscription raised an unexpected error — rolling back.")
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Credit Subscription Renewal  (invoice.paid — credit package)
# ---------------------------------------------------------------------------

def handle_credit_invoice_paid(invoice_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `invoice.paid` (billing_reason=subscription_cycle)
    for a recurring credit package subscription.
    Adds another cycle's credits and extends the end_date.

    Idempotent: skipped if a Payment row for this invoice already exists.
    """
    try:
        invoice_id             = invoice_data.get("id", "")
        stripe_subscription_id = invoice_data.get("subscription")

        logger.info(
            "[Stripe] credit invoice.paid invoice_id=%s stripe_sub=%s",
            invoice_id, stripe_subscription_id,
        )

        if not stripe_subscription_id:
            logger.warning("[Stripe] credit invoice.paid has no subscription id — skipping.")
            return

        # --- Idempotency guard ------------------------------------------------
        already_processed = db.query(Payment).filter(
            Payment.transaction_id == invoice_id
        ).first()
        if already_processed:
            logger.info("[Stripe] Invoice %s already processed — skipping duplicate.", invoice_id)
            return
        # -----------------------------------------------------------------------

        credit_sub = db.query(UserCreditSubscription).filter(
            UserCreditSubscription.stripe_subscription_id == stripe_subscription_id,
            UserCreditSubscription.status == "active",
        ).first()

        if not credit_sub:
            logger.warning(
                "[Stripe] No active UserCreditSubscription for stripe_sub=%s",
                stripe_subscription_id,
            )
            return

        user    = db.query(User).filter(User.id == credit_sub.user_id).first()
        package = db.query(CreditPackage).filter(CreditPackage.id == credit_sub.package_id).first()

        if not user or not package:
            logger.error(
                "[Stripe] user or package not found for credit renewal: user_id=%s package_id=%s",
                credit_sub.user_id, credit_sub.package_id,
            )
            return

        now  = datetime.utcnow()
        base = max(credit_sub.end_date or now, now)
        credit_sub.end_date     = base + timedelta(days=30)
        credit_sub.renewal_date = credit_sub.end_date

        credits_before = user.credits
        user.credits  += package.credits
        logger.info(
            "[Stripe] Credit renewal for user id=%d: %d -> %d (+%d) package='%s'",
            user.id, credits_before, user.credits, package.credits, package.name,
        )

        amount_cents = invoice_data.get("amount_paid", 0) or 0

        credit_tx = CreditTransaction(
            user_id=user.id,
            amount=package.credits,
            type="purchase",
            source="stripe_renewal",
            reference_id=invoice_id,
        )
        db.add(credit_tx)

        payment = Payment(
            user=user.email,
            payment_type="credit_package",
            amount=int(amount_cents),
            credits=package.credits,
            transaction_id=invoice_id,
            status="completed",
        )
        db.add(payment)

        db.commit()
        db.refresh(user)
        logger.info(
            "[Stripe] Credit renewal processed. User id=%d credits: %d",
            user.id, user.credits,
        )

    except Exception:
        logger.exception("[Stripe] handle_credit_invoice_paid raised an unexpected error — rolling back.")
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Credit Subscription Expired  (customer.subscription.deleted — credit package)
# ---------------------------------------------------------------------------

def handle_credit_subscription_deleted(subscription_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `customer.subscription.deleted` for a recurring
    credit package subscription. Marks the local record as expired; no credits
    are removed (already granted credits are non-refundable by design).
    """
    stripe_subscription_id = subscription_data.get("id")
    if not stripe_subscription_id:
        return

    credit_sub = db.query(UserCreditSubscription).filter(
        UserCreditSubscription.stripe_subscription_id == stripe_subscription_id,
    ).first()

    if credit_sub:
        credit_sub.status   = "expired"
        credit_sub.end_date = datetime.utcnow()
        db.commit()
        logger.info(
            "[Stripe] UserCreditSubscription id=%d marked expired (stripe_sub=%s).",
            credit_sub.id, stripe_subscription_id,
        )


# ---------------------------------------------------------------------------
# Webhook Dispatch
# ---------------------------------------------------------------------------

def handle_webhook_event(payload: bytes, sig_header: str) -> dict:
    """
    Verify the Stripe webhook signature and dispatch to the correct handler.
    Returns a status dict.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid Stripe webhook signature")

    event_type = event["type"]
    # Convert the Stripe object to a genuine plain Python dict.
    # to_dict_recursive() can still leave nested Stripe objects; serialising
    # through JSON guarantees every level is a plain dict / list / primitive.
    raw = event["data"]["object"]
    event_data = json.loads(str(raw))

    return {"event_type": event_type, "event_data": event_data}


# ---------------------------------------------------------------------------
# Subscription Activation  (checkout.session.completed)
# ---------------------------------------------------------------------------

def activate_subscription(session_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `checkout.session.completed`.
    Provisions the subscription in the database, adds credits, and records
    a Payment and CreditTransaction.

    This function is idempotent: if the Payment record for this Stripe session
    already exists (e.g. Stripe retried the webhook), the call is a no-op.
    """
    try:
        session_id = session_data.get("id", "")
        user_id = int(session_data.get("metadata", {}).get("user_id", 0))
        plan_id = int(session_data.get("metadata", {}).get("plan_id", 0))
        stripe_subscription_id = session_data.get("subscription")
        stripe_customer_id = session_data.get("customer")

        logger.info(
            "[Stripe] checkout.session.completed received "
            "session_id=%s user_id=%s plan_id=%s stripe_sub=%s",
            session_id, user_id, plan_id, stripe_subscription_id,
        )

        if not user_id or not plan_id:
            logger.warning("[Stripe] Missing user_id or plan_id in metadata — skipping.")
            return

        # --- Idempotency guard -------------------------------------------------
        already_processed = db.query(Payment).filter(
            Payment.transaction_id == session_id
        ).first()
        if already_processed:
            logger.info("[Stripe] Session %s already processed — skipping duplicate.", session_id)
            return
        # -----------------------------------------------------------------------

        user = db.query(User).filter(User.id == user_id).first()
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

        if not user:
            logger.error("[Stripe] User id=%s not found in DB.", user_id)
            return
        if not plan:
            logger.error("[Stripe] SubscriptionPlan id=%s not found in DB.", plan_id)
            return

        logger.info(
            "[Stripe] Activating plan '%s' (%d credits) for user '%s' (id=%d). "
            "Current credits: %d",
            plan.name, plan.monthly_credits, user.email, user.id, user.credits,
        )

        now = datetime.utcnow()

        # Expire any existing active subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
        ).all()
        for sub in existing_subs:
            sub.status = "expired"
            sub.end_date = now

        # Retrieve subscription details from Stripe for period end date
        end_date = now + timedelta(days=30)  # fallback
        renewal_date = None
        if stripe_subscription_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                period_end_ts = getattr(stripe_sub, "current_period_end", None)
                if period_end_ts:
                    end_date = datetime.utcfromtimestamp(period_end_ts)
                    renewal_date = end_date
            except Exception as e:
                logger.warning("[Stripe] Could not retrieve Stripe subscription: %s", e)

        # Create new UserSubscription record
        new_sub = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            start_date=now,
            end_date=end_date,
            renewal_date=renewal_date,
            status="active",
        )
        db.add(new_sub)

        # Credit the user's account with the plan's monthly credits
        credits_before = user.credits
        user.credits += plan.monthly_credits
        logger.info(
            "[Stripe] Crediting user id=%d: %d -> %d (+%d)",
            user.id, credits_before, user.credits, plan.monthly_credits,
        )

        # Record a CreditTransaction
        amount_cents = session_data.get("amount_total", 0) or 0

        credit_tx = CreditTransaction(
            user_id=user_id,
            amount=plan.monthly_credits,
            type="subscription",
            source="stripe_payment",
            reference_id=stripe_subscription_id or session_id,
        )
        db.add(credit_tx)

        # Record a Payment entry for billing overview
        payment = Payment(
            user=user.email,
            payment_type="subscription",
            amount=int(amount_cents),
            credits=plan.monthly_credits,
            transaction_id=session_id,
            status="completed",
        )
        db.add(payment)

        db.commit()
        db.refresh(user)
        logger.info(
            "[Stripe] Successfully activated subscription for user id=%d. "
            "Credits after commit: %d",
            user.id, user.credits,
        )

    except Exception:
        logger.exception("[Stripe] activate_subscription raised an unexpected error — rolling back.")
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Subscription Renewal  (invoice.paid)
# ---------------------------------------------------------------------------

def handle_invoice_paid(invoice_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `invoice.paid` (monthly renewal).
    Re-credits the user and extends the subscription end date.

    This function is idempotent: if the Payment record for this invoice
    already exists (e.g. Stripe retried the webhook), the call is a no-op.
    """
    try:
        invoice_id = invoice_data.get("id", "")
        stripe_subscription_id = invoice_data.get("subscription")
        logger.info("[Stripe] invoice.paid received invoice_id=%s stripe_sub=%s", invoice_id, stripe_subscription_id)

        if not stripe_subscription_id:
            logger.warning("[Stripe] invoice.paid has no subscription id — skipping.")
            return

        # --- Idempotency guard -------------------------------------------------
        already_processed = db.query(Payment).filter(
            Payment.transaction_id == invoice_id
        ).first()
        if already_processed:
            logger.info("[Stripe] Invoice %s already processed — skipping duplicate.", invoice_id)
            return
        # -----------------------------------------------------------------------

        # Find the active subscription in the DB
        user_sub = db.query(UserSubscription).filter(
            UserSubscription.stripe_subscription_id == stripe_subscription_id,
            UserSubscription.status == "active",
        ).first()

        if not user_sub:
            logger.warning("[Stripe] No active UserSubscription for stripe_sub=%s", stripe_subscription_id)
            return

        user = db.query(User).filter(User.id == user_sub.user_id).first()
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == user_sub.plan_id).first()

        if not user or not plan:
            logger.error("[Stripe] user or plan not found for renewal: user_id=%s plan_id=%s", user_sub.user_id, user_sub.plan_id)
            return

        now = datetime.utcnow()

        # Extend subscription by 30 days from now (or from current end_date if still future)
        base = max(user_sub.end_date or now, now)
        user_sub.end_date = base + timedelta(days=30)
        user_sub.renewal_date = user_sub.end_date

        # Add monthly credits
        credits_before = user.credits
        user.credits += plan.monthly_credits
        logger.info(
            "[Stripe] Renewal credit for user id=%d: %d -> %d (+%d)",
            user.id, credits_before, user.credits, plan.monthly_credits,
        )

        # Record transaction
        amount_cents = invoice_data.get("amount_paid", 0) or 0
        credit_tx = CreditTransaction(
            user_id=user.id,
            amount=plan.monthly_credits,
            type="subscription",
            source="stripe_renewal",
            reference_id=invoice_id,
        )
        db.add(credit_tx)

        payment = Payment(
            user=user.email,
            payment_type="subscription",
            amount=int(amount_cents),
            credits=plan.monthly_credits,
            transaction_id=invoice_id,
            status="completed",
        )
        db.add(payment)

        db.commit()
        db.refresh(user)
        logger.info("[Stripe] Renewal processed. User id=%d credits after commit: %d", user.id, user.credits)

    except Exception:
        logger.exception("[Stripe] handle_invoice_paid raised an unexpected error — rolling back.")
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Payment Failed  (invoice.payment_failed)
# ---------------------------------------------------------------------------

def handle_invoice_payment_failed(invoice_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `invoice.payment_failed` (renewal charge declined).
    Marks the local subscription as `past_due` so the frontend can prompt the
    user to update their payment method.  Access is NOT immediately revoked —
    Stripe will retry the charge according to the retry schedule configured in
    the Stripe Dashboard.  If all retries fail, Stripe fires
    `customer.subscription.deleted` which is handled by handle_subscription_deleted.
    """
    stripe_subscription_id = invoice_data.get("subscription")
    if not stripe_subscription_id:
        return

    user_sub = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == stripe_subscription_id,
        UserSubscription.status == "active",
    ).first()

    if not user_sub:
        return

    # Downgrade to past_due — user retains access while Stripe retries
    user_sub.status = "past_due"
    db.commit()


# ---------------------------------------------------------------------------
# Subscription Cancellation
# ---------------------------------------------------------------------------

def cancel_subscription(stripe_subscription_id: str, db: Session) -> UserSubscription | None:
    """
    Cancel a Stripe subscription at period end and mark it cancelled in the DB.
    """
    # Cancel on Stripe (at_period_end=True = user keeps access until billing ends)
    stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=True)

    user_sub = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == stripe_subscription_id,
    ).first()

    if user_sub:
        user_sub.status = "cancelled"
        db.commit()
        db.refresh(user_sub)

    return user_sub


# ---------------------------------------------------------------------------
# Subscription Deleted / Expired  (customer.subscription.deleted)
# ---------------------------------------------------------------------------

def handle_subscription_deleted(subscription_data: dict, db: Session) -> None:
    """
    Called when Stripe fires `customer.subscription.deleted`.
    Marks the local subscription as expired.
    """
    stripe_subscription_id = subscription_data.get("id")
    if not stripe_subscription_id:
        return

    user_sub = db.query(UserSubscription).filter(
        UserSubscription.stripe_subscription_id == stripe_subscription_id,
    ).first()

    if user_sub:
        user_sub.status = "expired"
        user_sub.end_date = datetime.utcnow()
        db.commit()
