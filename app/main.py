from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings # Note: config might be empty depending on structure

app = FastAPI(title="Vision-Pulse API")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "Welcome to Vision-Pulse API"}
