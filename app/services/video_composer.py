"""
Video Composer Module
Combines images and narration into a video with effects
"""
from pathlib import Path
from typing import List, Dict
import random
from moviepy import ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips, CompositeVideoClip, CompositeAudioClip
import numpy as np
from PIL import Image, ImageFont, ImageDraw
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
            
            # Calculate zoom factor with consistent motion
            progress = t / duration
            # Apply linear movement for consistent motion
            eased_progress = progress
            
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
            
            # Calculate zoom factor (1.15 to 1.0) with consistent motion
            progress = t / duration
            # Apply linear movement for consistent motion
            eased_progress = progress
            
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
            
            # Slow pan with consistent motion
            progress = t / duration
            # Apply linear movement for consistent motion
            eased_progress = progress
            
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
            
            # Progress with consistent motion
            progress = t / duration
            eased = progress
            
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
            audio_duration = audio.duration

            # Add padding to prevent video from cutting off abruptly at the end
            # This allows the final spoken word to finish cleanly and holds the last frame.
            # We clamp the audio to its own duration first to prevent MoviePy from requesting
            # frames beyond the file boundary (OSError: Accessing time t=X with clip duration=X).
            audio = audio.subclipped(0, audio_duration)
            total_duration = audio_duration + 1.0
            
            # Calculate duration per image
            duration_per_image = total_duration / len(image_paths)
            
            # Get video dimensions
            width, height = settings.VIDEO_FORMATS[video_format]
            
            # Create video clips with effects
            if video_scene_indices is None:
                video_scene_indices = set()
            
            clips = []
            for i, img_path in enumerate(image_paths):
                
                # Check if this scene is a video clip (from Sora 2)
                if i in video_scene_indices and str(img_path).endswith('.mp4'):
                    print(f"Processing video scene {i+1}/{len(image_paths)}...")
                    try:
                        vclip = VideoFileClip(str(img_path))

                        # Resize and center-crop to target dimensions without stretching.
                        scale = max(width / vclip.w, height / vclip.h)
                        resized_w = int(round(vclip.w * scale))
                        resized_h = int(round(vclip.h * scale))
                        vclip = vclip.resized((resized_w, resized_h))
                        x_center = resized_w / 2
                        y_center = resized_h / 2
                        vclip = vclip.cropped(
                            x_center=x_center,
                            y_center=y_center,
                            width=width,
                            height=height,
                        )
                        
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
            file_uuid = unique_id if unique_id else str(uuid.uuid4())
            output_path = settings.VIDEOS_DIR / f"{file_uuid}.mp4"
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
            
            # Extract thumbnail before subtitles are burned
            try:
                thumbnail_path = output_path.with_suffix('.jpg')
                import subprocess
                subprocess.run([
                    'ffmpeg', '-y', '-i', str(output_path),
                    '-ss', '00:00:01.000', '-vframes', '1',
                    str(thumbnail_path)
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"✓ Thumbnail extracted without subtitles via FFmpeg: {thumbnail_path}")
            except Exception as e:
                print(f"✗ Failed to extract thumbnail via FFmpeg: {e}")
            
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
            
            # Burn ASS subtitles via FFmpeg (after MoviePy resources are freed)
            if script and settings.ENABLE_SUBTITLES and subtitle_id is not None and subtitle_id != 1:
                print("Burning ASS subtitles via FFmpeg...")
                output_path = self._generate_and_burn_subtitles(
                    output_path, script, width, height, audio.duration, len(image_paths), subtitle_id, audio_path
                )

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
    
    def _generate_and_burn_subtitles(
        self,
        video_path: Path,
        script: str,
        width: int,
        height: int,
        duration: float,
        num_images: int,
        subtitle_id: int,
        audio_path: Path = None,
    ) -> Path:
        """
        Generate an ASS subtitle file from the script and burn it into the
        video using FFmpeg.  The video file is updated in-place.

        Args:
            video_path:  Path to the rendered video file.
            script:      Full video narration script.
            width:       Video pixel width.
            height:      Video pixel height.
            duration:    Total video duration in seconds.
            num_images:  Number of scenes (used for AI segmentation hints).
            subtitle_id: Style preset ID from settings.SUBTITLE_FORMATS.
            audio_path:  Optional path to the audio file for exact timestamp generation.

        Returns:
            Path to the video (same path; file may be replaced in-place).
        """
        try:
            # Retrieve the style preset
            style = settings.SUBTITLE_FORMATS.get(subtitle_id, {})
            if not style.get("enabled", False):
                print(f"Subtitle preset {subtitle_id} is disabled, skipping.")
                return video_path

            # 1. Generate timed subtitle segments (AI-assisted or Whisper-based)
            subtitle_segments = self.subtitle_gen.generate_subtitle_segments(
                script, duration, num_images, str(audio_path) if audio_path else None
            )
            if not subtitle_segments:
                print("No subtitle segments generated, skipping subtitle burn.")
                return video_path

            # 2. Export ASS file with styling
            ass_path = settings.TEMP_DIR / "subtitles.ass"
            self.subtitle_gen.export_ass(
                subtitle_segments,
                style,
                str(ass_path),
                video_width=width,
                video_height=height,
            )

            # 3. Burn subtitles into the video via FFmpeg
            return self._burn_subtitles_ffmpeg(video_path, ass_path)

        except Exception as e:
            print(f"Subtitle generation/burn failed — video saved without subtitles: {e}")
            import traceback
            traceback.print_exc()
            return video_path

    def _burn_subtitles_ffmpeg(self, video_path: Path, ass_path: Path) -> Path:
        """
        Burn an ASS subtitle file into the video using ffmpeg-python.
        The original video file is replaced in-place with the subtitled version.

        Uses the FFmpeg `ass` filter which preserves all ASS styling (fonts,
        colours, outlines, shadows, border styles) without frame-by-frame
        compositing.

        Args:
            video_path: Path to the source (already-rendered) video.
            ass_path:   Path to the .ass subtitle file.

        Returns:
            Path to the updated video (same as video_path).
        """
        import ffmpeg
        import os

        temp_out = video_path.with_suffix(".subbed.mp4")

        try:
            print(f"  FFmpeg burning subtitles: {ass_path.name} → {video_path.name}")

            input_stream = ffmpeg.input(str(video_path))

            # FFmpeg's ass filter aggressively parses colons and backslashes in Windows.
            # Convert to absolute path, swap backslashes for forward slashes, and escape the drive letter colon.
            # Example: C:\path\to\subtitles.ass -> C\:/path/to/subtitles.ass
            absolute_ass_path = str(ass_path.absolute()).replace("\\", "/")
            safe_ass_path = absolute_ass_path.replace(":", "\\:")
            
            # The fontsdir should be an absolute path with linux/windows appropriate slashes
            fonts_dir_path = str(settings.FONTS_DIR.absolute()).replace("\\", "/")

            # Apply ASS subtitle filter to the video stream, explicitly providing the fonts directory
            video_stream = input_stream.video.filter(
                "ass", safe_ass_path, fontsdir=fonts_dir_path
            )
            audio_stream = input_stream.audio

            (
                ffmpeg
                .output(
                    video_stream,
                    audio_stream,
                    str(temp_out),
                    acodec="copy",        # audio: copy without re-encoding
                    vcodec="libx264",
                    preset="medium",
                    crf=18,              # visually lossless quality
                )
                .overwrite_output()
                .run(quiet=True)
            )

            if temp_out.exists() and temp_out.stat().st_size > 0:
                temp_out.replace(video_path)   # atomic replace on same drive
                print(f"  ✓ Subtitles burned successfully into {video_path.name}")
            else:
                print("  ✗ FFmpeg produced no output — keeping unsubtitled video.")
                if temp_out.exists():
                    temp_out.unlink()

        except Exception as e:
            print(f"  FFmpeg subtitle burn error: {e}")
            import traceback
            traceback.print_exc()
            # Clean up partial output
            if temp_out.exists():
                temp_out.unlink()

        return video_path


if __name__ == "__main__":
    # Test the video composer
    print("VideoComposer module ready for testing")
