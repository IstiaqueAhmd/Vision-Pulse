from pydantic import BaseModel
from datetime import datetime

class PrivacyPolicyBase(BaseModel):
    content: str

class PrivacyPolicyCreate(PrivacyPolicyBase):
    pass

class PrivacyPolicyUpdate(PrivacyPolicyBase):
    pass

class PrivacyPolicyResponse(PrivacyPolicyBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True
