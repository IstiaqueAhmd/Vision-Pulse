import os
from sqlalchemy.orm import Session
from app.models.video import Video
from app.schemas.video import VideoCreate


def create_video_job(db: Session, video_in: VideoCreate, user_id: int):
    """Create a DB record for the queued video, linked to the requesting user."""
    db_video = Video(
        user_id=user_id,
        title=video_in.title,
        format=video_in.format,
        style=video_in.style,
        voice=video_in.voice,
        script=video_in.script,
        keywords=video_in.keywords,
        negative_keywords=video_in.negative_keywords,
        # Default status from model is "queued"
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    return db_video


def get_video(db: Session, video_id: int, user_id: int = None):
    query = db.query(Video).filter(Video.id == video_id)
    if user_id is not None:
        query = query.filter(Video.user_id == user_id)
    return query.first()


def get_all_videos(db: Session, user_id: int = None, search: str = None, skip: int = 0, limit: int = 100):
    query = db.query(Video)
    if user_id is not None:
        query = query.filter(Video.user_id == user_id)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Video.title.ilike(search_pattern))
        )
    return query.offset(skip).limit(limit).all()


def delete_video(db: Session, video_id: int, user_id: int = None):
    query = db.query(Video).filter(Video.id == video_id)
    if user_id is not None:
        query = query.filter(Video.user_id == user_id)
    video = query.first()
    if video:
        # Delete the video file from disk
        if video.path and os.path.exists(video.path):
            os.remove(video.path)
        db.delete(video)
        db.commit()
        return True
    return False
