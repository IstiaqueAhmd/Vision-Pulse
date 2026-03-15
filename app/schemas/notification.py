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
