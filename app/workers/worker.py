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
    
    def process_job(self, job: dict):
        """
        Process a single video generation job
        
        Args:
            job: Job dictionary
        """
        job_id = job['id']
        
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
            
            # Mark as completed
            self.queue.update_job(job_id, {
                'status': JobStatus.COMPLETED,
                'progress': 100,
                'message': 'Video generation complete!',
                'completed_at': datetime.now().isoformat(),
                'result': result
            })
            
            print(f"\n✓ Job {job_id} completed successfully!\n")
            
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
            try:
                self.queue.mark_job_for_retry(job_id)
            except Exception as retry_error:
                print(f"Could not schedule retry: {retry_error}")
    
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
    
    def stop(self):
        """Stop the worker"""
        self.running = False


if __name__ == '__main__':
    """
    Run worker from command line
    """
    worker = VideoWorker()
    worker.run()
