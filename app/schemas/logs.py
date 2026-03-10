from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class LogsResponse(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    action_type: Optional[str] = None
    reference_id: Optional[str] = None
    status: Optional[str] = None
    date_time: datetime

    model_config = ConfigDict(from_attributes=True)
