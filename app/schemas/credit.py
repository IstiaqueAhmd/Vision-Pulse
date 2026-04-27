from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime

class CreditPackageCreate(BaseModel):
    name: str
    credits: int
    price: float
    product_id: Optional[str] = None # Stripe product ID for this package
    stripe_price_id: Optional[str] = None # Stripe Price ID
    plan_type: Optional[Literal["one_time", "monthly", "yearly"]] = None
    status: str = "active" # "active", "inactive"

class CreditPackageUpdate(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    plan_type: Optional[Literal["one_time", "monthly", "yearly"]] = None
    status: Optional[str] = None # "active", "inactive"

class CreditPackageResponse(BaseModel):
    id: int
    name: str
    credits: int
    price: float
    product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    plan_type: Optional[Literal["one_time", "monthly", "yearly"]] = None
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

class CreditCheckoutSessionRequest(BaseModel):
    package_id: int = Field(..., description="ID of the CreditPackage to purchase")

class CreditCheckoutSessionResponse(BaseModel):
    checkout_url: str = Field(..., description="Stripe-hosted checkout URL to redirect the user to")

class CreditTransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    type: str  # "earn", "spend", "purchase", "subscription"
    source: str  # "video_generation", "stripe_payment", "monthly_renewal"
    reference_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CreditWalletResponse(BaseModel):
    user_credits: int
    purchased: int
    used: int
    remaining: int
    transaction_history: List[CreditTransactionResponse]

    class Config:
        from_attributes = True