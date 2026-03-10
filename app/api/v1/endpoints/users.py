import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UpdateUserStatusRequest
from app.api.deps import get_current_user, get_current_admin_user

router = APIRouter()

@router.put("/update-profile", response_model=UserResponse)
async def update_user_me(
    name: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update own user profile name and/or profile image.
    Accepts multipart/form-data.
    """
    if name is not None:
        current_user.name = name
        
    if profile_image is not None and profile_image.filename:
        # Ensure the directory exists
        os.makedirs(os.path.join("outputs", "profiles"), exist_ok=True)
        
        # Generate new file name
        ext = os.path.splitext(profile_image.filename)[1]
        if not ext:
            ext = ".png" # fallback
            
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join("outputs", "profiles", unique_filename)
        
        # Save the uploaded file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)
            
        # Optional: Delete old profile picture if it was stored locally
        if current_user.profile_image_url and current_user.profile_image_url.startswith("/outputs/profiles/"):
            old_file_path = current_user.profile_image_url.lstrip("/")
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except BaseException:
                    pass
        
        # Set new profile image URL (matches static files mount in main.py)
        current_user.profile_image_url = f"/outputs/profiles/{unique_filename}"
            
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/{user_id}/status")
def update_user_status(
    user_id: int,
    request: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if request.status not in ["active", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'active' or 'suspended'.")
        
    user.status = request.status
    db.commit()
    
    return {
        "message": f"User status updated to {request.status}", 
        "user_id": user.id, 
        "status": user.status
    }