from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class SubscriptionPlanBase(BaseModel):
    name: str
    monthly_price: float = 0.0
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None   # Stripe recurring Price ID
    monthly_credits: int = 0
    video_limit_per_month: int = 0
    priority_level: int = 0
    commercial_usage_allowed: bool = False
    max_video_duration: int = 0  # in seconds
    max_concurrent_jobs: int = 1
    max_queued_jobs: int = 10
    max_retry_attempts: int = 3
    plan_status: str = "active"

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    monthly_price: Optional[float] = None
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    monthly_credits: Optional[int] = None
    video_limit_per_month: Optional[int] = None
    priority_level: Optional[int] = None
    commercial_usage_allowed: Optional[bool] = None
    max_video_duration: Optional[int] = None
    max_concurrent_jobs: Optional[int] = None
    max_queued_jobs: Optional[int] = None
    max_retry_attempts: Optional[int] = None
    plan_status: Optional[str] = None

class SubscriptionPlanInDB(SubscriptionPlanBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AssignPlanRequest(BaseModel):
    user_id: int
    plan_id: int
    duration_days: int = 30

# ---- Stripe-specific schemas ----

class CheckoutSessionRequest(BaseModel):
    plan_id: int

class CheckoutSessionResponse(BaseModel):
    checkout_url: str

class UserSubscriptionInDB(BaseModel):
    id: int
    user_id: int
    plan_id: int
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str
    renewal_date: Optional[datetime] = None
    created_at: datetime
    plan: Optional[SubscriptionPlanInDB] = None

    model_config = ConfigDict(from_attributes=True)
