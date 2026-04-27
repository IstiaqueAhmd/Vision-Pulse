from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    profile_image_url = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # Nullable because of OAuth users
    auth_provider = Column(String, default="local")   # "local", "google", etc.
    reset_otp = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False)
    credits = Column(Integer, default=0, nullable=False)
    role = Column(String, default="user", nullable=False)
    status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")
    credit_subscriptions = relationship("UserCreditSubscription", back_populates="user", cascade="all, delete-orphan")
