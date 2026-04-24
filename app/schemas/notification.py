from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: str
    is_read: bool
    video_id: int | None = None
    job_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationCountResponse(BaseModel):
    unread: int


class NotificationSettingsUpdateRequest(BaseModel):
    email: bool | None = None
    low_balance: bool | None = None
    payment: bool | None = None
    video_status: bool | None = None
    message: bool | None = None
    product_update: bool | None = None

class NotificationSettingsUpdateResponse(BaseModel):
    id: int
    user_id: int
    email: bool
    low_balance: bool
    payment: bool
    video_status: bool
    message: bool
    product_update: bool

    model_config = ConfigDict(from_attributes=True)
