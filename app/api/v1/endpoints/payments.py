"""
Payment endpoints — Stripe subscription checkout, webhook, cancellation, and current subscription view.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.schemas.subscription import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    UserSubscriptionInDB,
)
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
        stripe_service.activate_subscription(session_data=event_data, db=db)

    elif event_type == "invoice.paid":
        # Skip the first invoice — it is already handled by checkout.session.completed
        billing_reason = event_data.get("billing_reason", "")
        if billing_reason == "subscription_cycle":
            stripe_service.handle_invoice_paid(invoice_data=event_data, db=db)

    elif event_type == "customer.subscription.deleted":
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

@router.get("/subscription/me", response_model=UserSubscriptionInDB)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the current user's active subscription, including plan details.
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

    return sub
