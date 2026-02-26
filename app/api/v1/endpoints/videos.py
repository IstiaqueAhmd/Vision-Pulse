from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.video import VideoCreate, VideoResponse
from app.services.video_service import create_video_job, get_video, get_all_videos, delete_video

router = APIRouter()

@router.post("/generate", response_model=VideoResponse)
def generate_video(video_in: VideoCreate, db: Session = Depends(get_db)):
    """
    Submit a new video generation job.
    Accepts video parameters, creates a job in the database, and schedules processing in the background.
    """
    # Note: user authentication could be added here as: current_user: User = Depends(get_current_user)
    # mock user ID for now
    user_id = 1
    
    # 1. Create the video generation job in the database and trigger worker
    video = create_video_job(db=db, video_in=video_in, user_id=user_id)
    return video

@router.get("/videos", response_model=list[VideoResponse])
def list_videos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all generated videos.
    """
    videos = get_all_videos(db, skip=skip, limit=limit)
    return videos

@router.get("/video/{video_id}", response_model=VideoResponse)
def get_video_status(video_id: int, db: Session = Depends(get_db)):
    """
    Get video metadata and status.
    """
    video = get_video(db, video_id=video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.delete("/video/{video_id}")
def remove_video(video_id: int, db: Session = Depends(get_db)):
    """
    Delete a video.
    """
    success = delete_video(db, video_id=video_id)
    if not success:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "deleted"}
