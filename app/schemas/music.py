from pydantic import BaseModel, field_validator
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

    @field_validator('file_path', mode='before')
    @classmethod
    def format_file_path(cls, v):
        if not v:
            return v
        v_str = str(v).replace('\\', '/')
        if '/musics/' in v_str:
            return '/musics/' + v_str.split('/musics/')[-1]
        return v

    class Config:
        from_attributes = True
