from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PoliciesBase(BaseModel):
    privacy_policy: Optional[str] = None
    terms_of_service: Optional[str] = None
    refund_policy: Optional[str] = None

class PoliciesCreate(PoliciesBase):
    pass

class PoliciesUpdate(PoliciesBase):
    pass

class PoliciesResponse(PoliciesBase):
    id: int
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None

    class Config:
        from_attributes = True
