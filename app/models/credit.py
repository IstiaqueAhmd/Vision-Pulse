from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base

class CreditPackage(Base):
    __tablename__ = "credit_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    credits = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    type = Column(String, nullable=False) # "earn", "spend", "purchase", "subscription"
    source = Column(String, nullable=False) # "video_generation", "stripe_payment", "monthly_renewal"
    reference_id = Column(String, nullable=True) # id from stripe or other external system
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
