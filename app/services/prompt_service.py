"""
Image Prompt Generator Module
Creates detailed image prompts from script using OpenAI GPT
"""
from openai import OpenAI
from app.core.config import settings
from typing import List, Dict
import time


class ImagePromptGenerator:
    """Generate image prompts from script using AI"""
    
    def __init__(self):
        """Initialize the prompt generator"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    
    def _calculate_image_count(self, script: str) -> int:
        """Calculate optimal number of images based on script length"""
        word_count = len(script.split())
        
        # Calculate based on script length:
        # Short (0-100 words): 3-5 images
        # Medium (100-300 words): 5-7 images
        # Long (300-500 words): 7-10 images
        # Very long (500+ words): 10-12 images
        
        if word_count < 100:
            return max(3, min(5, word_count // 20 + 2))
        elif word_count < 300:
            return max(5, min(7, word_count // 40 + 3))
        elif word_count < 500:
            return max(7, min(10, word_count // 50 + 4))
        else:
            return max(10, min(12, word_count // 60 + 5))
    
    def _get_style_guide(self, style: str) -> str:
        """Get detailed style-specific guidance for image generation"""
        style_guides = {
            'Realistic Action Art': 'Photorealistic, dramatic action scenes, cinematic lighting, intense motion, detailed textures, film-like quality',
            'B&W Sketch': 'Black and white pencil sketch, hand-drawn lines, shading with crosshatching, artistic sketch marks, no color',
            'Comic Noir': 'Dark noir comic book style, high contrast black/white/gray, dramatic shadows, bold ink lines, vintage detective aesthetic',
            'Retro Noir': 'Vintage 1940s-50s noir film aesthetic, grain texture, chiaroscuro lighting, moody atmosphere, sepia or desaturated tones',
            'Medieval Painting': 'Classical medieval illuminated manuscript style, rich colors, gold leaf accents, religious art influence, flat perspective',
            'Anime': 'Japanese anime style, vibrant colors, expressive eyes, clean cel-shaded look, dynamic poses, manga influence',
            'Warm Fable': 'Storybook illustration, warm color palette, soft textures, whimsical details, fairy tale atmosphere, gentle lighting',
            'Hyper Realistic': 'Ultra-photorealistic, extreme detail, perfect lighting, professional photography quality, sharp focus, lifelike textures',
            '3D Cartoon': 'Pixar-style 3D animation, smooth surfaces, vibrant colors, exaggerated features, playful character design, bounce lighting',
            'Caricature': 'Exaggerated features, humorous proportions, bold outlines, vibrant colors, expressive cartoon style, satirical art'
        }
        return style_guides.get(style, f'Strictly maintain {style} visual style throughout all images with consistent artistic approach')
    
    def generate_prompts(self, script: str, style: str = 'Modern Abstract', 
                        keywords: str = '', negative_keywords: str = '') -> List[Dict[str, str]]:
        """
        Generate image prompts from script
        
        Args:
            script: The video script
            style: Visual style for images
            keywords: Additional keywords to include
            negative_keywords: Keywords to avoid in images
            
        Returns:
            List of dictionaries containing prompts and negative prompts
        """
        try:
            # Calculate dynamic image count based on script length
            image_count = self._calculate_image_count(script)
            print(f"Script has {len(script.split())} words, generating {image_count} images")
            
            # Create comprehensive negative prompt that excludes text
            text_exclusions = "text, letters, words, writing, typography, captions, subtitles, labels, signs, banners, written language, alphabet, numbers, symbols"
            quality_exclusions = "blurry, low quality, distorted, watermark, logo, signature, jpeg artifacts, pixelated, grainy"
            
            if negative_keywords:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}, {negative_keywords}"
            else:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}"
            
            keywords_instruction = f"Include these keywords: {keywords}" if keywords else "Use vivid, descriptive language"
            
            # Create style-specific instructions
            style_guide = self._get_style_guide(style)
            
            system_prompt = f"""You are an expert at creating detailed image prompts for AI image generation.
Your task is to create exactly {image_count} unique image prompts based on the provided script.

CRITICAL - STYLE ENFORCEMENT:
ALL prompts MUST strictly adhere to the "{style}" style.
{style_guide}

Requirements:
1. Each prompt MUST START with: "In {style} style: " to enforce style consistency
2. Each prompt should represent a key scene or moment from the script
3. {keywords_instruction}
4. Make prompts detailed and vivid (2-3 sentences)
5. IMPORTANT: Do NOT include any text, letters, words, or writing in the scene descriptions
6. Focus on visual elements: people, objects, landscapes, atmosphere, lighting, colors
7. Maintain consistent visual style across all {image_count} prompts
8. For negative prompts, always include: {negative_prompt_base}

Return ONLY a JSON array with this exact format:
[
    {{
        "prompt": "In {style} style: detailed scene description with style-specific elements, no text, no letters",
        "negative_prompt": "{negative_prompt_base}"
    }},
    ...
]
"""
            
            print(f"Generating {image_count} image prompts...")
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Script: {script}"}
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            # Parse response
            import json
            content = response.choices[0].message.content
            
            # Extract JSON from response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            json_str = content[start_idx:end_idx]
            
            prompts = json.loads(json_str)
            
            # Ensure we have exactly the right number of prompts
            if len(prompts) < image_count:
                # Duplicate some prompts if needed
                while len(prompts) < image_count:
                    prompts.append(prompts[-1])
            elif len(prompts) > image_count:
                prompts = prompts[:image_count]
            
            print(f"Generated {len(prompts)} image prompts")
            return prompts
            
        except Exception as e:
            print(f"Error generating prompts: {e}")
            # Return default prompts as fallback
            return self._generate_default_prompts(script, style, image_count)
    
    def _generate_default_prompts(self, script: str, style: str, image_count: int = None) -> List[Dict[str, str]]:
        """Generate simple default prompts as fallback"""
        if image_count is None:
            image_count = self._calculate_image_count(script)
        
        style_guide = self._get_style_guide(style)
        words = script.split()
        chunk_size = max(1, len(words) // image_count)
        
        prompts = []
        for i in range(image_count):
            start = i * chunk_size
            end = start + chunk_size if i < image_count - 1 else len(words)
            chunk = ' '.join(words[start:end])
            
            prompts.append({
                "prompt": f"In {style} style: {chunk[:100]}. {style_guide}. No text, no letters, no words.",
                "negative_prompt": "text, letters, words, writing, typography, captions, subtitles, labels, signs, blurry, low quality, distorted, ugly, bad anatomy, watermark"
            })
        
        return prompts


if __name__ == "__main__":
    # Test the prompt generator
    generator = ImagePromptGenerator()
    test_script = "A journey through ancient Egypt. The pyramids stand tall under the desert sun. Pharaohs ruled with wisdom and power."
    prompts = generator.generate_prompts(test_script, style="Comic Book", keywords="ancient, historical")
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nPrompt {i}:")
        print(f"  Prompt: {prompt['prompt']}")
        print(f"  Negative: {prompt['negative_prompt']}")
