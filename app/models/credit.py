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
    product_id = Column(String, nullable=True) # Stripe product ID for this package
    stripe_price_id = Column(String, nullable=True)  # Stripe Price ID
    plan_type = Column(String, nullable=True)  # "one_time", "monthly", "yearly"
    status = Column(String, default="active") # "active", "inactive", "archived"
    created_at = Column(DateTime, default=datetime.utcnow)


class UserCreditSubscription(Base):
    """
    Tracks an active recurring credit package subscription for a user.
    Created on checkout.session.completed (monthly/yearly packages only).
    Updated on invoice.paid (renewal) and customer.subscription.deleted (expiry).
    """
    __tablename__ = "user_credit_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("credit_packages.id"), nullable=False)
    stripe_subscription_id = Column(String, nullable=True, index=True, unique=True)
    stripe_customer_id = Column(String, nullable=True)
    # status: "active" | "cancelled" | "expired" | "past_due"
    status = Column(String, default="active", nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)     # next billing date / expiry
    renewal_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_subscriptions")
    package = relationship("CreditPackage")


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
