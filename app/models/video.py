from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from app.db.base import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    category = Column(String, index=True, nullable=True)
    format = Column(String)
    style = Column(String)
    voice = Column(String)
    script = Column(Text)
    path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String, default="queued") # queued, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
