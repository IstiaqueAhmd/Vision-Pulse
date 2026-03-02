"""
Image Generator Module
Generates images using Google Gemini Nano Banana (primary) and OpenAI DALL-E (fallback)
"""
from openai import OpenAI
from google import genai
import requests
from pathlib import Path
from typing import List, Dict
from app.core.config import settings
import time
import os


class ImageGenerator:
    """Generate images using Gemini Nano Banana (primary) and DALL-E (fallback)"""
    
    def __init__(self):
        """Initialize the image generator"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        
        # Initialize Gemini with new API
        self.gemini_key = settings.GEMINI_API_KEY
        if self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
    
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
                
                # Try Gemini first
                if self.gemini_key:
                    try:
                        print(f"Attempting generation with Gemini...")
                        image_path = self._generate_with_gemini(prompt_dict, i, size)
                        if image_path:
                            print(f"Image {i} generated with Gemini")
                    except Exception as gemini_error:
                        print(f"Gemini failed: {gemini_error}, falling back to DALL-E...")
                
                # Fallback to DALL-E if Gemini failed or not configured
                if not image_path:
                    print(f"Generating with OpenAI DALL-E...")
                    image_path = self._generate_with_dalle(prompt_dict, i, size)
                    if image_path:
                        print(f"Image {i} generated with DALL-E")
                
                if image_path:
                    image_paths.append(image_path)
                    print(f"Image {i} saved to {image_path}")
                else:
                    raise Exception("Both Gemini and DALL-E failed")
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                print(f"Error generating image {i}: {e}")
                # Create a placeholder image
                image_path = self._create_placeholder(i, video_format)
                image_paths.append(image_path)
        
        return image_paths
    
    def _generate_with_gemini(self, prompt_dict: Dict[str, str], index: int, size: str) -> Path:
        """Generate image using Google Gemini Nano Banana"""
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
                    # Save image with unique timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    image_path = settings.IMAGES_DIR / f"image_{index:03d}_{timestamp}.png"
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Get image as PIL Image and save
                    image = part.as_image()
                    image.save(image_path)
                    
                    return image_path
            
            print("No image data in Gemini response")
            return None
            
        except Exception as e:
            print(f"Gemini Nano Banana generation error: {e}")
            return None
    
    def _get_aspect_ratio(self, size: str) -> str:
        """Convert DALL-E size to Gemini aspect ratio"""
        if size == "1024x1792":
            return "9:16"  # Vertical
        elif size == "1792x1024":
            return "16:9"  # Horizontal
        else:
            return "1:1"   # Square
    
    def _generate_with_dalle(self, prompt_dict: Dict[str, str], index: int, size: str) -> Path:
        """Generate image using OpenAI DALL-E"""
        try:
            # Prepare prompt with explicit no-text instruction
            prompt = prompt_dict['prompt']
            negative_prompt = prompt_dict.get('negative_prompt', '')
            
            # Enhance prompt to exclude text - DALL-E doesn't support negative prompts
            enhanced_prompt = f"Create a visual scene with NO TEXT, NO LETTERS, NO WORDS, NO WRITING: {prompt}"
            if negative_prompt:
                enhanced_prompt += f". Avoid: {negative_prompt}"
            
            # Generate image using DALL-E
            response = self.client.images.generate(
                prompt=enhanced_prompt[:4000],  # DALL-E has 4000 char limit
                n=1,
                size=size,
                quality="standard",
                model="dall-e-3"
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
            print(f"DALL-E generation error: {e}")
            return None
    
    def _get_image_size(self, video_format: str) -> str:
        """Get DALL-E image size based on video format"""
        # DALL-E 3 only supports 1024x1024, 1792x1024, 1024x1792
        if video_format == '9:16':
            return "1024x1792"  # Vertical
        elif video_format == '16:9':
            return "1792x1024"  # Horizontal
        else:  # 1:1
            return "1024x1024"  # Square
    
    def _create_placeholder(self, index: int, video_format: str) -> Path:
        """Create a placeholder image when generation fails"""
        from PIL import Image, ImageDraw, ImageFont
        
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
        
        # Save with unique timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        image_path = settings.IMAGES_DIR / f"placeholder_{index:03d}_{timestamp}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(image_path)
        
        return image_path
