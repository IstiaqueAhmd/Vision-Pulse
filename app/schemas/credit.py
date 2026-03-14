from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CreditPackageCreate(BaseModel):
    name: str
    credits: int
    price: float

class CreditPackageUpdate(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None

class CreditPackageResponse(BaseModel):
    id: int
    name: str
    credits: int
    price: float
    created_at: Optional[datetime]

    class Config:
        from_attributes = True
