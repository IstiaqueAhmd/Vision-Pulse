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