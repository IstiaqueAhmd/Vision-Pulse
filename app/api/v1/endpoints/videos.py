from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.schemas.video import VideoCreate, VideoResponse
from app.services.video_service import create_video_job, get_video, get_all_videos, delete_video
from app.workers.job_queue import JobQueue, JobStatus
from app.workers.pipeline import VideoGeneratorPipeline


router = APIRouter()

job_queue = JobQueue()

pipeline = VideoGeneratorPipeline()

@router.post("/create-video")
async def create_video(video_data: VideoCreate):
    """Create a new video from request data - adds to queue with deduplication"""
    try:
        # Log incoming request
        print(f"Received video request: {video_data.dict()}")
        print(f"Script length: {len(video_data.script)}, Max allowed: {settings.MAX_SCRIPT_LENGTH}")
        
        # Validate script length
        if len(video_data.script) > settings.MAX_SCRIPT_LENGTH:
            print(f"Script too long! {len(video_data.script)} > {settings.MAX_SCRIPT_LENGTH}")
            raise HTTPException(
                status_code=400,
                detail=f'Script too long. Maximum {settings.MAX_SCRIPT_LENGTH} characters'
            )
        
        # Check if system can accept new jobs
        can_accept, reason = job_queue.can_accept_new_job()
        if not can_accept:
            raise HTTPException(
                status_code=429,  # Too Many Requests
                detail=reason
            )
        
        # Add job to queue (always creates new video with unique ID and path)
        job_id = job_queue.add_job(video_data.dict())
        
        # Get current job status
        job = job_queue.get_job(job_id)
        
        # Get queue position if queued
        position = job_queue.get_queue_position(job_id) if job['status'] == JobStatus.QUEUED else -1
        
        response_content = {
            'job_id': job_id,
            'message': 'Video generation job added to queue',
            'status': job['status']
        }
        
        if position >= 0:
            response_content['queue_position'] = position
        
        if job['status'] == JobStatus.COMPLETED and job.get('result'):
            response_content['result'] = job['result']
        
        # Return immediately with 202 Accepted
        return JSONResponse(
            content=response_content,
            status_code=202
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in create_video: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/job-status/{job_id}')
async def job_status(job_id: str):
    """Check status of a video generation job"""
    job = job_queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    
    # Get queue position if still queued
    if job['status'] == JobStatus.QUEUED:
        position = job_queue.get_queue_position(job_id)
        job['queue_position'] = position
    
    return JSONResponse(
        content=job,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )



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
