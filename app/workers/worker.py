"""
Background Worker for Video Generation
Processes jobs from the queue in the background
"""
import time
import sys
from datetime import datetime
from pathlib import Path
from app.workers.job_queue import JobQueue, JobStatus
from app.workers.pipeline import VideoGeneratorPipeline
import traceback
import uuid
from app.db.session import SessionLocal
from app.models.logs import Logs
from app.models.notification import Notification
from app.models.user import User
from app.models.credit import CreditTransaction


class VideoWorker:
    """
    Background worker that processes video generation jobs
    """
    
    def __init__(self, check_interval: int = 2):
        """
        Initialize worker
        
        Args:
            check_interval: Seconds between queue checks
        """
        self.queue = JobQueue()
        self.pipeline = VideoGeneratorPipeline()
        self.check_interval = check_interval
        self.running = False
        
        # Reset any stuck processing jobs from previous runs
        self._reset_stuck_jobs()
        
    def _reset_stuck_jobs(self):
        """Reset jobs stuck in processing state from previous worker runs"""
        try:
            processing_jobs = self.queue.get_processing_jobs()
            for job in processing_jobs:
                job_id = job.get('id')
                if job_id:
                    print(f"Resetting stuck job {job_id} to FAILED")
                    self.queue.update_job(job_id, {
                        'status': JobStatus.FAILED,
                        'message': 'Job failed due to worker restart',
                        'completed_at': datetime.now().isoformat(),
                        'error': 'Worker was interrupted during processing'
                    })
        except Exception as e:
            print(f"Failed to reset stuck jobs: {e}")
    
    def process_job(self, job: dict):
        """
        Process a single video generation job
        
        Args:
            job: Job dictionary
        """
        job_id = job['id']
        user_id = job.get('video_data', {}).get('user_id')
        
        try:
            print(f"\n{'='*60}")
            print(f"Processing Job: {job_id}")
            print(f"Title: {job['video_data'].get('title', 'Untitled')}")
            print(f"{'='*60}\n")
            
            # Mark as processing
            self.queue.update_job(job_id, {
                'status': JobStatus.PROCESSING,
                'progress': 5,
                'message': 'Starting video generation...',
                'started_at': datetime.now().isoformat()
            })
            
            # Update progress - narration
            self.queue.update_job(job_id, {
                'progress': 15,
                'message': 'Generating narration...'
            })
            
            # Generate video using pipeline
            result = self.pipeline.generate_video(job['video_data'])
            
            self.queue.update_job(job_id, {
                'status': JobStatus.COMPLETED,
                'progress': 100,
                'message': 'Video generation complete!',
                'completed_at': datetime.now().isoformat(),
                'result': result
            })
            
            print(f"\n✓ Job {job_id} completed successfully!\n")
            
            # Save success log if user_id is present
            if user_id:
                try:
                    self._save_video_log(user_id, "success")
                except Exception as log_err:
                    print(f"Failed to save success log: {log_err}")
                try:
                    self._create_video_completion_notification(user_id, job_id, result)
                except Exception as notify_err:
                    print(f"Failed to create completion notification: {notify_err}")
            
            
        except Exception as e:
            error_message = str(e)
            error_trace = traceback.format_exc()
            
            print(f"\n✗ Job {job_id} failed!")
            print(f"Error: {error_message}")
            print(f"Trace:\n{error_trace}\n")
            
            # Mark as failed
            self.queue.update_job(job_id, {
                'status': JobStatus.FAILED,
                'message': f'Error: {error_message}',
                'completed_at': datetime.now().isoformat(),
                'error': error_trace
            })

            # Attempt retry if possible
            will_retry = False
            try:
                will_retry = self.queue.mark_job_for_retry(job_id)
            except Exception as retry_error:
                print(f"Could not schedule retry: {retry_error}")

            # Save failure log and refund only if no retry is happening
            if user_id and not will_retry:
                try:
                    self._save_video_log(user_id, "failed")
                except Exception as log_err:
                    print(f"Failed to save failed log: {log_err}")

                # Refund credits
                try:
                    credit_cost = job.get('video_data', {}).get('credit_cost', 0)
                    if credit_cost > 0:
                        self._refund_credits(user_id, job_id, credit_cost)
                except Exception as refund_err:
                    print(f"Failed to refund credits: {refund_err}")
    
    def run(self):
        """
        Main worker loop
        Continuously checks for and processes jobs
        """
        self.running = True
        
        print(f"\n{'='*60}")
        print("Video Generation Worker Started")
        print(f"Checking queue every {self.check_interval} seconds")
        print("Press Ctrl+C to stop")
        print(f"{'='*60}\n")
        
        try:
            while self.running:
                # Get next job
                job = self.queue.get_next_job()
                
                if job:
                    self.process_job(job)
                else:
                    # No jobs available, wait
                    time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\nWorker stopped by user\n")
            self.running = False
        except Exception as e:
            print(f"\n\nWorker error: {e}")
            print(traceback.format_exc())
            self.running = False
            
    def _save_video_log(self, user_id: int, status: str):
        """
        Save a log entry for video generation.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                # Generate a 6-character unique ID
                unique_hash = uuid.uuid4().hex[:6].upper()
                ref_id = f"VID - {unique_hash}"
                log_entry = Logs(
                    name=user.name,
                    email=user.email,
                    action_type="Video Generation",
                    reference_id=ref_id,
                    status=status
                )
                db.add(log_entry)
                db.commit()
        finally:
            db.close()

    def _create_video_completion_notification(self, user_id: int, job_id: str, result: dict):
        """Create an in-app notification when a job finishes successfully."""
        db = SessionLocal()
        try:
            video_id = result.get("id") if isinstance(result, dict) else None
            title = result.get("title", "Untitled") if isinstance(result, dict) else "Untitled"

            notification = Notification(
                user_id=user_id,
                title="Video Generation Complete",
                message=f"Your video '{title}' is ready.",
                type="video_completed",
                video_id=video_id,
                job_id=job_id,
                is_read=False,
            )
            db.add(notification)
            db.commit()
        finally:
            db.close()
            
    def _refund_credits(self, user_id: int, job_id: str, amount: int):
        """Refund credits to the user after a failed video generation."""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.credits += amount
                db.add(CreditTransaction(
                    user_id=user.id,
                    amount=amount,
                    type="refund",
                    source="video_generation_failure",
                    reference_id=job_id,
                ))
                db.commit()
                print(f"Refunded {amount} credits to user {user_id} for failed job {job_id}")
        except Exception as e:
            print(f"Error refunding credits for job {job_id}: {str(e)}")
        finally:
            db.close()
    
    def stop(self):
        """Stop the worker"""
        self.running = False


if __name__ == '__main__':
    """
    Run worker from command line
    """
    worker = VideoWorker()
    worker.run()
