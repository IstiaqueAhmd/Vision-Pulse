"""
Video Composer Module
Combines images and narration into a video with effects
"""
from pathlib import Path
from typing import List, Dict
import random
from moviepy import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip, TextClip, CompositeAudioClip
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import textwrap
import math
from app.services.subtitle_service import SubtitleGenerator
from app.core.config import settings

class VideoComposer:
    """Compose final video from images and audio"""
    
    def __init__(self):
        """Initialize the video composer"""
        self.fps = settings.DEFAULT_FPS
        self.subtitle_gen = SubtitleGenerator()
    
    def _make_zoom_in_effect(self, duration):
        """Create smooth zoom in effect function with subtle, controlled motion"""
        def effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]
            
            # Calculate zoom factor with smooth easing (1.0 to 1.15) - subtle and controlled
            progress = t / duration
            # Apply quintic ease-in-out for ultra smooth cinematic motion (smoother than quartic)
            if progress < 0.5:
                eased_progress = 16 * progress * progress * progress * progress * progress
            else:
                eased_progress = 1 - pow(-2 * progress + 2, 5) / 2
            
            # Use configurable zoom intensity (default 15% vs old 35%)
            zoom_intensity = settings.CAMERA_ZOOM_INTENSITY
            zoom = 1.0 + (eased_progress * zoom_intensity)
            
            # Calculate crop coordinates for zoom
            new_h, new_w = int(h / zoom), int(w / zoom)
            y1, x1 = (h - new_h) // 2, (w - new_w) // 2
            y2, x2 = y1 + new_h, x1 + new_w
            
            # Crop and resize back with high quality
            cropped = frame[y1:y2, x1:x2]
            img = Image.fromarray(cropped)
            img_resized = img.resize((w, h), Image.Resampling.LANCZOS)
            return np.array(img_resized)
        return effect
    
    def _make_zoom_out_effect(self, duration):
        """Create smooth zoom out effect function with subtle, controlled motion"""
        def effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]
            
            # Calculate zoom factor (1.15 to 1.0) with smooth easing - subtle and controlled
            progress = t / duration
            # Apply quintic ease-in-out for ultra smooth cinematic motion (smoother than quartic)
            if progress < 0.5:
                eased_progress = 16 * progress * progress * progress * progress * progress
            else:
                eased_progress = 1 - pow(-2 * progress + 2, 5) / 2
            
            # Use configurable zoom intensity (default 15% vs old 35%)
            zoom_intensity = settings.CAMERA_ZOOM_INTENSITY
            zoom = (1.0 + zoom_intensity) - (eased_progress * zoom_intensity)
            
            # Calculate crop coordinates for zoom
            new_h, new_w = int(h / zoom), int(w / zoom)
            y1, x1 = (h - new_h) // 2, (w - new_w) // 2
            y2, x2 = y1 + new_h, x1 + new_w
            
            # Crop and resize back with high quality
            cropped = frame[y1:y2, x1:x2]
            img = Image.fromarray(cropped)
            img_resized = img.resize((w, h), Image.Resampling.LANCZOS)
            return np.array(img_resized)
        return effect
    
    def _make_pan_effect(self, duration, direction='horizontal'):
        """Create smooth pan effect with subject-aware motion
        
        Args:
            duration: Duration of the effect in seconds
            direction: 'horizontal', 'vertical', or 'diagonal'
        """
        def effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]
            
            # Slow pan with quintic easing for ultra-smooth cinematic motion
            progress = t / duration
            # Apply quintic ease-in-out (smoother than quartic)
            if progress < 0.5:
                eased_progress = 16 * progress * progress * progress * progress * progress
            else:
                eased_progress = 1 - pow(-2 * progress + 2, 5) / 2
            
            # Use configurable pan intensity (default 8% horizontal, 4% vertical)
            h_max = settings.CAMERA_PAN_HORIZONTAL_MAX
            v_max = settings.CAMERA_PAN_VERTICAL_MAX
            
            # Prefer horizontal pan (more natural for subjects)
            if direction == 'horizontal':
                h_shift = int(w * h_max * (eased_progress - 0.5))
                v_shift = 0
            elif direction == 'vertical':
                h_shift = 0
                v_shift = int(h * v_max * (eased_progress - 0.5))
            else:  # diagonal
                h_shift = int(w * h_max * (eased_progress - 0.5))
                v_shift = int(h * v_max * 0.5 * (eased_progress - 0.5))  # Less vertical
            
            # Apply horizontal pan
            if h_shift > 0:
                frame = np.pad(frame, ((0, 0), (h_shift, 0), (0, 0)), mode='edge')[:, :w]
            elif h_shift < 0:
                frame = np.pad(frame, ((0, 0), (0, -h_shift), (0, 0)), mode='edge')[:, -w:]
            
            # Apply vertical pan
            if v_shift > 0:
                frame = np.pad(frame, ((v_shift, 0), (0, 0), (0, 0)), mode='edge')[:h, :]
            elif v_shift < 0:
                frame = np.pad(frame, ((0, -v_shift), (0, 0), (0, 0)), mode='edge')[-h:, :]
            
            return frame
        return effect
    
    def _make_rotate_zoom_effect_DISABLED(self, duration):
        """DISABLED: Rotation effect - too jarring for most content"""
        # This effect is disabled by default for better user experience
        # Use slow pan or subtle zoom instead
        return self._make_zoom_in_effect(duration)
    
    def _make_rotate_zoom_effect(self, duration):
        """Create smooth rotate + zoom effect - RARELY USED (disabled by default)
        
        This effect is disabled in config by default (CAMERA_ENABLE_ROTATION=False)
        Only use for dramatic/action scenes when explicitly enabled
        """
        # Check if rotation is enabled in config
        if not settings.CAMERA_ENABLE_ROTATION:
            # Return subtle zoom instead
            return self._make_zoom_in_effect(duration)
        
        def effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]
            
            # Progress with quintic easing (smoother)
            progress = t / duration
            if progress < 0.5:
                eased = 16 * progress * progress * progress * progress * progress
            else:
                eased = 1 - pow(-2 * progress + 2, 5) / 2
            
            # Very subtle rotation (-1° to +1°) + minimal zoom (reduced from ±2° and 25%)
            angle = (eased - 0.5) * 2  # -1 to +1 degrees
            zoom_intensity = settings.CAMERA_ZOOM_INTENSITY
            zoom = 1.0 + (eased * zoom_intensity)
            
            # Use PIL for rotation and zoom
            img = Image.fromarray(frame)
            
            # Calculate new dimensions after zoom
            new_w, new_h = int(w * zoom), int(h * zoom)
            
            # Zoom first
            img_zoomed = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Rotate with expand to prevent cropping
            img_rotated = img_zoomed.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(0, 0, 0))
            
            # Crop back to original size (center crop)
            left = (img_rotated.width - w) // 2
            top = (img_rotated.height - h) // 2
            img_cropped = img_rotated.crop((left, top, left + w, top + h))
            
            return np.array(img_cropped)
        return effect
    
    def __init__(self):
        """Initialize the video composer"""
        self.fps = settings.DEFAULT_FPS
        self.subtitle_gen = SubtitleGenerator()
    
    def create_video(self, image_paths: List[Path], audio_path: Path,
                     video_format: str = '16:9', 
                     video_title: str = 'output',
                     script: str = '',
                     unique_id: str = None,
                     bg_music_path: Path = None,
                     video_scene_indices: set = None,
                     subtitle_id: int = None) -> Path:
        """
        Create video from images and audio with subtitles
        
        Args:
            image_paths: List of image file paths
            audio_path: Path to audio file
            video_format: Video aspect ratio (9:16, 16:9, 1:1)
            video_title: Title for output video file
            script: Script text for subtitles
            unique_id: Unique identifier to ensure filename uniqueness (optional)
            
        Returns:
            Path to the generated video
        """
        try:
            print(f"Creating video with {len(image_paths)} images...")
            
            # Load audio
            audio = AudioFileClip(str(audio_path))
            total_duration = audio.duration
            
            # Calculate duration per image
            duration_per_image = total_duration / len(image_paths)
            
            # Get video dimensions
            width, height = settings.VIDEO_FORMATS[video_format]
            
            # Create video clips with effects
            if video_scene_indices is None:
                video_scene_indices = set()
            
            clips = []
            for i, img_path in enumerate(image_paths):
                
                # Check if this scene is a video clip (from Veo)
                if i in video_scene_indices and str(img_path).endswith('.mp4'):
                    print(f"Processing video scene {i+1}/{len(image_paths)}...")
                    try:
                        vclip = VideoFileClip(str(img_path))
                        
                        # Resize to target dimensions
                        vclip = vclip.resized((width, height))
                        
                        # Trim or loop to match duration_per_image
                        if vclip.duration > duration_per_image:
                            vclip = vclip.subclipped(0, duration_per_image)
                        elif vclip.duration < duration_per_image:
                            from moviepy import concatenate_videoclips as concat_vc
                            loops = int(duration_per_image / vclip.duration) + 1
                            vclip = concat_vc([vclip] * loops).subclipped(0, duration_per_image)
                        
                        # Remove audio from the clip (narration is separate)
                        vclip = vclip.without_audio()
                        
                        clips.append(vclip)
                        continue
                    except Exception as e:
                        print(f"  Failed to load video scene {i}, falling back to image: {e}")
                
                # Standard image scene processing
                print(f"Processing image {i+1}/{len(image_paths)}...")
                
                # Load image using PIL
                img = Image.open(str(img_path))
                img_width, img_height = img.size
                
                # Calculate scaling to cover the entire frame (like CSS object-fit: cover)
                scale_x = width / img_width
                scale_y = height / img_height
                scale = max(scale_x, scale_y)
                
                # Calculate new dimensions after scaling
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                
                # Resize image with high quality
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Calculate center crop coordinates
                left = (new_width - width) // 2
                top = (new_height - height) // 2
                right = left + width
                bottom = top + height
                
                # Crop to exact target dimensions from center
                img_cropped = img_resized.crop((left, top, right, bottom))
                
                # Save processed image temporarily
                temp_img_path = settings.TEMP_DIR / f"temp_processed_{i}.png"
                temp_img_path.parent.mkdir(parents=True, exist_ok=True)
                img_cropped.save(temp_img_path)
                img.close()
                
                # Create image clip from processed image (already perfect size)
                clip = ImageClip(str(temp_img_path), duration=duration_per_image)
                
                # Apply zoom and pan effect (image is already centered and correct size)
                clip = self._apply_zoom_pan_effect(clip, width, height, duration_per_image, clip_index=i)
                
                clips.append(clip)
            
            # Concatenate all clips with smooth transitions
            print("Combining clips...")
            final_video = concatenate_videoclips(clips, method="compose")
            
            # Add AI-powered subtitles
            if script and settings.ENABLE_SUBTITLES and subtitle_id is not None and subtitle_id != 1:
                print("Generating AI-powered subtitles...")
                final_video = self._add_ai_subtitles(final_video, script, width, height, total_duration, len(image_paths), subtitle_id)
            
            # Set audio - use with_audio instead of set_audio for MoviePy 2.x
            
            # Mix Background Music
            final_audio = audio
            bg_audio = None
            if bg_music_path and bg_music_path.exists():
                try:
                    from moviepy import concatenate_audioclips
                    print(f"Mixing background music: {bg_music_path}")
                    bg_audio = AudioFileClip(str(bg_music_path))
                    
                    # Loop background music to match video duration
                    if bg_audio.duration < total_duration:
                        loops_needed = int(total_duration / bg_audio.duration) + 1
                        bg_audio = concatenate_audioclips([bg_audio] * loops_needed)
                    bg_audio = bg_audio.subclipped(0, total_duration)
                    
                    # Reduce volume based on config
                    try:
                        bg_audio = bg_audio.with_volume_scaled(settings.BACKGROUND_MUSIC_VOLUME)
                    except AttributeError:
                        try:
                            bg_audio = bg_audio.multiply_volume(settings.BACKGROUND_MUSIC_VOLUME)
                        except AttributeError:
                            bg_audio = bg_audio.volumex(settings.BACKGROUND_MUSIC_VOLUME)
                    
                    # Mix narration and background music
                    final_audio = CompositeAudioClip([audio, bg_audio])
                    print(f"✓ Background music mixed successfully")
                except Exception as e:
                    print(f"Failed to mix background music: {e}")
                    import traceback
                    traceback.print_exc()
            
            try:
                final_video = final_video.with_audio(final_audio)
            except AttributeError:
                # Fallback for different MoviePy versions
                final_video.audio = final_audio
            
            # Ensure video matches audio duration exactly
            try:
                final_video = final_video.with_duration(total_duration)
            except AttributeError:
                final_video = final_video.set_duration(total_duration)
            
            # Generate unique output path with timestamp and unique ID to avoid conflicts
            from slugify import slugify
            from datetime import datetime
            import uuid
            safe_title = slugify(video_title)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            # Add unique_id or generate new UUID to ensure absolute uniqueness
            unique_suffix = unique_id[:8] if unique_id else str(uuid.uuid4())[:8]
            output_path = settings.VIDEOS_DIR / f"{safe_title}_{timestamp}_{unique_suffix}.mp4"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write video file
            print(f"Rendering final video to {output_path}...")
            final_video.write_videofile(
                str(output_path),
                fps=self.fps,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile=str(settings.TEMP_DIR / 'temp_audio.m4a'),
                remove_temp=True,
                threads=4,
                preset='medium'
            )
            
            # Verify video was created
            if not output_path.exists():
                raise Exception(f"Video file was not created at {output_path}")
            
            file_size = output_path.stat().st_size
            print(f"✓ Video file created: {output_path}")
            print(f"✓ File size: {file_size / (1024*1024):.2f} MB")
            
            # Clean up clips and resources AFTER confirming file exists
            try:
                if bg_audio:
                    bg_audio.close()
            except:
                pass
            
            try:
                if final_audio != audio:
                    final_audio.close()
            except:
                pass
            
            try:
                audio.close()
            except:
                pass
            
            try:
                final_video.close()
            except:
                pass
            
            try:
                for clip in clips:
                    clip.close()
            except:
                pass
            
            print(f"Video created successfully: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error creating video: {e}")
            raise
    
    def _apply_zoom_pan_effect(self, clip, target_width: int, 
                               target_height: int, duration: float, clip_index: int = 0):
        """
        Apply dynamic zoom/pan effects to perfectly sized and centered clips
        Uses controlled pattern instead of pure randomness for better results
        
        Args:
            clip: The video clip (already at exact target dimensions)
            target_width: Target video width
            target_height: Target video height
            duration: Clip duration
            clip_index: Index of clip in sequence (for pattern-based selection)
            
        Returns:
            Modified clip with smooth animations
        """
        try:
            # Clip is already at perfect size (target_width x target_height)
            # No cropping needed - just apply effects
            
            # Subject-aware effect selection with controlled pattern
            # Prioritize slow pans over zooms for more professional look
            
            # Check if rotation is enabled (default: disabled)
            use_rotation = settings.CAMERA_ENABLE_ROTATION
            
            # Pattern: slow_pan_h, slow_zoom_in, slow_pan_h, slow_zoom_out (repeats)
            # Avoid rotation unless explicitly enabled
            effect_pattern = clip_index % 4
            
            if effect_pattern == 0:
                # Horizontal pan (most natural)
                effect = self._make_pan_effect(duration, direction='horizontal')
            elif effect_pattern == 1:
                # Subtle zoom in
                effect = self._make_zoom_in_effect(duration)
            elif effect_pattern == 2:
                # Horizontal pan opposite direction
                effect = self._make_pan_effect(duration, direction='horizontal')
            else:  # effect_pattern == 3
                # Subtle zoom out
                effect = self._make_zoom_out_effect(duration)
            
            # Minimal speed variation for smooth, consistent motion (0.99x to 1.01x)
            speed_factor = random.uniform(0.99, 1.01)
            
            # Apply the effect using transform
            animated_clip = clip.transform(effect)
            
            # Apply subtle speed variation
            try:
                if abs(speed_factor - 1.0) > 0.01:  # Only if meaningful difference
                    animated_clip = animated_clip.with_fps(self.fps * speed_factor)
            except:
                pass  # Skip speed variation if it fails
            
            return animated_clip
            
        except Exception as e:
            print(f"Error applying effect: {e}")
            return clip  # Return original clip if effect fails:
            print(f"Animation effect failed: {e}, using static crop")
            # Fallback: return cropped clip without animation
            try:
                cropped = clip.image_transform(crop_frame)
                return cropped
            except Exception as e2:
                print(f"Crop also failed: {e2}, returning original clip")
                return clip
    
    def _add_ai_subtitles(self, video_clip, script: str, width: int, 
                          height: int, duration: float, num_images: int, subtitle_id: int = None):
        """
        Add AI-generated subtitles to video with professional styling
        
        Args:
            video_clip: The video clip to add subtitles to
            script: The video script
            width: Video width
            height: Video height
            duration: Video duration
            num_images: Number of images/scenes
            
        Returns:
            Video clip with subtitles
        """
        try:
            # Generate subtitle segments using AI
            subtitle_segments = self.subtitle_gen.generate_subtitle_segments(
                script, duration, num_images
            )
            
            if not subtitle_segments:
                print("No subtitle segments generated")
                return video_clip
            
            # Export SRT file for reference
            srt_path = settings.TEMP_DIR / "subtitles.srt"
            self.subtitle_gen.export_srt(subtitle_segments, str(srt_path))
            
            # Create subtitle clips with professional styling
            subtitle_clips = []
            
            for segment in subtitle_segments:
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                duration_seg = end_time - start_time
                
                if duration_seg <= 0:
                    continue
                
                # Create subtitle clip with enhanced styling
                txt_clip = self._create_styled_subtitle(
                    text, width, height, duration_seg, start_time, subtitle_id
                )
                
                if txt_clip:
                    subtitle_clips.append(txt_clip)
            
            # Composite subtitles onto video
            if subtitle_clips:
                print(f"Adding {len(subtitle_clips)} subtitle segments to video...")
                video_with_subs = CompositeVideoClip([video_clip] + subtitle_clips)
                return video_with_subs
            else:
                print("No subtitle clips were created successfully, proceeding without subtitles...")
                return video_clip
                
        except Exception as e:
            print(f"Error adding AI subtitles: {e}")
            import traceback
            traceback.print_exc()
            return video_clip
    
    def _create_styled_subtitle(self, text: str, video_width: int, 
                                video_height: int, duration: float, 
                                start_time: float, subtitle_id: int = 1):
        """
        Create a professionally styled subtitle clip
        
        Args:
            text: Subtitle text
            video_width: Video width
            video_height: Video height
            duration: Subtitle duration
            start_time: When subtitle appears
            
        Returns:
            Styled TextClip or None
        """
        try:
            # Calculate font size based on video height
            font_size = int(video_height * settings.SUBTITLE_FONT_SIZE_RATIO)
            
            # Wrap text to fit screen width (80% of width)
            max_chars_per_line = int(video_width * 0.8 / (font_size * 0.6))
            wrapped_text = textwrap.fill(text, width=max_chars_per_line)
            
            subtitle_style = self.subtitle_gen.get_subtitle_style(subtitle_id)
            
            # Extract style with fallbacks from config
            font = subtitle_style.get("font", settings.SUBTITLE_FONT)
            color = subtitle_style.get("color", settings.SUBTITLE_COLOR)
            bg_color = subtitle_style.get("bg_color")
            stroke_color = subtitle_style.get("stroke_color", settings.SUBTITLE_STROKE_COLOR)       
            stroke_width = subtitle_style.get("stroke_width")
            stroke_width = settings.SUBTITLE_STROKE_WIDTH
            
            # Try creating text clip with label method (more compatible)
            try:
                txt_clip = TextClip(
                    text=wrapped_text,
                    font=font,
                    font_size=font_size,
                    color=color,
                    bg_color=bg_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    method='label',
                    size=(int(video_width * 0.9), None)
                )
            except Exception as e1:
                print(f"Label method failed: {e1}, trying caption method...")
                # Fallback to caption without font specification if it failed
                try:
                    txt_clip = TextClip(
                        text=wrapped_text,
                        font=font,
                        font_size=font_size,
                        color=color,
                        bg_color=bg_color,
                        stroke_color=stroke_color,
                        stroke_width=stroke_width,
                        method='caption',
                        size=(int(video_width * 0.9), None),
                        text_align='center'
                    )
                except Exception as e2:
                    print(f"Caption method failed: {e2}")
                    return None
            
            if txt_clip is None:
                return None
            
            # Set duration and start time
            txt_clip = txt_clip.with_duration(duration).with_start(start_time)
            
            # Position subtitle ensuring it stays within visible area with extra spacing
            padding_pixels = int(video_height * settings.SUBTITLE_BOTTOM_PADDING)
            y_position = video_height - txt_clip.size[1] - padding_pixels
            
            # Ensure subtitle doesn't get cut off at bottom and doesn't go too high
            min_y = int(video_height * 0.35)  # Don't go above 35% of screen
            min_bottom_space = int(video_height * 0.08)  # Minimum 8% blank space from bottom
            max_y = video_height - txt_clip.size[1] - min_bottom_space
            
            y_position = max(min_y, min(y_position, max_y))
            txt_clip = txt_clip.with_position(('center', y_position))
            
            # Add fade in/out effects for smooth appearance (if available)
            fade_duration = min(0.3, duration / 4)
            try:
                txt_clip = txt_clip.fadein(fade_duration).fadeout(fade_duration)
            except AttributeError:
                # Fade methods not available, skip fade effects
                pass
            
            return txt_clip
            
        except Exception as e:
            print(f"Error creating subtitle clip: {e}")
            return None


if __name__ == "__main__":
    # Test the video composer
    print("VideoComposer module ready for testing")
