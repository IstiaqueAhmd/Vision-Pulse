import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.api import api_router
from app.workers.worker import VideoWorker
from app.db.session import engine
from app.db.base import Base

Base.metadata.create_all(bind=engine)

# Background worker instance
worker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    global worker
    
    # Startup: Start background worker
    worker = VideoWorker(check_interval=2)
    worker_thread = threading.Thread(target=worker.run, daemon=True)
    worker_thread.start()
    print("✓ Background worker thread started")
    
    yield  # Application is running
    
    # Shutdown: Stop background worker
    if worker:
        worker.stop()
    print("✓ Background worker stopping...")

app = FastAPI(
    title="ClipForge",
    description="AI Video Generation System",
    version="1.0.0",
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000","http://localhost:3001"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Vision-Pulse API"}
