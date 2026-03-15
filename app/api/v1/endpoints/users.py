import os
import shutil
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationCountResponse
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

@router.get("/{user_id}/credit-balance")
def get_credit_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> int:
    """Calculate the current credit balance for a user."""
    user = db.query(User).filter(User.id == current_user.id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.credits


@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 200")

    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    return query.order_by(Notification.created_at.desc()).limit(limit).all()


@router.get("/notifications/unread-count", response_model=NotificationCountResponse)
def get_unread_notifications_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    unread = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False)
    ).scalar() or 0
    return {"unread": unread}


@router.put("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    return {"status": "ok", "notification_id": notification.id}


@router.put("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False)
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()

    return {"status": "ok"}