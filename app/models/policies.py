from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from datetime import datetime
from app.db.base_class import Base

class Policies(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    privacy_policy = Column(Text, nullable=True)
    terms_of_service = Column(Text, nullable=True)
    refund_policy = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)