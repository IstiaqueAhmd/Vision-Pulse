"""
Image Generator Module
Generates images using OpenAI GPT Image 2 (primary) and Google Gemini (fallback)
"""
from openai import OpenAI
import requests
from pathlib import Path
from typing import List, Dict
from app.core.config import settings
import time
import os
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from google import genai
except ImportError:
    genai = None


class ImageGenerator:
    """Generate images using OpenAI GPT Image 2 (primary) and Gemini (fallback)"""
    
    def __init__(self):
        """Initialize the image generator"""
        # Initialize OpenAI as primary
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        
        # Initialize Gemini as fallback
        self.gemini_key = settings.GEMINI_API_KEY
        self.gemini_client = None
        
        if self.gemini_key and genai is not None:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        elif self.gemini_key and genai is None:
            print("Gemini SDK not installed; will not be able to use Gemini as fallback.")

    def generate_images(self, prompts: List[Dict[str, str]], 
                       video_format: str = '16:9') -> List[Path]:
        """
        Generate images from prompts
        
        Args:
            prompts: List of prompt dictionaries
            video_format: Video aspect ratio (9:16, 16:9, 1:1)
            
        Returns:
            List of paths to generated images
        """
        image_paths = []
        
        # Determine image size based on format
        size = self._get_image_size(video_format)
        
        print(f"Generating {len(prompts)} images at {size} resolution...")
        
        for i, prompt_dict in enumerate(prompts, 1):
            try:
                print(f"Generating image {i}/{len(prompts)}...")
                image_path = None
                
                # Try OpenAI (GPT Image 2) first
                if self.openai_client:
                    try:
                        print(f"Attempting generation with GPT Image 2...")
                        image_path = self._generate_with_openai(prompt_dict, i, size)
                        if image_path:
                            print(f"Image {i} generated with GPT Image 2")
                    except Exception as openai_error:
                        print(f"OpenAI failed: {openai_error}, falling back to Gemini...")
                
                # Fallback to Gemini if OpenAI failed or not configured
                if not image_path and self.gemini_client:
                    print(f"Generating with Google Gemini...")
                    image_path = self._generate_with_gemini(prompt_dict, i, size)
                    if image_path:
                        print(f"Image {i} generated with Gemini")
                
                if image_path:
                    image_paths.append(image_path)
                    print(f"Image {i} saved to {image_path}")
                else:
                    raise Exception("Both OpenAI and Gemini failed")
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                print(f"Error generating image {i}: {e}")
                # Create a placeholder image
                image_path = self._create_placeholder(i, video_format)
                image_paths.append(image_path)
        
        return image_paths

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _generate_with_openai(self, prompt_dict: Dict[str, str], index: int, size: str) -> Path:
        """Generate image using OpenAI GPT Image 2"""
        try:
            # Prepare prompt with explicit no-text instruction
            prompt = prompt_dict['prompt']
            negative_prompt = prompt_dict.get('negative_prompt', '')
            
            # Enhance prompt to exclude text
            enhanced_prompt = f"Create a visual scene with NO TEXT, NO LETTERS, NO WORDS, NO WRITING: {prompt}"
            if negative_prompt:
                enhanced_prompt += f". Avoid: {negative_prompt}"
            
            # Generate image using GPT Image 2
            response = self.openai_client.images.generate(
                prompt=enhanced_prompt[:4000],  # OpenAI has a 4000 char limit
                n=1,
                size=size,
                quality="standard",
                model="gpt-image-2"
            )
            
            # Get image URL
            image_url = response.data[0].url
            
            # Download image
            image_data = requests.get(image_url).content
            
            # Save image with unique timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            image_path = settings.IMAGES_DIR / f"image_{index:03d}_{timestamp}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            return image_path
            
        except Exception as e:
            print(f"GPT Image 2 generation error: {e}")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _generate_with_gemini(self, prompt_dict: Dict[str, str], index: int, size: str) -> Path:
        """Generate image using Google Gemini"""
        try:
            # Build full prompt with negative keywords incorporated
            full_prompt = prompt_dict['prompt']
            negative_prompt = prompt_dict.get('negative_prompt', '')
            
            # Add explicit "no text" instruction at the start
            full_prompt = f"Create an image with absolutely NO TEXT, NO LETTERS, NO WORDS, NO WRITING of any kind. {full_prompt}"
            
            # Incorporate negative keywords into main prompt
            if negative_prompt:
                full_prompt += f". Strictly avoid: {negative_prompt}"
            
            # Add unique variation seed to ensure different images each time
            unique_seed = prompt_dict.get('_seed', '')
            if unique_seed:
                full_prompt += f" [Variation: {unique_seed}]"
            
            # Use Nano Banana (gemini-2.5-flash-image) for fast image generation
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash-image',
                contents=full_prompt
            )
            
            # Extract image from response
            for part in response.parts:
                if part.inline_data:
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    image_path = settings.IMAGES_DIR / f"image_{index:03d}_{timestamp}.png"
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    image = part.as_image()
                    image.save(image_path)
                    
                    return image_path
            
            print("No image data in Gemini response")
            return None
            
        except Exception as e:
            print(f"Gemini generation error: {e}")
            return None

    def _get_image_size(self, video_format: str) -> str:
        """Get OpenAI image size based on video format"""
        if video_format == '9:16':
            return "1024x1792"  # Vertical
        elif video_format == '16:9':
            return "1792x1024"  # Horizontal
        else:  # 1:1
            return "1024x1024"  # Square

    def _create_placeholder(self, index: int, video_format: str) -> Path:
        """Create a placeholder image when generation fails"""
        from PIL import Image, ImageDraw
        
        width, height = settings.VIDEO_FORMATS[video_format]
        
        # Create a simple colored image
        img = Image.new('RGB', (width, height), color=(50, 50, 100))
        draw = ImageDraw.Draw(img)
        
        # Add text
        text = f"Image {index}"
        bbox = draw.textbbox((0, 0), text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill=(255, 255, 255))
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        image_path = settings.IMAGES_DIR / f"placeholder_{index:03d}_{timestamp}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(image_path)
        
        return image_path