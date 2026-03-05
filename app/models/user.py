from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable because of OAuth users
    auth_provider = Column(String, default="local")   # "local", "google", etc.
    reset_otp = Column(String, nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)
    credits = Column(Integer, default=400, nullable=False)
    subscription_plan = Column(String, default="free", nullable=False)  # "free", "pro", "enterprise"
    role = Column(String, default="user", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
