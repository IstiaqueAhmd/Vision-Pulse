from sqlalchemy import Column, Integer, Text, DateTime
from datetime import datetime
from app.db.base_class import Base

class PrivacyPolicy(Base):
    __tablename__ = "privacy_policy"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
