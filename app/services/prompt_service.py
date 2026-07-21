"""
Image Prompt Generator Module
Creates detailed image prompts from script using OpenAI GPT
"""
import json
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
            'Realistic Action Art': '2D comic book action illustration style, graphic novel artwork, bold black ink outlines, dynamic action poses, dramatic comic panel composition, vibrant saturated colors, cell shading, high-energy action motion effects, hand-drawn comic art, NOT a photo',
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openai_api_low_temp(self, system_prompt: str, user_content: str):
        """Call OpenAI with low temperature for deterministic outputs (identity extraction)"""
        return self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.3,
            max_tokens=1500
        )

    def _extract_visual_identities(self, script: str, style: str) -> Dict[str, str]:
        """
        Analyze the script to extract a Visual Identity Sheet — frozen, ultra-specific
        descriptions for every recurring visual element (characters, objects, environments).
        
        These anchors are injected verbatim into every image prompt so the image model
        receives identical specifications across all scenes.
        
        Args:
            script: The video script to analyze
            style: The visual style (used to tailor descriptions)
            
        Returns:
            Dictionary mapping element names to their frozen visual descriptors.
            Empty dict if extraction fails (graceful degradation).
        """
        if not self.client:
            print("OpenAI client not available for identity extraction, skipping.")
            return {}
        
        extraction_prompt = f"""You are a visual continuity supervisor for an AI image generation pipeline.
The target art style is "{style}". All descriptors you produce must use vocabulary and visual traits
appropriate for this style — do NOT default to photorealistic descriptions.

Analyze the script below and identify every recurring visual element (characters, key objects, environments)
that appears across multiple scenes. For each, produce a FROZEN VISUAL DESCRIPTOR — a self-contained
description that can be dropped into any image prompt to ensure the element looks identical every time.

Tailor your descriptors to the "{style}" style:
- For stylized art (anime, cartoon, comic, caricature, etc.): focus on silhouette, color scheme, distinctive
  features, costume design, hair style and color, proportions, and signature visual traits that define the
  character or object in that art style.
- For realistic art (hyper realistic, retro noir, etc.): focus on age, build, hair, clothing details,
  materials, textures, and lighting.
- For all styles: be specific about exact colors (not "blue" but "dark navy blue"), and include enough
  detail that the image model cannot misinterpret the appearance.

If the script has NO characters (nature, abstract, product, etc.), anchor environments, objects, and
color palettes instead.

If the same character appears in different forms or outfits, create separate entries but note they share
the same base appearance.

RULES:
1. Each descriptor must be fully self-contained — readable with zero context.
2. Only include elements that actually recur or are central to the script.
3. Include at least the primary environment or setting.
4. Do NOT add elements that are not in the script.

Return ONLY a valid JSON object where keys are element names and values are their frozen descriptors as strings."""

        try:
            print("Extracting visual identities from script...")
            response = self._call_openai_api_low_temp(extraction_prompt, f"Script: {script}")
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle possible markdown wrapping)
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            # Find JSON object boundaries
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                print("No valid JSON object found in identity extraction response.")
                return {}
            
            identities = json.loads(content[start_idx:end_idx])
            
            print(f"✓ Extracted {len(identities)} visual identities:")
            for name, desc in identities.items():
                print(f"  • {name}: {desc[:80]}...")
            
            return identities
            
        except Exception as e:
            print(f"Visual identity extraction failed (graceful degradation): {e}")
            return {}

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
            
            # Create comprehensive negative prompt that excludes text and unwanted media types
            text_exclusions = "text, letters, words, writing, typography, captions, subtitles, labels, signs, banners, written language, alphabet, numbers, symbols"
            quality_exclusions = "blurry, low quality, distorted, watermark, logo, signature, jpeg artifacts, pixelated, grainy"
            
            # Style-specific negative exclusions
            style_exclusions = ""
            if style in ['Realistic Action Art', 'Comic Noir', 'B&W Sketch', 'Anime', 'Warm Fable', 'Medieval Painting', 'Caricature']:
                style_exclusions = ", photorealistic, real life photograph, photography, realistic 3d render, live action photo"
            
            if negative_keywords:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}{style_exclusions}, {negative_keywords}"
            else:
                negative_prompt_base = f"{text_exclusions}, {quality_exclusions}{style_exclusions}"
            
            if keywords:
                keywords_instruction = f"CRITICAL: You MUST prominently feature these exact keywords as the main central subject in EVERY single prompt: '{keywords}'. The entire scene must be built around them."
            else:
                keywords_instruction = "Use vivid, descriptive language"
            
            # Create style-specific instructions
            style_guide = self._get_style_guide(style)
            
            # --- Visual Identity Anchoring ---
            # Extract frozen visual descriptors for recurring elements to ensure
            # cross-scene consistency. This is a pre-pass that produces a reference
            # sheet injected into the main prompt generation call.
            visual_identities = self._extract_visual_identities(script, style)
            
            # Build the identity reference block for the system prompt
            identity_block = ""
            if visual_identities:
                identity_lines = []
                for name, descriptor in visual_identities.items():
                    identity_lines.append(f'  • {name}: {descriptor}')
                identity_sheet = '\n'.join(identity_lines)
                identity_block = f"""\n\n=== VISUAL IDENTITY REFERENCE SHEET ===
The following are FROZEN visual descriptions for recurring elements in this script.
When an element from this sheet NATURALLY APPEARS in a scene based on the script,
you MUST use its EXACT description verbatim — do NOT modify, abbreviate, or
reinterpret any detail. Copy-paste the full descriptor into your prompt.

IMPORTANT: Only include an element in a prompt if the SCRIPT calls for it in that
specific scene. Do NOT force elements into scenes where they do not belong.
A scene may have no characters, only environments, or only objects — that is fine.

{identity_sheet}

These descriptors are for CONSISTENCY, not for forcing inclusion. Use them only
when the script places that element in that scene.
=== END REFERENCE SHEET ==="""
            
            style_prefix_str = "In 2D comic book graphic novel illustration style: " if style == 'Realistic Action Art' else f"In {style} style: "

            system_prompt = f"""You are an expert at creating detailed image prompts for AI image generation.
Your task is to create exactly {image_count} unique image prompts based on the provided script.

CRITICAL - STYLE ENFORCEMENT:
ALL prompts MUST strictly adhere to the "{style}" style.
{style_guide}
{identity_block}

Requirements:
1. Each prompt MUST START with: "{style_prefix_str}" to enforce style consistency
2. Each prompt should represent a key scene or moment from the script
3. {keywords_instruction}
4. Make prompts detailed and vivid (2-3 sentences)
5. IMPORTANT: Do NOT include any text, letters, words, or writing in the scene descriptions
6. Focus on visual elements: people, objects, landscapes, atmosphere, lighting, colors
7. Maintain consistent visual style across all {image_count} prompts
8. For negative prompts, always include: {negative_prompt_base}
9. CRITICAL CONTEXT RULE: The image AI has NO memory. Each prompt must be fully self-contained. Only describe what ACTUALLY APPEARS in that specific scene according to the script. If a character is not in a scene, do NOT include them.
10. NO PRONOUNS: NEVER use pronouns (it, he, they, she). When a character or object from the Reference Sheet appears in a scene, use their full frozen descriptor instead of pronouns or vague references.
11. MANDATORY FORMAT: Every prompt must follow this structure exactly: "{style_prefix_str}[Setting/environment]. [What is happening — only include characters/objects that the script places in this scene]. [Lighting/Atmosphere/Style details]."

Return ONLY a JSON array with this exact format:
[
    {{
        "prompt": "{style_prefix_str}[Setting and characters using frozen descriptors]. [Specific scene action]. [Style elements], no text",
        "negative_prompt": "{negative_prompt_base}"
    }},
    ...
]
"""
            
            print(f"Generating {image_count} image prompts...")
            
            # Call OpenAI API
            response = self._call_openai_api(system_prompt, script)
            
            # Parse response
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
            return self._generate_default_prompts(script, style, keywords, image_count)
    
    def _generate_default_prompts(self, script: str, style: str, keywords: str = '', image_count: int = None) -> List[Dict[str, str]]:
        """Generate simple default prompts as fallback"""
        if image_count is None:
            image_count = self._calculate_image_count(script)
        
        style_guide = self._get_style_guide(style)
        words = script.split()
        chunk_size = max(1, len(words) // image_count)
        
        # Try to extract a very basic context from the first few words (up to 20 words)
        context = " ".join(words[:20]).strip()
        
        prompts = []
        for i in range(image_count):
            start = i * chunk_size
            end = start + chunk_size if i < image_count - 1 else len(words)
            chunk = ' '.join(words[start:end])
            
            style_prefix_str = "In 2D comic book graphic novel illustration style: " if style == 'Realistic Action Art' else f"In {style} style: "
            style_exclusions = ", photorealistic, real life photograph, photography, realistic 3d render, live action photo" if style in ['Realistic Action Art', 'Comic Noir', 'B&W Sketch', 'Anime', 'Warm Fable', 'Medieval Painting', 'Caricature'] else ""
            
            prompt_text = f"{style_prefix_str}A scene featuring: {context}... In this specific moment: {chunk[:100]}. {style_guide}. No text, no letters, no words."
            if keywords:
                prompt_text = f"Main focus: {keywords}. " + prompt_text
                
            prompts.append({
                "prompt": prompt_text,
                "negative_prompt": f"text, letters, words, writing, typography, captions, subtitles, labels, signs, blurry, low quality, distorted, ugly, bad anatomy, watermark{style_exclusions}"
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
