"""
Narration Generator Module
Handles text-to-speech conversion using ElevenLabs API with OpenAI TTS fallback
"""
import os
import openai
from pathlib import Path
from elevenlabs.client import ElevenLabs
from app.core.config import settings
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

class NarrationGenerator:
    """Generate narration audio from text using ElevenLabs with OpenAI TTS fallback"""
    
    def __init__(self):
        """Initialize the narration generator"""
        if not settings.ELEVENLABS_API_KEY:
            print("⚠️ Warning: ElevenLabs API key not found, will use OpenAI TTS only")
        else:
            self.elevenlabs_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
        
        # Initialize OpenAI if available
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            self.openai_available = True
        else:
            self.openai_available = False
            
        self.voices = settings.VOICE_TYPES
    
    def generate_narration(self, script: str, voice_name: str = 'Cassidy') -> Path:
        """
        Generate narration from script using ElevenLabs with OpenAI TTS fallback
        
        Args:
            script: The text to convert to speech
            voice_name: Name of the voice to use (default: Cassidy)
            
        Returns:
            Path to the generated audio file
        """
        # Try ElevenLabs first if available
        if settings.ELEVENLABS_API_KEY:
            try:
                return self._generate_with_elevenlabs(script, voice_name)
            except Exception as e:
                error_msg = str(e)
                print(f"\n⚠️ ElevenLabs Error: {error_msg}")
                
                # Check if it's a voice limit error
                if 'voice_limit_reached' in error_msg or 'custom voices' in error_msg:
                    print("❌ ElevenLabs voice limit reached!")
                elif 'quota' in error_msg.lower() or 'limit' in error_msg.lower():
                    print("❌ ElevenLabs quota/limit exceeded!")
                else:
                    print(f"❌ ElevenLabs API error: {error_msg[:200]}")
                
                # Fall back to OpenAI TTS
                if self.openai_available:
                    print("🔄 Falling back to OpenAI TTS...")
                    return self._generate_with_openai(script, voice_name)
                else:
                    raise Exception("ElevenLabs failed and OpenAI TTS not available. Please check API keys.")
        
        # Use OpenAI directly if ElevenLabs not configured
        elif self.openai_available:
            print("ℹ️ Using OpenAI TTS (ElevenLabs not configured)")
            return self._generate_with_openai(script, voice_name)
        else:
            raise Exception("No TTS service available. Configure ElevenLabs or OpenAI API key.")
    
    def _generate_with_elevenlabs(self, script: str, voice_input: str) -> Path:
        """Generate narration using ElevenLabs"""
        print(f"\n{'='*60}")
        print(f"VOICE SELECTION DEBUG")
        print(f"{'='*60}")
        print(f"Requested voice input: '{voice_input}'")
        print(f"Voice input type: {type(voice_input)}")
        print(f"Available voices in config: {list(self.voices.keys())}")
        
        # Check if input is already a voice ID (20 characters alphanumeric)
        voice_input_stripped = voice_input.strip()
        if len(voice_input_stripped) == 20 and voice_input_stripped.replace('_', '').replace('-', '').isalnum():
            # Input appears to be a voice ID - use it directly
            voice_id = voice_input_stripped
            # Try to find the voice name from the ID
            voice_name = None
            for name, vid in self.voices.items():
                if vid == voice_id:
                    voice_name = name
                    break
            if not voice_name:
                voice_name = "Custom"
            print(f"✓ Direct voice ID detected: {voice_id}")
            print(f"  Matched to voice name: {voice_name}")
        else:
            # Input is a voice name - look it up
            voice_name_original = voice_input
            voice_name_lower = voice_input_stripped.lower()
            
            # Try exact match first
            if voice_input in self.voices:
                voice_id = self.voices[voice_input]
                voice_name = voice_input
                print(f"✓ Exact match found for '{voice_input}'")
            else:
                # Try case-insensitive match
                matched = False
                for key in self.voices.keys():
                    if key.lower() == voice_name_lower:
                        voice_name = key
                        voice_id = self.voices[key]
                        matched = True
                        print(f"✓ Case-insensitive match: '{voice_name_original}' → '{key}'")
                        break
                
                if not matched:
                    print(f"❌ WARNING: Voice '{voice_name_original}' not found in config!")
                    print(f"Available voices: {list(self.voices.keys())}")
                    # Use Cassidy as fallback (known to work)
                    voice_name = 'Cassidy'
                    voice_id = self.voices[voice_name]
                    print(f"Using fallback voice: {voice_name}")
        
        # Verify voice ID format (ElevenLabs IDs are 20 characters)
        if not voice_id or len(voice_id) != 20:
            raise ValueError(f"Invalid voice ID for {voice_name}: {voice_id}")
        
        # Log final selection
        print(f"\nFINAL VOICE SELECTION:")
        print(f"  Voice Name: {voice_name}")
        print(f"  Voice ID: {voice_id}")
        print(f"  Script length: {len(script)} characters")
        print(f"  Model: eleven_turbo_v2_5")
        print(f"{'='*60}\n")
        
        # Use the correct ElevenLabs API method with turbo v2.5 for better quality
        audio = self.elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=script,
            model_id="eleven_turbo_v2_5"
        )
        
        # Save audio file with unique timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        output_path = settings.AUDIO_DIR / f"narration_{voice_name}_{timestamp}_elevenlabs.mp3"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert generator to bytes and save
        with open(output_path, 'wb') as f:
            for chunk in audio:
                f.write(chunk)
        
        print(f"✓ Narration saved to {output_path}")
        return output_path
    
    def get_available_voices(self) -> list:
        """Get list of available voice names"""
        return list(self.voices.keys())
    
    def _generate_with_openai(self, script: str, voice_name: str) -> Path:
        """Generate narration using OpenAI TTS as fallback"""
        # Map voice names to OpenAI voices (6 available: alloy, echo, fable, onyx, nova, shimmer)
        # Map based on gender and characteristics
        openai_voice_map = {
            # Female voices
            'Hope': 'nova',
            'Cassidy': 'shimmer',
            'Lana': 'nova',
            'Amelia': 'shimmer',
            'Jane': 'nova',
            
            # Male voices
            'Brian': 'onyx',
            'Peter': 'echo',
            'Adam': 'echo',
            'Alex': 'fable',
            'Finn': 'onyx',
            'Edward': 'fable',
            'Archie': 'onyx'
        }
        
        openai_voice = openai_voice_map.get(voice_name, 'nova')
        
        print(f"\n{'='*60}")
        print(f"OPENAI TTS GENERATION")
        print(f"{'='*60}")
        print(f"Voice Name: {voice_name}")
        print(f"OpenAI Voice: {openai_voice}")
        print(f"Script length: {len(script)} characters")
        print(f"{'='*60}\n")
        
        try:
            response = openai.audio.speech.create(
                model="tts-1-hd",  # Use HD model for better quality
                voice=openai_voice,
                input=script
            )
            
            # Save audio file with unique timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            output_path = settings.AUDIO_DIR / f"narration_{voice_name}_{timestamp}_openai.mp3"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            response.stream_to_file(str(output_path))
            
            print(f"✓ OpenAI narration saved to {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ OpenAI TTS Error: {e}")
            raise


if __name__ == "__main__":
    # Test the narration generator
    generator = NarrationGenerator()
    test_script = "This is a test narration. ClipForge can generate amazing videos with AI."
    audio_path = generator.generate_narration(test_script)
    print(f"Test narration generated: {audio_path}")
