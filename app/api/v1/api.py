from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.videos import router as videos_router
from app.api.v1.endpoints.music import router as music_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(music_router, prefix="/music", tags=["music"])