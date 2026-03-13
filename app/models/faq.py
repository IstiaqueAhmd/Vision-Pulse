from sqlalchemy import Column, Integer, Text, DateTime
from datetime import datetime
from app.db.base_class import Base

class FAQ(Base):
    __tablename__ = "faq"

    id = Column(Integer, primary_key=True, index=True)
    Question = Column(Text, nullable=False)
    Answer = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
