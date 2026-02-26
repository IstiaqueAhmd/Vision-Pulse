from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class VideoCreate(BaseModel):
    title: str = Field(..., description="Video title")
    script: str = Field(..., max_length=1500, description="The narration script")
    format: str = Field(..., description="Aspect ratio: 9:16, 16:9, or 1:1")
    style: str = Field(..., description="One of the 10 visual styles")
    voice: str = Field(..., description="ElevenLabs voice name or ID")
    category: Optional[str] = Field(None, description="Video category label")
    keywords: Optional[str] = Field(None, description="Extra keywords to include in image prompts")
    negative_keywords: Optional[str] = Field(None, description="Keywords to exclude from images")

class VideoResponse(BaseModel):
    id: int
    title: str
    category: Optional[str]
    format: str
    style: str
    voice: str
    script: str
    path: Optional[str]
    duration: Optional[float]
    status: str
    created_at: datetime

    class Config:
        orm_mode = True
