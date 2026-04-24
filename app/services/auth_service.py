from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional
import random
import string
from datetime import datetime, timedelta

from app.models.user import User
from app.models.notification import Notification
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password
from app.services.email_service import send_otp_email

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def _create_welcome_notification(db: Session, user: User) -> None:
    """Create a welcome in-app notification for a newly registered user."""
    notification = Notification(
        user_id=user.id,
        title="Welcome to Vision Pulse",
        message=f"Welcome {user.name}! Your account is ready. Start creating your first video.",
        type="welcome",
        is_read=False,
    )
    db.add(notification)

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
        is_verified=False,
        status="active"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate OTP for registration
    otp = ''.join(random.choices(string.digits, k=6))
    user.reset_otp = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    # Send actual email
    try:
        send_otp_email(to_email=user_in.email, otp=otp)
    except Exception as e:
        print(f"Failed to send email: {e}")

    # Assign default "free" subscription plan
    free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "Free").first()
    if not free_plan:
        free_plan = SubscriptionPlan(
            name="Free",
            monthly_price=0.0,
            monthly_credits=200,  # Default free credits
            video_limit_per_month=2,
            max_concurrent_jobs=1,
            max_queued_jobs=5,
            max_retry_attempts=1,
            plan_status="active"
        )
        db.add(free_plan)
        db.commit()
        db.refresh(free_plan)

    now = datetime.utcnow()
    db_sub = UserSubscription(
        user_id=user.id,
        plan_id=free_plan.id,
        start_date=now,
        end_date=None,
        status="active"
    )
    # Allocate initial free credits based on the plan
    user.credits += free_plan.monthly_credits
    db.add(db_sub)
    _create_welcome_notification(db, user)
    db.commit()

    return user

def authenticate_google_user(db: Session, email: str, name: str) -> User:
    """
    Handles Google OAuth Login/Signup.
    If the email exists, just return the user (Login).
    If the email does not exist, create the user as a Google provider (Signup).
    """
    user = get_user_by_email(db, email=email)
    
    if user:
        # Optional: You could update their name or picture here if desired.
        return user
        
    # User does not exist, create a new one!
    new_user = User(
        name=name,
        email=email,
        auth_provider="google",
        hashed_password=None, # Google users don't have local passwords
        is_verified=True, # Google users are already verified
        status="active"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Assign default "free" subscription plan
    free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == "Free").first()
    if not free_plan:
        free_plan = SubscriptionPlan(
            name="Free",
            monthly_price=0.0,
            monthly_credits=200,  # Default free credits
            video_limit_per_month=2,
            max_concurrent_jobs=1,
            max_queued_jobs=5,
            max_retry_attempts=1,
            plan_status="active"
        )
        db.add(free_plan)
        db.commit()
        db.refresh(free_plan)

    now = datetime.utcnow()
    db_sub = UserSubscription(
        user_id=new_user.id,
        plan_id=free_plan.id,
        start_date=now,
        end_date=None,
        status="active"
    )
    # Allocate initial free credits based on the plan
    new_user.credits += free_plan.monthly_credits
    db.add(db_sub)
    _create_welcome_notification(db, new_user)
    db.commit()

    return new_user

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

def verify_register_otp(db: Session, email: str, otp: str) -> bool:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")
        
    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already verified")
        
    if not user.reset_otp or user.reset_otp != otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
        
    if user.otp_expires_at and user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
    
    user.is_verified = True
    user.reset_otp = None
    user.otp_expires_at = None
    db.commit()
    return True

def resend_register_otp(db: Session, email: str) -> bool:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
    if user.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already verified")
        
    # Generate new OTP
    otp = ''.join(random.choices(string.digits, k=6))
    
    # Update expiration
    user.reset_otp = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    # Send email
    try:
        send_otp_email(to_email=user.email, otp=otp)
    except Exception as e:
        print(f"Failed to send email: {e}")
        
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

def change_password(db: Session, user: User, new_password: str) -> bool:
    # Ensure OTP verification was completed before allowing password change
    if not user.reset_otp or user.otp_expires_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must verify an OTP first"
        )

    user.hashed_password = get_password_hash(new_password)
    user.reset_otp = None
    user.otp_expires_at = None

    db.commit()
    return True
