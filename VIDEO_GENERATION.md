# 🎬 Vision-Pulse — Video Generation Process

This document explains the full end-to-end process of how Vision-Pulse generates AI-powered videos, from a user request through to the final `.mp4` file.

---

## Overview

Vision-Pulse is built around a **6-step pipeline**. Every video creation request goes through these stages in sequence:

```
User Request
    │
    ▼
[Job Queue]  ──→  Queued / Processing / Completed / Failed
    │
    ▼
Step 1: Narration Generation   (ElevenLabs TTS → OpenAI TTS fallback)
    │
    ▼
Step 2: Image Prompt Creation  
    │
    ▼
Step 3: Image Generation       
    │
    ▼
Step 4-5: Video Composition    (MoviePy: clips + zoom/pan effects + AI subtitles)
    │
    ▼
Step 6: Save to Database       
    │
    ▼
Final MP4 Output
```



## Step-by-Step Breakdown

### Step 1 — Narration Generation

The script text is converted to an audio MP3 using a **dual-provider** strategy:

1. **Primary**: [ElevenLabs](https://elevenlabs.io/) — Uses the `eleven_turbo_v2_5` model with a selected voice.
2. **Fallback**: [OpenAI TTS](https://platform.openai.com/docs/guides/text-to-speech) — Uses `tts-1-hd` model with a mapped voice.

**Available voices (ElevenLabs):**

| Voice | Gender | Accent |
|---|---|---|
| Hope, Cassidy, Lana | Female | American |
| Brian, Peter, Adam, Alex, Finn | Male | American |
| Amelia, Jane | Female | British |
| Edward, Archie | Male | British |

> Voices can be selected by name or directly by ElevenLabs Voice ID.

The audio is saved to `outputs/audio/narration_<voice>_<timestamp>.mp3`.

---

### Step 2 — Image Prompt Creation

**OpenAI GPT-4** analyzes the script and generates a set of image prompts:

- **Dynamic count** based on script length:
  - `< 100 words` → 3–5 images
  - `100–300 words` → 5–7 images
  - `300–500 words` → 7–10 images
  - `500+ words` → 10–12 images

- Each prompt enforces the selected **visual style** (e.g., Anime, Hyper Realistic, Comic Noir).
- Prompts always include instructions to **exclude text, letters, and watermarks**.
- Each prompt also carries a **negative prompt** listing elements to avoid (blurriness, watermarks, etc.).

**Available styles:**

`Realistic Action Art`, `B&W Sketch`, `Comic Noir`, `Retro Noir`, `Medieval Painting`, `Anime`, `Warm Fable`, `Hyper Realistic`, `3D Cartoon`, `Caricature`

---

### Step 3 — Image Generation

Images are generated for each prompt using a **dual-provider** strategy:

1. **Primary**: **Google Gemini** (`gemini-2.5-flash-image`) — Fast, high-quality image generation.
2. **Fallback**: **OpenAI DALL-E 3** — Used if Gemini is unavailable or fails.

**Image sizes** are set based on the target video format:

| Format | Resolution | Use Case |
|---|---|---|
| `9:16` | 1024×1792 | TikTok / Reels (Vertical) |
| `16:9` | 1792×1024 | YouTube (Horizontal) |
| `1:1` | 1024×1024 | Instagram (Square) |

If both providers fail, a **placeholder image** is created automatically so the pipeline doesn't break.

Images are saved to `outputs/images/image_<NNN>_<timestamp>.png`.

---

### Steps 4 & 5 — Video Composition

This is the most complex step, handled entirely by [MoviePy](https://zulko.github.io/moviepy/).

#### 4a — Image Processing
Each image is:
1. **Scaled** to cover the full video frame (like CSS `object-fit: cover`) — no black bars.
2. **Center-cropped** to the exact target dimensions.

#### 4b — Camera Motion Effects
Each clip gets a **cinematic camera motion** effect applied, cycling through a pattern:

| Pattern Index | Effect |
|---|---|
| 0 | Horizontal Pan (left → right) |
| 1 | Zoom In (subtle, 15% max) |
| 2 | Horizontal Pan (opposite direction) |
| 3 | Zoom Out |

All motion uses **quintic ease-in-out** for ultra-smooth, cinematic movement. Rotation effects exist but are **disabled by default** (configurable via `CAMERA_ENABLE_ROTATION`).

#### 4c — AI-Powered Subtitles 
Subtitles are generated automatically when `ENABLE_SUBTITLES=True`:

1. **GPT-4o-mini** intelligently segments the script into subtitle chunks (5–12 words each).
2. Timing is calculated **proportionally** by word count, capped between 0.8s and 5.0s per segment.
3. Subtitles are rendered with a **white font + black stroke** for readability.
4. Subtitles fade in and fade out smoothly.
5. An `.srt` file is also exported to `temp/subtitles.srt`.

#### 4d — Final Render
All clips are concatenated and the narration audio is attached. The final video is exported using:
- **Codec**: `libx264`
- **Audio Codec**: `aac`
- **FPS**: 30 (configurable)
- **Preset**: `medium`

Video files are saved to `outputs/videos/<title>_<timestamp>_<uid>.mp4`.

---

### Step 6 — Save to Database

Once the video file is verified on disk, its metadata is persisted:

```json
{
  "title": "My Video",
  "category": "Education",
  "format": "16:9",
  "style": "Hyper Realistic",
  "voice": "Cassidy",
  "script": "...",
  "path": "outputs/videos/my-video_20240201_120000_abc12345.mp4",
  "duration": 45.3,
  "status": "completed",
  "created_at": "2024-02-01T12:00:00"
}
```

For **update jobs** (`_update_video_id` present), the old video file is deleted and the database record is updated in place.

---

## Job Queue System 

Video generation is asynchronous. 

### Job Lifecycle

```
add_job()  →  QUEUED  →  PROCESSING  →  COMPLETED
                                    ↘  FAILED  →  [retry up to 3x]
```

### Key Limits (configurable in `config.py`)

| Setting | Default | Description |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | 10 | Max simultaneous videos processing |
| `MAX_QUEUED_JOBS` | 10 | Max jobs waiting in queue |
| `MAX_RETRY_ATTEMPTS` | 3 | Auto-retry on failure |
| `RETRY_DELAY_SECONDS` | 60 | Wait between retries |

### API Endpoints 

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate` | Submit a new video generation job |
| `GET` | `/job/<job_id>` | Check job status and progress |
| `GET` | `/videos` | List all generated videos |
| `GET` | `/video/<id>` | Get video metadata |
| `DELETE` | `/video/<id>` | Delete a video |

---

## Input Parameters

When submitting to `/generate`, the following fields are accepted:

| Field | Required | Description |
|---|---|---|
| `title` | yes | Video title |
| `script` | yes | The narration script (max 1500 chars) |
| `format` | yes | `9:16`, `16:9`, or `1:1` |
| `style` | yes | One of the 10 visual styles |
| `voice` | yes | ElevenLabs voice name or ID |
| `category` | no | Video category label |
| `keywords` | no | Extra keywords to include in image prompts |
| `negative_keywords` | no | Keywords to exclude from images |


---

## Project Structure 

video_generator_backend/
├── app/
│   ├── main.py                  # FastAPI application instance and entry point
│   ├── api/                     # API Routers
│   │   ├── dependencies.py      # Reusable dependencies (e.g., get_current_user, get_db)
│   │   └── v1/                  
│   │       ├── api.py           # Ties all v1 routers together
│   │       └── endpoints/
│   │           ├── auth.py      # Login, token generation, password reset
│   │           ├── users.py     # User profile management
│   │           └── videos.py    # Trigger video generation, check status, fetch result
│   ├── core/                    # Application-wide settings
│   │   ├── config.py            # Environment variables (Pydantic BaseSettings)
│   │   └── security.py          # Password hashing, JWT creation/verification
│   ├── db/                      # Database setup
│   │   ├── session.py           # SQLAlchemy/Asyncpg engine and session maker
│   │   └── base.py              # Base declarative class
│   ├── models/                  # Database Models (SQLAlchemy)
│   │   ├── user.py              # User table (id, email, hashed_password)
│   │   └── video.py             # Video table (id, user_id, status, file_url)
│   ├── schemas/                 # Pydantic Models (Data Validation)
│   │   ├── token.py             # Token response schema
│   │   ├── user.py              # UserCreate, UserResponse schemas
│   │   └── video.py             # VideoCreate, VideoStatus schemas
│   ├── services/                # Business Logic (Keeps endpoints clean)
│   │   ├── auth_service.py      # Logic for authenticating users
│   │   └── video_service.py     # Logic for handling video generation requests
│   └── worker/                  # Background Task Processing (e.g., Celery)
│       ├── celery_app.py        # Celery instance configuration
│       └── tasks.py             # The actual video generation functions
├── alembic/                     # Database migrations folder
├── tests/                       # Pytest unit and integration tests
├── .env                         # Environment variables (secrets, DB URIs)
├── alembic.ini                  # Alembic configuration
├── docker-compose.yml           # Runs FastAPI, DB, Redis, and Celery Worker
├── Dockerfile                   # Docker build instructions for the API
└── requirements.txt             # Python dependencies



## Configuration Reference (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_FPS` | `30` | Video frame rate |
| `ENABLE_SUBTITLES` | `True` | Toggle subtitle generation |
| `SUBTITLE_MODEL` | `gpt-4o-mini` | AI model for subtitle segmentation |
| `CAMERA_ZOOM_INTENSITY` | `0.15` | Max zoom (15%) |
| `CAMERA_ENABLE_ROTATION` | `False` | Enable rotation effects |
| `CAMERA_PAN_HORIZONTAL_MAX` | `0.08` | Max horizontal pan (8%) |
| `CAMERA_PAN_VERTICAL_MAX` | `0.04` | Max vertical pan (4%) |
| `IMAGE_COUNT` | `7` | Default images per video |
| `MAX_SCRIPT_LENGTH` | `1500` | Max script characters |
