"""
Video Generator Pipeline
Main orchestrator for the complete video generation process
"""
from pathlib import Path
from typing import Dict
import json
from datetime import datetime
from app.services.narration_service import NarrationGenerator
from app.services.prompt_service import ImagePromptGenerator
from app.services.image_service import ImageGenerator
from app.services.video_composer import VideoComposer
from app.db.videodb import VideoDatabase

class VideoGeneratorPipeline:
    """
    Main pipeline for video generation
    Implements the 6-step process:
    1. Generate narration using voice selection
    2. Create 7 image prompts
    3. Call API for all image prompts
    4. Combine images and narration in sequence
    5. Randomly zoom and pan images in video
    6. Add final video to "All Videos List"
    """
    
    def __init__(self):
        """Initialize all components"""
        self.narration_gen = NarrationGenerator()
        self.prompt_gen = ImagePromptGenerator()
        self.image_gen = ImageGenerator()
        self.video_composer = VideoComposer()
        self.db = VideoDatabase()
    
    def generate_video(self, video_data: Dict) -> Dict:
        """
        Generate complete video from input data
        
        Args:
            video_data: Dictionary containing:
                - title: Video title
                - category: Video category
                - format: Video format (9:16, 16:9, 1:1)
                - style: Visual style
                - voice: Voice type
                - script: Video script
                
        Returns:
            Dictionary with video metadata and path
        """
        try:
            title = video_data.get('title', 'Untitled Video')
            category = video_data.get('category', 'General')
            video_format = video_data.get('format', '16:9')
            style = video_data.get('style', 'Modern Abstract')
            voice = video_data.get('voice', 'Bella')
            script = video_data.get('script', '')
            keywords = video_data.get('keywords', '')
            negative_keywords = video_data.get('negative_keywords', '')
            user_id = video_data.get('user_id')  # supplied by the authenticated endpoint
            
            print(f"\n{'='*60}")
            print(f"STARTING VIDEO GENERATION: {title}")
            print(f"{'='*60}\n")
            
            # STEP 1: Generate narration
            print("STEP 1: Generating narration...")
            print(f"  Requested voice: '{voice}'")
            print(f"  Voice type: {type(voice)}")
            audio_path = self.narration_gen.generate_narration(script, voice)
            print(f"✓ Narration complete\n")
            
            # STEP 2: Create image prompts
            print("STEP 2: Creating image prompts...")
            prompts = self.prompt_gen.generate_prompts(script, style, keywords, negative_keywords)
            
            # Add unique seed to each prompt for variation
            generation_seed = video_data.get('_generation_seed', '')
            if generation_seed:
                for prompt in prompts:
                    prompt['_seed'] = generation_seed
            
            print(f"✓ Generated {len(prompts)} prompts\n")
            
            # STEP 3: Generate images
            print("STEP 3: Generating images from prompts...")
            image_paths = self.image_gen.generate_images(prompts, video_format)
            print(f"✓ Generated {len(image_paths)} images\n")
            
            # STEP 4 & 5: Combine images and narration with zoom/pan effects
            print("STEP 4-5: Composing video with effects and AI subtitles...")
            # Extract unique_id from video_data to ensure unique filenames
            unique_id = video_data.get('_unique_id', None)
            video_path = self.video_composer.create_video(
                image_paths, audio_path, video_format, title, script, unique_id
            )
            print(f"✓ Video composed successfully with AI-powered subtitles\n")
            
            # Verify video file exists
            if not video_path.exists():
                raise Exception(f"Video file not found after generation: {video_path}")
            
            print(f"✓ Video file verified at: {video_path}")
            print(f"✓ File size: {video_path.stat().st_size / (1024*1024):.2f} MB")
            
            # STEP 6: Save to database
            print("STEP 6: Saving to database...")
            video_metadata = {
                'user_id': user_id,
                'title': title,
                'category': category,
                'format': video_format,
                'style': style,
                'voice': voice,
                'script': script,
                'keywords': keywords,
                'negative_keywords': negative_keywords,
                'path': str(video_path),
                'created_at': datetime.now().isoformat(),
                'duration': self._get_video_duration(audio_path),
                'status': 'completed'
            }
            
            # Check if this is an update job
            update_video_id = video_data.get('_update_video_id')
            if update_video_id:
                # Update existing video
                print(f"Updating existing video ID: {update_video_id}")
                
                # Get old video to delete old file
                old_video = self.db.get_video(update_video_id)
                if old_video:
                    old_path = Path(old_video['path'])
                    if old_path.exists() and old_path != video_path:
                        old_path.unlink()
                        print(f"✓ Deleted old video file: {old_path}")
                
                # Update database record
                self.db.update_video(update_video_id, video_metadata)
                video_metadata['id'] = update_video_id
                print(f"✓ Updated database record (ID: {update_video_id})\n")
            else:
                # Create new video
                video_id = self.db.add_video(video_metadata)
                video_metadata['id'] = video_id
                print(f"✓ Saved to database (ID: {video_id})\n")
            
            print(f"{'='*60}")
            print(f"VIDEO GENERATION COMPLETE!")
            print(f"Output: {video_path}")
            print(f"{'='*60}\n")
            
            return video_metadata
            
        except Exception as e:
            print(f"\n✗ Error in video generation pipeline: {e}")
            raise
    
    def get_all_videos(self) -> list:
        """Get all videos from database"""
        return self.db.get_all_videos()
    
    def _get_video_duration(self, audio_path: Path) -> float:
        """Get duration of audio file"""
        try:
            from moviepy import AudioClip
            audio = AudioClip(str(audio_path))
            duration = audio.duration
            audio.close()
            return duration
        except:
            return 0.0


if __name__ == "__main__":
    # Test the pipeline
    pipeline = VideoGeneratorPipeline()
    
    test_data = {
        'title': 'Test Video',
        'category': 'Test',
        'format': '16:9',
        'style': 'Modern Abstract',
        'voice': 'Bella',
        'script': 'This is a test video script. It will be converted into an amazing video with AI.'
    }
    
    result = pipeline.generate_video(test_data)
    print(f"Generated video: {result}")
