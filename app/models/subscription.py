from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    monthly_price = Column(Float, nullable=False, default=0.0)
    monthly_credits = Column(Integer, nullable=False, default=0)
    video_limit_per_month = Column(Integer, nullable=False, default=0)
    priority_level = Column(Integer, nullable=False, default=0) 
    commercial_usage_allowed = Column(Boolean, nullable=False, default=False)
    max_video_duration = Column(Integer, nullable=False, default=0) # in seconds
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("UserSubscription", back_populates="plan", cascade="all, delete-orphan")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), index=True, nullable=False)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="active") # "active", "cancelled", "expired"
    renewal_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
