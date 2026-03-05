from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.schemas.video import VideoCreate, VideoResponse
from app.services.video_service import create_video_job, get_video, get_all_videos, delete_video
from app.workers.job_queue import JobQueue, JobStatus
from app.workers.pipeline import VideoGeneratorPipeline
from app.api.deps import get_current_user
from app.models.user import User
from elevenlabs import ElevenLabs

router = APIRouter()

job_queue = JobQueue()

pipeline = VideoGeneratorPipeline()

@router.get("/elevenlabs-voices")
async def get_elevenlabs_voices(current_user: User = Depends(get_current_user)):
    """Get all available voices from ElevenLabs API"""
    try:
        client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        voices = client.voices.get_all()
        
        voice_list = []
        for voice in voices.voices:
            voice_list.append({
                "name": voice.name,
                "voice_id": voice.voice_id,
                "category": getattr(voice, 'category', 'unknown'),
                "labels": getattr(voice, 'labels', {})
            })
        
        return JSONResponse(content={
            "success": True,
            "voices": voice_list,
            "count": len(voice_list),
            "message": "ElevenLabs voices retrieved successfully"
        })
        
    except Exception as e:
        print(f"Error fetching ElevenLabs voices: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": "Failed to fetch ElevenLabs voices"
            }
        )

@router.post("/create-video")
async def create_video(
    video_data: VideoCreate,
    current_user: User = Depends(get_current_user),
):
    """Create a new video — requires a valid JWT Bearer token."""
    try:
        # Log incoming request
        print(f"Received video request from user {current_user.id}: {video_data.dict()}")
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

        # Inject user info into the video payload
        payload = video_data.dict()
        payload["user_id"] = current_user.id

        # Add job to queue
        job_id = job_queue.add_job(payload)

        # Get current job status
        job = job_queue.get_job(job_id)

        # Get queue position if queued
        position = job_queue.get_queue_position(job_id) if job['status'] == JobStatus.QUEUED else -1

        response_content = {
            'job_id': job_id,
            'message': 'Video generation job added to queue',
            'status': job['status'],
            'user_id': current_user.id,
            'user_credits': current_user.credits,
            'subscription_plan': current_user.subscription_plan,
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

@router.get("/get-all", response_model=list[VideoResponse])
def list_videos(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all videos belonging to the current user. Optionally filter by search query.
    """
    videos = get_all_videos(db, user_id=current_user.id, search=search, skip=skip, limit=limit)
    return videos

@router.get("/get/{video_id}", response_model=VideoResponse)
def get_video_status(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get video metadata and status — only if owned by current user.
    """
    video = get_video(db, video_id=video_id, user_id=current_user.id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.delete("/delete/{video_id}")
def remove_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a video — only if owned by current user.
    """
    success = delete_video(db, video_id=video_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": "deleted"}
