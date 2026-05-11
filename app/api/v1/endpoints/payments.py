"""
Payment endpoints — Stripe subscription/credit checkout, webhook, cancellation, current subscription view, and user payment history.
"""
import math
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.payments import Payment
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.credit import CreditPackage, UserCreditSubscription
from app.schemas.subscription import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    UserSubscriptionInDB,
    UserSubscriptionWithCredits,
)
from app.schemas.credit import (
    CreditCheckoutSessionRequest,
    CreditCheckoutSessionResponse,
)
from app.schemas.payments import UserPaymentsResponse
from app.services import stripe_service

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /payments/subscription/checkout
# ---------------------------------------------------------------------------

@router.post(
    "/subscription/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
)
def create_subscription_checkout(
    body: CheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout Session for the given subscription plan.
    Returns a `checkout_url` where the user should be redirected to complete payment.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == body.plan_id,
        SubscriptionPlan.plan_status == "active",
    ).first()

    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found or not active.",
        )

    if not plan.stripe_price_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Plan '{plan.name}' is not yet configured for online purchase. "
                "Please contact support."
            ),
        )

    try:
        checkout_url = stripe_service.create_checkout_session(plan=plan, user=current_user)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    return CheckoutSessionResponse(checkout_url=checkout_url)


# ---------------------------------------------------------------------------
# POST /payments/credit/checkout
# ---------------------------------------------------------------------------

@router.post(
    "/credit/checkout",
    response_model=CreditCheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
)
def create_credit_checkout(
    body: CreditCheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Stripe Checkout Session (one-time payment) for the given credit package.
    Returns a `checkout_url` where the user should be redirected to complete payment.
    Credits are added to the user's account automatically via webhook after payment.
    """
    package = db.query(CreditPackage).filter(
        CreditPackage.id == body.package_id,
        CreditPackage.status == "active",
    ).first()

    if not package:
        raise HTTPException(
            status_code=404,
            detail="Credit package not found or not active.",
        )

    if not package.stripe_price_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Credit package '{package.name}' is not yet configured for online purchase. "
                "Please contact support."
            ),
        )

    try:
        checkout_url = stripe_service.create_credit_checkout_session(
            package=package, user=current_user
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    return CreditCheckoutSessionResponse(checkout_url=checkout_url)


# ---------------------------------------------------------------------------
# POST /payments/webhook
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook listener.
    Stripe sends signed POST requests here when payment events occur.
    Must NOT require authentication — Stripe verifies the payload with a signature.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        result = stripe_service.handle_webhook_event(payload=payload, sig_header=sig_header)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_type = result["event_type"]
    event_data = result["event_data"]

    if event_type == "checkout.session.completed":
        purchase_type = event_data.get("metadata", {}).get("purchase_type", "")
        if purchase_type == "credit_package":
            # mode="payment" → one_time; mode="subscription" → monthly/yearly
            stripe_mode = event_data.get("mode", "payment")
            if stripe_mode == "subscription":
                stripe_service.activate_credit_subscription(session_data=event_data, db=db)
            else:
                stripe_service.fulfill_credit_purchase(session_data=event_data, db=db)
        else:
            stripe_service.activate_subscription(session_data=event_data, db=db)

    elif event_type == "invoice.paid":
        # Skip the first invoice — already handled by checkout.session.completed
        billing_reason = event_data.get("billing_reason", "")
        if billing_reason == "subscription_cycle":
            stripe_sub_id = event_data.get("subscription")
            # Check which type owns this Stripe subscription
            is_credit_sub = db.query(UserCreditSubscription).filter(
                UserCreditSubscription.stripe_subscription_id == stripe_sub_id,
                UserCreditSubscription.status == "active",
            ).first()
            if is_credit_sub:
                stripe_service.handle_credit_invoice_paid(invoice_data=event_data, db=db)
            else:
                stripe_service.handle_invoice_paid(invoice_data=event_data, db=db)

    elif event_type == "invoice.payment_failed":
        # Renewal charge declined — mark subscription as past_due
        stripe_service.handle_invoice_payment_failed(invoice_data=event_data, db=db)

    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = event_data.get("id")
        # Check which type owns this Stripe subscription
        is_credit_sub = db.query(UserCreditSubscription).filter(
            UserCreditSubscription.stripe_subscription_id == stripe_sub_id,
        ).first()
        if is_credit_sub:
            stripe_service.handle_credit_subscription_deleted(subscription_data=event_data, db=db)
        else:
            stripe_service.handle_subscription_deleted(subscription_data=event_data, db=db)

    return {"status": "ok", "event": event_type}


# ---------------------------------------------------------------------------
# DELETE /payments/subscription/cancel
# ---------------------------------------------------------------------------

@router.delete("/subscription/cancel", status_code=status.HTTP_200_OK)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel the current user's active Stripe subscription at the end of the billing period.
    The user retains access until the current period ends.
    """
    active_sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == current_user.id,
        UserSubscription.status == "active",
    ).first()

    if not active_sub:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    if not active_sub.stripe_subscription_id:
        raise HTTPException(
            status_code=400,
            detail="This subscription was not created via Stripe and cannot be cancelled here.",
        )

    try:
        stripe_service.cancel_subscription(
            stripe_subscription_id=active_sub.stripe_subscription_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    return {
        "message": "Subscription cancelled. You will retain access until the current billing period ends.",
        "end_date": active_sub.end_date,
    }


# ---------------------------------------------------------------------------
# GET /payments/subscription/me
# ---------------------------------------------------------------------------

@router.get("/subscription/me", response_model=UserSubscriptionWithCredits)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the current user's active subscription, including plan details and credits.
    """
    sub = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.created_at.desc())
        .first()
    )

    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    sub.credits = current_user.credits
    return sub


# ---------------------------------------------------------------------------
# GET /payments/history
# ---------------------------------------------------------------------------

@router.get("/history", response_model=UserPaymentsResponse)
def get_my_payment_history(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Records per page (1–100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the authenticated user's full payment history from the `payments` table,
    ordered newest-first and paginated.

    Query params:
    - **page**: page number, 1-indexed (default 1)
    - **page_size**: records per page, 1–100 (default 20)
    """
    base_query = db.query(Payment).filter(Payment.user == current_user.email)

    total_payments = base_query.count()
    total_pages = math.ceil(total_payments / page_size) if total_payments else 1

    payments = (
        base_query
        .order_by(Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return UserPaymentsResponse(
        page=page,
        page_size=page_size,
        total_payments=total_payments,
        total_pages=total_pages,
        payments=payments,
    )
