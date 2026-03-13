from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FAQBase(BaseModel):
    Question: str
    Answer: str

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    Question: Optional[str] = None
    Answer: Optional[str] = None

class FAQResponse(FAQBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True
