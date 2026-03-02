"""
Subtitle Generator Module
Generates intelligent, timed subtitles using AI
"""
import openai
from app.core.config import settings
from typing import List, Dict
import json
import re


class SubtitleGenerator:
    """Generate AI-powered subtitles with intelligent text segmentation"""
    
    def __init__(self):
        """Initialize the subtitle generator"""
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
    
    def generate_subtitle_segments(self, script: str, audio_duration: float, 
                                   num_images: int = 7) -> List[Dict]:
        """
        Generate subtitle segments using AI for intelligent text breaking
        
        Args:
            script: The full video script
            audio_duration: Total duration of the audio in seconds
            num_images: Number of images/scenes in the video
            
        Returns:
            List of subtitle dictionaries with 'text', 'start_time', 'end_time'
        """
        try:
            # Use AI to intelligently segment the script
            segments = self._ai_segment_script(script, num_images)
            
            # Calculate timing for each segment
            timed_segments = self._calculate_timings(segments, audio_duration)
            
            return timed_segments
            
        except Exception as e:
            print(f"AI subtitle generation failed: {e}")
            # Fallback to simple word-based segmentation
            return self._fallback_segmentation(script, audio_duration)
    
    def _ai_segment_script(self, script: str, num_scenes: int) -> List[str]:
        """
        Use OpenAI to intelligently break script into subtitle segments
        
        Args:
            script: The full script text
            num_scenes: Number of scenes/images in the video
            
        Returns:
            List of text segments optimized for subtitles
        """
        prompt = f"""Break this video script into subtitle segments. 
Each segment should:
- Be 1-2 short sentences (5-12 words each)
- Match natural speaking rhythm and pauses
- Be readable on screen (not too long)
- Cover ALL text from the script (don't skip anything)
- End at natural break points

IMPORTANT: Include EVERY word from the script - do not omit any text.

Script:
{script}

Return ONLY a JSON array of strings (no extra text):
["segment 1", "segment 2", ...]"""

        try:
            response = openai.chat.completions.create(
                model=settings.SUBTITLE_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert video subtitle creator. Create concise, readable subtitle segments that match natural speech patterns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON array from response
            # Handle cases where AI adds markdown code blocks
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            content = content.strip()
            
            segments = json.loads(content)
            
            # Validate segments
            if isinstance(segments, list) and len(segments) > 0:
                print(f"AI generated {len(segments)} subtitle segments")
                return segments
            else:
                raise ValueError("Invalid segment format from AI")
                
        except Exception as e:
            print(f"AI segmentation error: {e}")
            # Fallback to sentence-based segmentation
            return self._sentence_segmentation(script, num_scenes)
    
    def _sentence_segmentation(self, script: str, target_segments: int) -> List[str]:
        """
        Fallback: Split script into sentences
        
        Args:
            script: The script text
            target_segments: Desired number of segments
            
        Returns:
            List of text segments
        """
        # Split by sentences
        sentences = re.split(r'[.!?]+', script)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # If we have roughly the right number, use them
        if len(sentences) >= target_segments * 0.7:
            return sentences
        
        # Otherwise, split longer sentences
        segments = []
        for sentence in sentences:
            words = sentence.split()
            if len(words) > 15:
                # Split long sentences at natural breaks (commas, conjunctions)
                parts = re.split(r',\s*|\s+and\s+|\s+but\s+|\s+or\s+', sentence)
                segments.extend([p.strip() for p in parts if p.strip()])
            else:
                segments.append(sentence)
        
        return segments if segments else [script]
    
    def _calculate_timings(self, segments: List[str], 
                           total_duration: float) -> List[Dict]:
        """
        Calculate start and end times for each subtitle segment
        
        Args:
            segments: List of text segments
            total_duration: Total audio duration in seconds
            
        Returns:
            List of dictionaries with 'text', 'start_time', 'end_time'
        """
        if not segments:
            return []
        
        timed_segments = []
        
        # Calculate word count for each segment
        word_counts = [len(segment.split()) for segment in segments]
        total_words = sum(word_counts)
        
        # Allocate time proportionally based on word count
        current_time = 0.0
        
        for i, (segment, word_count) in enumerate(zip(segments, word_counts)):
            # Calculate duration based on word proportion
            # Average speaking rate: 150-160 words per minute
            duration = (word_count / total_words) * total_duration
            
            # Minimum subtitle duration: 0.8 seconds
            # Maximum subtitle duration: 5 seconds
            duration = max(0.8, min(5.0, duration))
            
            end_time = min(current_time + duration, total_duration)
            
            timed_segments.append({
                'text': segment.strip(),
                'start_time': round(current_time, 2),
                'end_time': round(end_time, 2)
            })
            
            current_time = end_time
        
        # Adjust last segment to match total duration exactly
        if timed_segments:
            timed_segments[-1]['end_time'] = total_duration
        
        return timed_segments
    
    def _fallback_segmentation(self, script: str, 
                               audio_duration: float) -> List[Dict]:
        """
        Simple word-based segmentation fallback
        
        Args:
            script: The script text
            audio_duration: Total audio duration
            
        Returns:
            List of timed subtitle segments
        """
        words = script.split()
        
        # Create segments of 4-8 words each
        segments = []
        for i in range(0, len(words), 6):
            segment_words = words[i:i+6]
            segments.append(' '.join(segment_words))
        
        return self._calculate_timings(segments, audio_duration)
    
    def export_srt(self, segments: List[Dict], output_path: str) -> str:
        """
        Export subtitles in SRT format
        
        Args:
            segments: List of subtitle segments
            output_path: Path to save SRT file
            
        Returns:
            Path to the saved SRT file
        """
        srt_content = []
        
        for i, segment in enumerate(segments, 1):
            start_time = self._format_srt_time(segment['start_time'])
            end_time = self._format_srt_time(segment['end_time'])
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(segment['text'])
            srt_content.append("")  # Blank line between subtitles
        
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        
        print(f"SRT file saved to {output_path}")
        return output_path
    
    def _format_srt_time(self, seconds: float) -> str:
        """
        Format time in SRT format: HH:MM:SS,mmm
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


if __name__ == "__main__":
    # Test the subtitle generator
    generator = SubtitleGenerator()
    test_script = "Welcome to our amazing video. Today we'll explore the wonders of AI technology. Machine learning is transforming how we create content. With powerful tools, anyone can become a creator. The future of video production is here. Let's dive into this exciting journey together. Thank you for watching!"
    
    segments = generator.generate_subtitle_segments(test_script, 45.0, 7)
    
    print("\nGenerated Subtitle Segments:")
    print("=" * 60)
    for i, seg in enumerate(segments, 1):
        print(f"{i}. [{seg['start_time']:.2f}s - {seg['end_time']:.2f}s] {seg['text']}")
