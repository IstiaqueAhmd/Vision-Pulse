from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.music import Music
from app.schemas.music import MusicResponse
import os
import shutil
from typing import List, Optional

router = APIRouter()

MUSIC_DIR = "musics"

# Ensure the musics directory exists
os.makedirs(MUSIC_DIR, exist_ok=True)

@router.post("/upload", response_model=MusicResponse)
async def upload_music(
    name: str = Form(...),
    category: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Basic validation (optional)
    if not file.filename.endswith(('.mp3', '.wav', '.ogg', '.flac')):
        raise HTTPException(status_code=400, detail="Invalid audio format. Allowed: mp3, wav, ogg, flac.")

    # Save file
    file_location = os.path.join(MUSIC_DIR, file.filename)
    
    # Check if a file with the same name exists to avoid overwriting (or handle it by suffixing)
    # Simple conflict resolution
    base, ext = os.path.splitext(file.filename)
    counter = 1
    while os.path.exists(file_location):
        file_location = os.path.join(MUSIC_DIR, f"{base}_{counter}{ext}")
        counter += 1

    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
    
    # Save to database
    db_music = Music(name=name, category=category, file_path=file_location)
    db.add(db_music)
    db.commit()
    db.refresh(db_music)
    
    return db_music

@router.get("/get", response_model=List[MusicResponse])
def get_musics(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    musics = db.query(Music).offset(skip).limit(limit).all()
    return musics

@router.delete("/delete/{music_id}")
def delete_music(music_id: int, db: Session = Depends(get_db)):
    db_music = db.query(Music).filter(Music.id == music_id).first()
    if not db_music:
        raise HTTPException(status_code=404, detail="Music not found")
    
    # Delete the file
    if os.path.exists(db_music.file_path):
        os.remove(db_music.file_path)
    
    # Delete from database
    db.delete(db_music)
    db.commit()
    
    return JSONResponse(content={"message": "Music deleted successfully"})
