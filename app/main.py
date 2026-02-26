from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings

from app.db.session import engine
from app.db.base import Base
from app.models.user import User
from app.models.video import Video

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vision-Pulse API")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Vision-Pulse API"}
