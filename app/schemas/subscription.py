from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class SubscriptionPlanBase(BaseModel):
    name: str
    monthly_price: float = 0.0
    monthly_credits: int = 0
    video_limit_per_month: int = 0
    priority_level: int = 0
    commercial_usage_allowed: bool = False
    max_video_duration: int = 0 # in seconds
    plan_status: str = "active"

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    monthly_price: Optional[float] = None
    monthly_credits: Optional[int] = None
    video_limit_per_month: Optional[int] = None
    priority_level: Optional[int] = None
    commercial_usage_allowed: Optional[bool] = None
    max_video_duration: Optional[int] = None
    plan_status: Optional[str] = None

class SubscriptionPlanInDB(SubscriptionPlanBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
