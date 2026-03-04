import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vision-Pulse"
    
    # Base directory (project root: Vision-Pulse/)
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    
    #Generative AI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")

    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    
    # Directory Configuration
    OUTPUT_DIR: Path = BASE_DIR / os.getenv('OUTPUT_DIR', 'outputs')
    TEMP_DIR: Path = BASE_DIR / os.getenv('TEMP_DIR', 'temp')
    VIDEOS_DIR: Path = BASE_DIR / os.getenv('VIDEOS_DIR', 'outputs/videos')
    IMAGES_DIR: Path = BASE_DIR / os.getenv('IMAGES_DIR', 'outputs/images')
    AUDIO_DIR: Path = BASE_DIR / os.getenv('AUDIO_DIR', 'outputs/audio')

    # Video Generation Settings
    DEFAULT_FPS: int = int(os.getenv('DEFAULT_FPS', 30))
    DEFAULT_DURATION_PER_IMAGE: int = int(os.getenv('DEFAULT_DURATION_PER_IMAGE', 5))
    IMAGE_COUNT: int = int(os.getenv('IMAGE_COUNT', 7))
    MAX_SCRIPT_LENGTH: int = int(os.getenv('MAX_SCRIPT_LENGTH', 1500))

    # Job Queue Settings
    MAX_CONCURRENT_JOBS: int = int(os.getenv('MAX_CONCURRENT_JOBS', 10))  # Maximum 1 video processing at a time
    MAX_QUEUED_JOBS: int = int(os.getenv('MAX_QUEUED_JOBS', 10))  # Maximum jobs in queue (up to 10 can wait)
    MAX_RETRY_ATTEMPTS: int = int(os.getenv('MAX_RETRY_ATTEMPTS', 3))  # Retry failed jobs
    RETRY_DELAY_SECONDS: int = int(os.getenv('RETRY_DELAY_SECONDS', 60))  # Wait before retry

    # Camera Movement Settings
    CAMERA_MOTION_TYPE: str = os.getenv('CAMERA_MOTION_TYPE', 'slow_pan')  # slow_pan, slow_zoom, static
    CAMERA_ZOOM_INTENSITY: float = float(os.getenv('CAMERA_ZOOM_INTENSITY', 0.15))  # 15% zoom (down from 35%)
    CAMERA_ENABLE_ROTATION: bool = os.getenv('CAMERA_ENABLE_ROTATION', 'False') == 'True'  # Disable spin effects
    CAMERA_FOCUS_ON_SUBJECT: bool = os.getenv('CAMERA_FOCUS_ON_SUBJECT', 'True') == 'True'  # Track subjects
    CAMERA_MOTION_SMOOTHNESS: str = os.getenv('CAMERA_MOTION_SMOOTHNESS', 'high')  # high, medium, low
    CAMERA_PAN_HORIZONTAL_MAX: float = float(os.getenv('CAMERA_PAN_HORIZONTAL_MAX', 0.08))  # 8% max (down from 12%)
    CAMERA_PAN_VERTICAL_MAX: float = float(os.getenv('CAMERA_PAN_VERTICAL_MAX', 0.04))  # 4% max (down from 6%)

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND")

    # Email Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@visionpulse.com")

    # Subtitle Settings
    ENABLE_SUBTITLES: bool = os.getenv('ENABLE_SUBTITLES', 'True') == 'True'
    SUBTITLE_MODEL: str = os.getenv('SUBTITLE_MODEL', 'gpt-4o-mini')  # AI model for subtitle segmentation
    SUBTITLE_FONT: str = os.getenv('SUBTITLE_FONT', 'Arial')
    SUBTITLE_FONT_SIZE_RATIO: float = float(os.getenv('SUBTITLE_FONT_SIZE_RATIO', '0.045'))  # 4.5% of video height
    SUBTITLE_COLOR: str = os.getenv('SUBTITLE_COLOR', 'white')
    SUBTITLE_STROKE_COLOR: str = os.getenv('SUBTITLE_STROKE_COLOR', 'black')
    SUBTITLE_STROKE_WIDTH: int = int(os.getenv('SUBTITLE_STROKE_WIDTH', '3'))
    SUBTITLE_BOTTOM_PADDING: float = float(os.getenv('SUBTITLE_BOTTOM_PADDING', '0.15'))  # 15% from bottom

    # Audio Settings
    BACKGROUND_MUSIC_VOLUME: float = float(os.getenv('BACKGROUND_MUSIC_VOLUME', '0.4'))
    
    # Video Formats
    VIDEO_FORMATS: dict = {
        '9:16': (1080, 1920),  # Vertical (TikTok, Reels)
        '16:9': (1920, 1080),  # Horizontal (YouTube)
        '1:1': (1080, 1080)    # Square (Instagram)
    }
    
    # Video Styles
    VIDEO_STYLES: list = [
        'Realistic Action Art',
        'B&W Sketch',
        'Comic Noir',
        'Retro Noir',
        'Medieval Painting',
        'Anime',
        'Warm Fable',
        'Hyper Realistic',
        '3D Cartoon',
        'Caricature'
    ]

    # Voice Types (ElevenLabs voices)
    VOICE_TYPES: dict = {
        # Female - American
        'Hope': 'tnSpp4vdxKPjI9w0GnoV',
        'Cassidy': '56AoDkrOh6qfVPDXZ7Pt',
        'Lana': '0zj1iWvloMkAXydIFsJR',
        
        # Male - American
        'Brian': 'D11AWvkESE7DJwqIVi7L',
        'Peter': 'ZthjuvLPty3kTMaNKVKb',
        'Adam': 'pNInz6obpgDQGcFmaJgB',
        'Alex': 'yl2ZDV1MzN4HbQJbMihG',
        'Finn': 'vBKc2FfBKJfcZNyEt1n6',
        
        # Female - British
        'Amelia': 'ZF6FPAbjXT4488VcRRnw',
        'Jane': 'RILOU7YmBhvwJGDGjNmP',
        
        # Male - British
        'Edward': 'goT3UYdM9bhm0n2lmKQx',
        'Archie': 'kmSVBPu7loj4ayNinwWM'
    }

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Ensure all output directories exist at startup
for _dir in [settings.OUTPUT_DIR, settings.TEMP_DIR, settings.VIDEOS_DIR,
             settings.IMAGES_DIR, settings.AUDIO_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)
