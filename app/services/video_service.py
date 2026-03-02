from sqlalchemy.orm import Session
from app.models.video import Video
from app.schemas.video import VideoCreate


def create_video_job(db: Session, video_in: VideoCreate, user_id: int):
    """Create a DB record for the queued video, linked to the requesting user."""
    db_video = Video(
        user_id=user_id,
        title=video_in.title,
        category=video_in.category,
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


def get_video(db: Session, video_id: int):
    return db.query(Video).filter(Video.id == video_id).first()


def get_all_videos(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Video).offset(skip).limit(limit).all()


def delete_video(db: Session, video_id: int):
    video = db.query(Video).filter(Video.id == video_id).first()
    if video:
        db.delete(video)
        db.commit()
        return True
    return False
