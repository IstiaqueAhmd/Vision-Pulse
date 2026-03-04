from pydantic import BaseModel, Field
from typing import Optional, Literal
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
    music_id: Optional[int] = Field(None, description="The Background music for the video")
    media_option: Optional[Literal["all_images", "first_scene", "last_scene", "first_and_last_scene"]] = Field("all_images", description="Controls which scenes are AI video clips vs static images")
    # Injected server-side from the JWT — not sent by the client
    user_id: Optional[int] = Field(None, description="Owner user ID (set by server)")

class VideoResponse(BaseModel):
    id: int
    user_id: int
    title: str
    category: Optional[str]
    format: str
    style: str
    voice: str
    script: str
    path: Optional[str]
    duration: Optional[float]
    music_id: Optional[int]
    media_option: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
