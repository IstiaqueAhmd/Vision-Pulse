"""
Job Queue Manager for Video Generation
Handles queueing and tracking of video generation jobs
"""
from app.core.config import settings
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from enum import Enum


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobQueue:
    """
    Simple file-based job queue manager
    Stores jobs in JSON file for persistence
    """
    
    def __init__(self, queue_file: str = "outputs/job_queue.json"):
        """Initialize job queue"""
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize queue file if it doesn't exist
        if not self.queue_file.exists():
            self._save_queue({"jobs": {}, "queue": []})
    
    def _load_queue(self) -> Dict:
        """Load queue from file"""
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"jobs": {}, "queue": []}
    
    def _save_queue(self, data: Dict):
        """Save queue to file"""
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_job(self, video_data: Dict) -> str:
        """
        Add a new job to the queue
        Every request creates a completely new job with unique ID and path
        
        Args:
            video_data: Video generation parameters
            
        Returns:
            Unique job ID (always creates new job)
        """
        # Always generate new unique job ID
        job_id = str(uuid.uuid4())
        
        data = self._load_queue()
        
        # Add unique timestamp and random seed to ensure different generation each time
        video_data_with_seed = video_data.copy()
        video_data_with_seed['_generation_seed'] = datetime.now().isoformat()
        video_data_with_seed['_unique_id'] = job_id  # Ensure uniqueness
        
        job = {
            'id': job_id,
            'status': JobStatus.QUEUED,
            'progress': 0,
            'message': 'Job queued',
            'video_data': video_data_with_seed,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None
        }
        
        data['jobs'][job_id] = job
        data['queue'].append(job_id)
        
        self._save_queue(data)
        
        print(f"✓ New job created: {job_id} - Title: {video_data.get('title', 'Untitled')}")
        
        return job_id
    
    def get_next_job(self) -> Optional[Dict]:
        """
        Get next job from queue (respects concurrency limits)
        
        Returns:
            Job dict or None if queue is empty or at capacity
        """

        data = self._load_queue()
        
        # Check if we're at max concurrent processing
        processing_count = sum(1 for job in data['jobs'].values() if job['status'] == JobStatus.PROCESSING)
        if processing_count >= settings.MAX_CONCURRENT_JOBS:
            return None
        
        # Find first queued job that's ready to process
        for job_id in data['queue']:
            job = data['jobs'].get(job_id)
            if job and job['status'] == JobStatus.QUEUED:
                # Check if job is waiting for retry delay
                retry_at = job.get('retry_at')
                if retry_at:
                    retry_time = datetime.fromisoformat(retry_at)
                    if datetime.now() < retry_time:
                        continue  # Skip this job, not ready yet
                
                return job
        
        return None
    
    def update_job(self, job_id: str, updates: Dict):
        """
        Update job status and details
        
        Args:
            job_id: Job identifier
            updates: Dictionary with fields to update
        """
        data = self._load_queue()
        
        if job_id not in data['jobs']:
            raise ValueError(f"Job {job_id} not found")
        
        job = data['jobs'][job_id]
        job.update(updates)
        
        self._save_queue(data)
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Get job by ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job dict or None
        """
        data = self._load_queue()
        return data['jobs'].get(job_id)
    
    def get_all_jobs(self) -> List[Dict]:
        """
        Get all jobs
        
        Returns:
            List of all jobs
        """
        data = self._load_queue()
        return list(data['jobs'].values())
    
    def get_queued_jobs(self) -> List[Dict]:
        """
        Get all queued jobs
        
        Returns:
            List of queued jobs
        """
        data = self._load_queue()
        return [
            job for job in data['jobs'].values()
            if job['status'] == JobStatus.QUEUED
        ]
    
    def get_processing_jobs(self) -> List[Dict]:
        """
        Get all processing jobs
        
        Returns:
            List of processing jobs
        """
        data = self._load_queue()
        return [
            job for job in data['jobs'].values()
            if job['status'] == JobStatus.PROCESSING
        ]
    
    def can_accept_new_job(self) -> tuple[bool, str]:
        """
        Check if system can accept a new job based on limits
        
        Returns:
            Tuple of (can_accept, reason)
        """
        
        queued_count = len(self.get_queued_jobs())
        processing_count = len(self.get_processing_jobs())
        
        # Check if too many jobs processing
        if processing_count >= settings.MAX_CONCURRENT_JOBS:
            return False, f"Server at capacity ({processing_count}/{settings.MAX_CONCURRENT_JOBS} videos processing). Please wait."
        
        # Check if queue is full
        if queued_count >= settings.MAX_QUEUED_JOBS:
            return False, f"Queue is full ({queued_count}/{settings.MAX_QUEUED_JOBS} jobs waiting). Please try again later."
        
        return True, "OK"
    
    def mark_job_for_retry(self, job_id: str):
        """
        Mark a failed job for retry
        
        Args:
            job_id: Job identifier
        """
        from datetime import timedelta
        
        data = self._load_queue()
        
        if job_id not in data['jobs']:
            raise ValueError(f"Job {job_id} not found")
        
        job = data['jobs'][job_id]
        
        # Check retry count
        retry_count = job.get('retry_count', 0)
        if retry_count >= settings.MAX_RETRY_ATTEMPTS:
            job['message'] = f'Job failed after {retry_count} retry attempts'
            self._save_queue(data)
            return
        
        # Reset job for retry
        job['status'] = JobStatus.QUEUED
        job['retry_count'] = retry_count + 1
        job['progress'] = 0
        job['message'] = f'Retrying (attempt {retry_count + 1}/{settings.MAX_RETRY_ATTEMPTS})...'
        job['error'] = None
        job['retry_at'] = (datetime.now() + timedelta(seconds=settings.RETRY_DELAY_SECONDS)).isoformat()
        
        # Add back to queue if not already there
        if job_id not in data['queue']:
            data['queue'].append(job_id)
        
        self._save_queue(data)
        print(f"Job {job_id} marked for retry (attempt {retry_count + 1})")
    
    def get_queue_position(self, job_id: str) -> int:
        """
        Get position of job in queue
        
        Args:
            job_id: Job identifier
            
        Returns:
            Position (0-indexed) or -1 if not found or not queued
        """
        queued_jobs = self.get_queued_jobs()
        for i, job in enumerate(queued_jobs):
            if job['id'] == job_id:
                return i
        return -1
    
    def cleanup_old_jobs(self, days: int = 7):
        """
        Remove completed/failed jobs older than specified days
        
        Args:
            days: Number of days to keep jobs
        """
        from datetime import timedelta
        
        data = self._load_queue()
        cutoff_date = datetime.now() - timedelta(days=days)
        
        jobs_to_remove = []
        
        for job_id, job in data['jobs'].items():
            if job['status'] in [JobStatus.COMPLETED, JobStatus.FAILED]:
                completed_at = job.get('completed_at')
                if completed_at:
                    job_date = datetime.fromisoformat(completed_at)
                    if job_date < cutoff_date:
                        jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del data['jobs'][job_id]
            if job_id in data['queue']:
                data['queue'].remove(job_id)
        
        self._save_queue(data)
        
        return len(jobs_to_remove)
