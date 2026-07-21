"""
Image Prompt Generator Module
Creates detailed image prompts from script using OpenAI GPT
"""
from openai import OpenAI
from app.core.config import settings
from typing import List, Dict
import time
from tenacity import retry, stop_after_attempt, wait_exponential


class ImagePromptGenerator:
    """Generate image prompts from script using AI"""
    
    def __init__(self):
        """Initialize the prompt generator"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _extract_character_bible(self, script: str) -> str:
        """
        Phase 1: Extract a Character Bible from the script.
        
        Analyzes the story to produce locked-down visual descriptions for every
        character and recurring visual element. This bible is then injected
        verbatim into every scene prompt to ensure the image AI generates
        visually consistent characters across all images.
        
        Returns:
            A plain-text character bible string ready to embed in scene prompts.
        """
        system_prompt = """You are a visual character designer for AI image generation.
Your job is to analyze a story script and produce a CHARACTER BIBLE — a locked set of
detailed, concrete visual descriptions for every character and recurring visual element.

Rules:
1. For EACH character, provide:
   - Full name (and any aliases/alter-egos)
   - Exact age (pick a specific number, e.g. "35 years old")
   - Ethnicity and skin tone
   - Hair: color, length, style
   - Face: specific features (eye color, facial hair, scars, glasses, etc.)
   - Body type: build, height impression
   - Outfit(s): describe EACH distinct outfit the character wears in the story
     (e.g. civilian clothes vs. superhero suit). Be extremely specific about
     colors, materials, logos, accessories.
2. For RECURRING VISUAL ELEMENTS (vehicles, locations, objects that appear in
   multiple scenes), provide a brief locked description.
3. Be EXTREMELY specific. Say "dark navy-blue skintight suit with a silver
   gravity-wave emblem on the chest" NOT "blue superhero suit".
4. Do NOT add backstory or personality traits — only VISUAL details.
5. Keep each character description to 2-4 sentences per appearance/outfit.

Return your response in this EXACT plain-text format:

=== CHARACTER BIBLE ===

CHARACTER: [Name] (alias: [Alias if any])
- Base appearance: [age, ethnicity, skin tone, hair, face, body type]
- Outfit 1 ([context, e.g. "as janitor"]): [detailed outfit description]
- Outfit 2 ([context, e.g. "as Graviton"]): [detailed outfit description]

CHARACTER: [Next character...]

RECURRING ELEMENTS:
- [Element name]: [visual description]

=== END CHARACTER BIBLE ==="""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract the character bible from this script:\n\n{script}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            bible = response.choices[0].message.content.strip()
            print(f"Character Bible extracted:\n{bible}")
            return bible
            
        except Exception as e:
            print(f"Error extracting character bible: {e}")
            return ""
    
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
            'Realistic Action Art': 'Dynamic action comic book art style, bold ink lines, dramatic poses, cinematic panel composition, vibrant colors, high-energy motion effects, detailed comic shading, graphic novel aesthetic',
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openai_api(self, system_prompt: str, script: str):
        return self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Script: {script}"}
            ],
            temperature=0.8,
            max_tokens=2000
        )

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
            
            # Phase 1: Extract Character Bible for visual consistency
            character_bible = ""
            if self.client:
                character_bible = self._extract_character_bible(script)
            
            # Create comprehensive negative prompt that excludes text
            text_exclusions = "text, letters, words, writing, typography, captions, subtitles, labels, signs, banners, written language, alphabet, numbers, symbols"
            quality_exclusions = "blurry, low quality, distorted, watermark, logo, signature, jpeg artifacts, pixelated, grainy"
            
            if negative_keywords:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}, {negative_keywords}"
            else:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}"
            
            if keywords:
                keywords_instruction = f"CRITICAL: You MUST prominently feature these exact keywords as the main central subject in EVERY single prompt: '{keywords}'. The entire scene must be built around them."
            else:
                keywords_instruction = "Use vivid, descriptive language"
            
            # Create style-specific instructions
            style_guide = self._get_style_guide(style)
            
            # Build character bible section for the system prompt
            if character_bible:
                bible_section = f"""\n\nCHARACTER REFERENCE (use ONLY when a character appears in the scene):
The following Character Bible contains locked visual descriptions. When a character
appears in a scene, use their EXACT details (age, hair, build, outfit) from this bible
in ONE concise sentence. Do NOT paste the entire bible — summarize the relevant
character's look in a single sentence using the bible's specific details.
If a scene has NO characters (e.g. a landscape, an object, an empty room), do NOT
mention any character at all.

{character_bible}"""
            else:
                bible_section = ""
            
            system_prompt = f"""You are an expert at creating detailed image prompts for AI image generation.
Your task is to create exactly {image_count} unique image prompts based on the provided script.

HIGHEST PRIORITY - ART STYLE:
The visual art style is the MOST important aspect of every prompt.
Style: "{style}" — {style_guide}
Every prompt MUST begin with "In {style} style: " and end with style-reinforcing keywords.
The art style must dominate the final image. Character details are secondary to style.
{bible_section}

Requirements:
1. Each prompt MUST START with: "In {style} style: " and MUST END with: ", {style_guide}, no text"
2. Each prompt should represent a key scene or moment from the script
3. {keywords_instruction}
4. Make prompts detailed and vivid (2-3 sentences between the style bookends)
5. IMPORTANT: Do NOT include any text, letters, words, or writing in the scene descriptions
6. Focus on visual elements: people, objects, landscapes, atmosphere, lighting, colors
7. Maintain consistent visual style across all {image_count} prompts
8. For negative prompts, always include: {negative_prompt_base}
9. CHARACTER RULES:
   a. NOT every scene needs a character. Establishing shots, landscapes, object close-ups, and atmospheric scenes should describe ONLY the environment.
   b. When a character IS in the scene, describe them in ONE sentence using the EXACT details from the Character Bible (same age, hair, build, outfit every time).
   c. When a character is NOT in the scene, do NOT force their description in.
   d. NO PRONOUNS: Never use "he", "she", "they", "it". Use the character's name.
10. CONSISTENCY: If a character appears in multiple prompts, their physical description must use the same details every time (from the Character Bible).
11. PROMPT FORMAT: "In {{style}} style: [1-sentence character description IF character is present]. [Scene action and setting]. [Mood/atmosphere], {style_guide}, no text"

Return ONLY a JSON array with this exact format:
[
    {{
        "prompt": "In {style} style: [scene description]. [action], {style_guide}, no text",
        "negative_prompt": "{negative_prompt_base}"
    }},
    ...
]
"""
            
            print(f"Generating {image_count} image prompts...")
            
            # Call OpenAI API
            response = self._call_openai_api(system_prompt, script)
            
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
            
            # Strengthen keyword weighting by explicitly prepending to final prompt
            if keywords:
                for p in prompts:
                    p['prompt'] = f"Main focus: {keywords}. " + p['prompt']
            
            print(f"Generated {len(prompts)} image prompts")
            return prompts
            
        except Exception as e:
            print(f"Error generating prompts: {e}")
            # Return default prompts as fallback
            return self._generate_default_prompts(script, style, keywords, image_count, character_bible)
    
    def _generate_default_prompts(self, script: str, style: str, keywords: str = '', 
                                   image_count: int = None, character_bible: str = '') -> List[Dict[str, str]]:
        """Generate simple default prompts as fallback, with optional character bible for consistency"""
        if image_count is None:
            image_count = self._calculate_image_count(script)
        
        style_guide = self._get_style_guide(style)
        words = script.split()
        chunk_size = max(1, len(words) // image_count)
        
        # Use character bible if available, otherwise fall back to basic context
        if character_bible:
            context = character_bible
        else:
            context = "A scene featuring: " + " ".join(words[:20]).strip() + "..."
        
        prompts = []
        for i in range(image_count):
            start = i * chunk_size
            end = start + chunk_size if i < image_count - 1 else len(words)
            chunk = ' '.join(words[start:end])
            
            prompt_text = f"In {style} style: {context} In this specific moment: {chunk[:100]}. {style_guide}. No text, no letters, no words."
            if keywords:
                prompt_text = f"Main focus: {keywords}. " + prompt_text
                
            prompts.append({
                "prompt": prompt_text,
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
