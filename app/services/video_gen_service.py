"""
Image-to-Video Generator Service
Uses OpenAI Sora 2 to convert images into short video clips.
"""
from pathlib import Path
from PIL import Image
from openai import OpenAI
from app.core.config import settings
from datetime import datetime


class ImageToVideoGenerator:
    """Generate video clips from images using OpenAI Sora 2"""

    SUPPORTED_SORA2_SIZES = ((720, 1280), (1280, 720))

    def __init__(self):
        """Initialize with OpenAI client"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    def _pick_sora_size(self, width: int, height: int, video_format: str | None = None) -> tuple[int, int]:
        """Pick Sora 2 supported resolution, preferring requested output format."""
        if video_format == "16:9":
            return 1280, 720
        if video_format == "9:16":
            return 720, 1280
        if video_format == "1:1":
            strategy = settings.VIDEO_GEN_SQUARE_STRATEGY.lower()
            if strategy == "portrait":
                return 720, 1280
            if strategy == "auto":
                return (720, 1280) if height >= width else (1280, 720)
            return 1280, 720

        # For unknown formats, pick the closest orientation-based option.
        source_ratio = width / height
        if height >= width:
            candidates = [size for size in self.SUPPORTED_SORA2_SIZES if size[1] > size[0]]
        else:
            candidates = [size for size in self.SUPPORTED_SORA2_SIZES if size[0] > size[1]]

        # Fallback is defensive in case orientation filtering returns an empty list.
        if not candidates:
            candidates = list(self.SUPPORTED_SORA2_SIZES)
        return min(candidates, key=lambda size: abs((size[0] / size[1]) - source_ratio))

    def _prepare_reference_image(self, image_path: Path, video_format: str | None = None) -> tuple[Path, str]:
        """Resize and crop the reference image to a Sora-supported width/height pair."""
        with Image.open(image_path) as image:
            target_width, target_height = self._pick_sora_size(*image.size, video_format=video_format)
            scale = max(target_width / image.width, target_height / image.height)
            resized_width = int(round(image.width * scale))
            resized_height = int(round(image.height * scale))

            resampling = getattr(Image, "Resampling", Image).LANCZOS
            resized = image.resize((resized_width, resized_height), resampling)

            left = max(0, (resized_width - target_width) // 2)
            top = max(0, (resized_height - target_height) // 2)
            cropped = resized.crop((left, top, left + target_width, top + target_height))

            if cropped.mode not in ("RGB", "RGBA"):
                cropped = cropped.convert("RGB")

            ref_dir = settings.TEMP_DIR / "sora_references"
            ref_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            prepared_path = ref_dir / f"sora_ref_{timestamp}.png"
            cropped.save(prepared_path, format="PNG")

        return prepared_path, f"{target_width}x{target_height}"

    def generate_video_from_image(
        self,
        image_path: Path,
        prompt: str,
        output_dir: Path = None,
        video_format: str | None = None,
    ) -> Path:
        """
        Convert a static image into a short video clip using Sora 2.

        Args:
            image_path: Path to the source image
            prompt: Text prompt to guide the video generation
            output_dir: Directory to save the output video (defaults to TEMP_DIR)
            video_format: Target output format (9:16, 16:9, 1:1)

        Returns:
            Path to the generated video clip (.mp4)
        """
        if output_dir is None:
            output_dir = settings.TEMP_DIR / "video_clips"
        output_dir.mkdir(parents=True, exist_ok=True)
        prepared_image_path = None

        try:
            if self.client is None:
                print("  ✗ Sora 2 video generation failed: OPENAI_API_KEY is not configured")
                return None

            print(f"  🎬 Converting image to video: {image_path.name}")
            print(f"     Prompt: {prompt[:80]}...")

            print("     Waiting for Sora 2 video generation...")
            prepared_image_path, size_param = self._prepare_reference_image(
                image_path,
                video_format=video_format,
            )
            with open(prepared_image_path, "rb") as image_file:
                video = self.client.videos.create_and_poll(
                    model=settings.VIDEO_GEN_MODEL,
                    prompt=prompt,
                    input_reference=image_file,
                    seconds=str(settings.VIDEO_GEN_SECONDS),
                    size=size_param,
                )

            if video.status != "completed":
                error_msg = video.error.message if video.error else "unknown error"
                print(f"  ✗ Sora 2 video generation failed: {error_msg}")
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            output_path = output_dir / f"sora2_clip_{timestamp}.mp4"

            content = self.client.videos.download_content(video.id)
            content.write_to_file(output_path)

            print(f"  ✓ Video clip generated: {output_path}")
            return output_path

        except Exception as e:
            print(f"  ✗ Sora 2 video generation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if prepared_image_path and prepared_image_path.exists():
                prepared_image_path.unlink()
