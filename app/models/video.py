from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    music_id = Column(Integer, ForeignKey("musics.id"), nullable=True, index=True)
    title = Column(String, index=True)
    format = Column(String)
    style = Column(String)
    voice = Column(String)
    script = Column(Text)
    keywords = Column(Text, nullable=True)
    negative_keywords = Column(Text, nullable=True)
    path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String, default="queued")  # queued, processing, completed, failed
    media_option = Column(String, default="all_images")  # all_images, first_scene, last_scene, first_and_last_scene
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="videos")
    music = relationship("Music")
