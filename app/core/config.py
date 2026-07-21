import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

_IS_PRODUCTION = os.getenv("APP_ENV") == "production"

BASE_DIR: Path = Path("/var/data") if _IS_PRODUCTION else Path(__file__).resolve().parents[2] / "data"

BASE_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "ClipForgeReels"

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
    BASE_DIR: Path = BASE_DIR                              # project source root (read-only on Render)
    OUTPUT_DIR: Path = BASE_DIR / "outputs"
    TEMP_DIR: Path = BASE_DIR / "temp"
    VIDEOS_DIR: Path = BASE_DIR / "outputs" / "videos"
    IMAGES_DIR: Path = BASE_DIR / "outputs" / "images"
    AUDIO_DIR: Path = BASE_DIR / "outputs" / "audio"
    FONTS_DIR: Path = BASE_DIR / "fonts"

    # Video Generation Settings
    DEFAULT_FPS: int = int(os.getenv('DEFAULT_FPS', 30))
    DEFAULT_DURATION_PER_IMAGE: int = int(os.getenv('DEFAULT_DURATION_PER_IMAGE', 5))
    IMAGE_COUNT: int = int(os.getenv('IMAGE_COUNT', 7))
    MAX_SCRIPT_LENGTH: int = int(os.getenv('MAX_SCRIPT_LENGTH', 800))
    VIDEO_CREATION_CREDIT_COST: int = int(os.getenv('VIDEO_CREATION_CREDIT_COST', 200))
    VIDEO_GEN_MODEL: str = os.getenv('VIDEO_GEN_MODEL', 'sora-2')
    VIDEO_GEN_SECONDS: int = int(os.getenv('VIDEO_GEN_SECONDS', 8))
    VIDEO_GEN_SQUARE_STRATEGY: str = os.getenv('VIDEO_GEN_SQUARE_STRATEGY', 'landscape')  # landscape|portrait|auto

    # Job Queue Settings
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
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "support@clipforgereels.com")

    # Stripe Payment Integration
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_SUCCESS_URL: str = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/subscription/success")
    STRIPE_CANCEL_URL: str = os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/subscription/cancel")

    # Cloudinary Integration
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    # Subtitle Settings
    ENABLE_SUBTITLES: bool = os.getenv('ENABLE_SUBTITLES', 'True') == 'True'
    SUBTITLE_MODEL: str = os.getenv('SUBTITLE_MODEL', 'gpt-4o-mini')  # AI model for subtitle segmentation
    SUBTITLE_FONT: str = os.getenv('SUBTITLE_FONT', 'Roboto')
    SUBTITLE_FONT_SIZE_RATIO: float = float(os.getenv('SUBTITLE_FONT_SIZE_RATIO', '0.045'))  # 4.5% of video height
    SUBTITLE_COLOR: str = os.getenv('SUBTITLE_COLOR', 'white')
    SUBTITLE_STROKE_COLOR: str = os.getenv('SUBTITLE_STROKE_COLOR', 'black')
    SUBTITLE_STROKE_WIDTH: int = int(os.getenv('SUBTITLE_STROKE_WIDTH', '3'))
    SUBTITLE_BOTTOM_PADDING: float = float(os.getenv('SUBTITLE_BOTTOM_PADDING', '0.15'))  # 15% from bottom

    SUBTITLE_FORMATS: dict = {
        # id=1 → subtitles disabled
        1: {
            "enabled": False,
        },
        # id=2 → White text, semi-transparent black pill (CapCut default look)
        # 2-3 word bursts synced to Whisper word timestamps
        2: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,                 # large — only 2-3 words per event
            "primary_color": "&H00FFFFFF",   # white text
            "secondary_color": "&H000000FF",
            "outline_color": "&H00000000",   # black outline
            "back_color": "&HAA000000",      # ~67% opaque black pill
            "bold": True,
            "italic": False,
            "outline": 4,
            "shadow": 0,
            "border_style": 3,               # pill/box background
            "alignment": 2,                  # lower-third, centered
            "margin_v": 120,                 # above platform UI chrome
        },
        # id=3 → White text, black pill (high contrast — great for dark scenes)
        3: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,
            "primary_color": "&H00FFFFFF",   # white (BGR)
            "secondary_color": "&H000000FF",
            "outline_color": "&H00000000",
            "back_color": "&HCC000000",      # ~80% opaque black pill
            "bold": True,
            "italic": False,
            "outline": 3,
            "shadow": 0,
            "border_style": 3,               # pill/box background
            "alignment": 2,
            "margin_v": 120,
        },
        # id=4 → Black text, opaque white pill (clean minimal)
        4: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,
            "primary_color": "&H00000000",   # black text
            "secondary_color": "&H000000FF",
            "outline_color": "&H00FFFFFF",
            "back_color": "&H00FFFFFF",      # opaque white pill
            "bold": True,
            "italic": False,
            "outline": 1,
            "shadow": 0,
            "border_style": 3,               # pill/box background
            "alignment": 2,
            "margin_v": 120,
        },
        # id=5 → Black text, yellow pill (bold influencer style)
        5: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,
            "primary_color": "&H00000000",   # black text
            "secondary_color": "&H000000FF",
            "outline_color": "&H0000FFFF",
            "back_color": "&H0000FFFF",      # yellow (BGR) opaque pill
            "bold": True,
            "italic": False,
            "outline": 1,
            "shadow": 0,
            "border_style": 3,               # pill/box background
            "alignment": 2,
            "margin_v": 120,
        },
        # id=6 → White text, hot-pink pill (lifestyle / beauty creator style)
        6: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,
            "primary_color": "&H00FFFFFF",   # white text
            "secondary_color": "&H000000FF",
            "outline_color": "&H00B469FF",
            "back_color": "&H00B469FF",      # hot pink (BGR) opaque pill
            "bold": True,
            "italic": False,
            "outline": 2,
            "shadow": 0,
            "border_style": 3,               # pill/box background
            "alignment": 2,
            "margin_v": 120,
        },
        # id=7 → reserved for future frontend expansion (same as id=2)
        7: {
            "enabled": True,
            "font_name": "Roboto",
            "font_size": 72,
            "primary_color": "&H00FFFFFF",
            "secondary_color": "&H000000FF",
            "outline_color": "&H00000000",
            "back_color": "&HAA000000",
            "bold": True,
            "italic": False,
            "outline": 4,
            "shadow": 0,
            "border_style": 3,
            "alignment": 2,
            "margin_v": 120,
        },
    }

    # Audio Settings
    BACKGROUND_MUSIC_VOLUME: float = float(os.getenv('BACKGROUND_MUSIC_VOLUME', '0.2'))
    
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
             settings.IMAGES_DIR, settings.AUDIO_DIR, settings.FONTS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)
