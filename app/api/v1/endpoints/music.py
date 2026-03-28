from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.music import Music
from app.schemas.music import MusicResponse
from app.core.config import settings
import shutil
from pathlib import Path
from typing import List, Optional

router = APIRouter()

# Absolute path — works regardless of server working directory
MUSIC_DIR = settings.BASE_DIR / "musics"

# Ensure the musics directory exists
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

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

    # Save file using absolute path
    file_location = MUSIC_DIR / file.filename

    # Simple conflict resolution — avoid overwriting existing files
    base, ext = Path(file.filename).stem, Path(file.filename).suffix
    counter = 1
    while file_location.exists():
        file_location = MUSIC_DIR / f"{base}_{counter}{ext}"
        counter += 1

    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # Store absolute path in DB so it resolves correctly on any server
    db_music = Music(name=name, category=category, file_path=str(file_location))
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
    music_path = Path(db_music.file_path)
    if music_path.exists():
        music_path.unlink()
    
    # Delete from database
    db.delete(db_music)
    db.commit()
    
    return JSONResponse(content={"message": "Music deleted successfully"})
