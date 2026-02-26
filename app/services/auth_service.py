from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional
import random
import string
from datetime import datetime, timedelta

from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash
from app.services.email_service import send_otp_email

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_in: UserCreate) -> User:
    # Check if user already exists
    if get_user_by_email(db, email=user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system."
        )
    
    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def generate_password_reset_otp(db: Session, email: str) -> bool:
    user = get_user_by_email(db, email)
    if not user:
        # We don't expose if the email exists or not for security reasons
        return True
    
    # Generate 6 digit OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Expire in 15 minutes
    user.reset_otp = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    db.commit()
    
    # Send actual email
    send_otp_email(to_email=email, otp=otp)
    
    return True

def verify_otp(db: Session, email: str, otp: str) -> bool:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")
        
    if not user.reset_otp or user.reset_otp != otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
        
    if user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
    
    # We clear the expiration time but LEAVE the reset_otp temporarily to indicate 
    # to the `reset_password` step that this user successfully passed verification.
    user.otp_expires_at = None
    db.commit()
    return True

def reset_password(db: Session, email: str, new_password: str) -> bool:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")
    
    # Ensure they actually passed the OTP verification step
    # If otp_expires_at is None but reset_otp has a value, they verified successfully.
    if not user.reset_otp or user.otp_expires_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You must verify an OTP first")
        
    user.hashed_password = get_password_hash(new_password)
    user.reset_otp = None
    user.otp_expires_at = None
    
    db.commit()
    return True
