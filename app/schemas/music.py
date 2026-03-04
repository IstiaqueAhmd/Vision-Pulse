from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MusicBase(BaseModel):
    name: str
    category: Optional[str] = None

class MusicCreate(MusicBase):
    pass

class MusicResponse(MusicBase):
    id: int
    file_path: str
    upload_date: datetime

    class Config:
        from_attributes = True
