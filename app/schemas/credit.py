from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CreditPackageCreate(BaseModel):
    name: str
    credits: int
    price: float
    product_id: Optional[str] = None # Stripe product ID for this package
    stripe_price_id: Optional[str] = None # Stripe Price ID
    interval: Optional[str] = None
    status: str = "active" # "active", "inactive"

class CreditPackageUpdate(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    interval: Optional[str] = None
    status: Optional[str] = None # "active", "inactive"

class CreditPackageResponse(BaseModel):
    id: int
    name: str
    credits: int
    price: float
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    interval: Optional[str] = None
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class CreditTransactionCreate(BaseModel):
    user_id: int
    amount: int
    type: str # "earn", "spend", "purchase", "subscription"
    source: str # "video_generation", "stripe_payment", "monthly_renewal"
    reference_id: Optional[str] = None

class GiveCreditRequest(BaseModel):
    amount: int  # Number of credits to grant (must be > 0)
    note: Optional[str] = None  # Optional admin note / reason

class GiveCreditResponse(BaseModel):
    message: str
    user_id: int
    credits_granted: int
    new_balance: int
    transaction_id: int
