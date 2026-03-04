"""
Image-to-Video Generator Service
Uses Google Gemini Veo 3.1 to convert images into short video clips.
"""
import time
from pathlib import Path
from PIL import Image
from google import genai
from app.core.config import settings
from datetime import datetime


class ImageToVideoGenerator:
    """Generate video clips from images using Gemini Veo 3.1"""

    def __init__(self):
        """Initialize with Gemini client"""
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_video_from_image(
        self, image_path: Path, prompt: str, output_dir: Path = None
    ) -> Path:
        """
        Convert a static image into a short video clip using Veo 3.1.

        Args:
            image_path: Path to the source image
            prompt: Text prompt to guide the video generation
            output_dir: Directory to save the output video (defaults to TEMP_DIR)

        Returns:
            Path to the generated video clip (.mp4)
        """
        if output_dir is None:
            output_dir = settings.TEMP_DIR / "video_clips"
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            print(f"  🎬 Converting image to video: {image_path.name}")
            print(f"     Prompt: {prompt[:80]}...")

            # Load the image
            image = Image.open(str(image_path))

            # Call Veo 3.1 image-to-video
            operation = self.client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
                image=image,
                config={
                    "number_of_videos": 1,
                    "duration_seconds": 8,
                    "negative_prompt": "text, watermark, letters, words, writing, blurry, distorted",
                },
            )

            # Poll until done
            print("     Waiting for Veo video generation...")
            poll_count = 0
            while not operation.done:
                time.sleep(10)
                operation = self.client.operations.get(operation)
                poll_count += 1
                if poll_count % 3 == 0:
                    print(f"     Still generating... ({poll_count * 10}s elapsed)")

            # Download and save
            video = operation.response.generated_videos[0]
            self.client.files.download(file=video.video)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            output_path = output_dir / f"veo_clip_{timestamp}.mp4"
            video.video.save(str(output_path))

            print(f"  ✓ Video clip generated: {output_path}")
            return output_path

        except Exception as e:
            print(f"  ✗ Veo video generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
