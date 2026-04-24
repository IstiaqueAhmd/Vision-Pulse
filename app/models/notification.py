from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, default="video", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    video_id = Column(Integer, nullable=True, index=True)
    job_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    email = Column(Boolean, default=True, nullable=False)
    low_balance = Column(Boolean, default=True, nullable=False)
    payment = Column(Boolean, default=True, nullable=False)
    video_status = Column(Boolean, default=True, nullable=False)
    message = Column(Boolean, default=True, nullable=False)
    product_update = Column(Boolean, default=True, nullable=False)

    user = relationship("User")