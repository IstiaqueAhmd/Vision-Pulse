from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.base_class import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, nullable=False)
    payment_type = Column(String, nullable=False, default="purchase")
    amount = Column(Integer, nullable=False)
    credits = Column(Integer, nullable=False)
    transaction_id = Column(String(255), nullable=False, unique=True)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


