from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import settings
from app.schemas.video import VideoCreate, VideoResponse, VideoUpdate
from app.services.video_service import create_video_job, get_video, get_all_videos, delete_video, update_video
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

@router.put("/update/{video_id}")
async def regenerate_video(
    video_id: int,
    video_update: VideoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Regenerate a video under the same video ID — queues a new generation job,
    deletes the previous video file, and reuses the existing DB record.
    Any fields omitted from the request body are preserved from the existing video.
    """
    try:
        # Look up the existing video (must be owned by current user)
        video = get_video(db, video_id=video_id, user_id=current_user.id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found or you don't have permission to update it")

        # Merge update fields over existing video data
        update_data = video_update.dict(exclude_unset=True)
        payload = {
            "title": update_data.get("title", video.title),
            "format": update_data.get("format", video.format),
            "style": update_data.get("style", video.style),
            "voice": update_data.get("voice", video.voice),
            "script": update_data.get("script", video.script),
            "keywords": update_data.get("keywords", video.keywords),
            "negative_keywords": update_data.get("negative_keywords", video.negative_keywords),
            "music_id": update_data.get("music_id", video.music_id),
            "subtitle_id": update_data.get("subtitle_id", video.subtitle_id),
            "media_option": update_data.get("media_option", video.media_option),
            "user_id": current_user.id,
            "_update_video_id": video_id,
        }

        # Validate script length
        if len(payload["script"]) > settings.MAX_SCRIPT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f'Script too long. Maximum {settings.MAX_SCRIPT_LENGTH} characters'
            )

        # Check system capacity
        can_accept, reason = job_queue.can_accept_new_job()
        if not can_accept:
            raise HTTPException(status_code=429, detail=reason)

        # Mark the existing DB record as queued so clients can track progress
        video.status = "queued"
        video.path = None
        video.duration = None
        db.commit()

        # Add regeneration job to queue
        job_id = job_queue.add_job(payload)
        job = job_queue.get_job(job_id)
        position = job_queue.get_queue_position(job_id) if job['status'] == JobStatus.QUEUED else -1

        response_content = {
            'job_id': job_id,
            'video_id': video_id,
            'message': 'Video regeneration job added to queue',
            'status': job['status'],
            'user_id': current_user.id,
        }
        if position >= 0:
            response_content['queue_position'] = position

        return JSONResponse(content=response_content, status_code=202)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in regenerate_video: {str(e)}")
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

@router.get('/queue')
async def get_queue(current_user: User = Depends(get_current_user)):
    """Get all jobs in queue for the authenticated user"""
    all_queued = job_queue.get_queued_jobs()
    all_processing = job_queue.get_processing_jobs()
    
    # Filter jobs by current user's ID
    queued = [job for job in all_queued if job.get('video_data', {}).get('user_id') == current_user.id]
    processing = [job for job in all_processing if job.get('video_data', {}).get('user_id') == current_user.id]
    
    return JSONResponse(content={
        'queued': queued,
        'processing': processing,
        'total_queued': len(queued),
        'total_processing': len(processing)
    })

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
    return list(reversed(videos))

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
