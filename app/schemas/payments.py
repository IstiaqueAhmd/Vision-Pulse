from pydantic import BaseModel
from datetime import datetime
from typing import List

class PaymentRecord(BaseModel):
    id: int
    user: str
    payment_type: str
    amount: int
    credits: int
    transaction_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class BillingOverviewResponse(BaseModel):
    total_revenue: float
    refund_amount: float
    net_revenue: float
    records: List[PaymentRecord]
