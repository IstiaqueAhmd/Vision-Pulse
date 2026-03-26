from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.videos import router as videos_router
from app.api.v1.endpoints.music import router as music_router
from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.subscriptions import router as subscriptions_router
from app.api.v1.endpoints.payments import router as payments_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(videos_router, prefix="/videos", tags=["videos"])
api_router.include_router(music_router, prefix="/music", tags=["music"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(subscriptions_router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])