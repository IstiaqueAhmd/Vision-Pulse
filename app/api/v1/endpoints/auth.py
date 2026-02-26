from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.schemas.token import Token
from app.services.auth_service import create_user, verify_otp_and_reset_password, generate_password_reset_otp

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register_user(
    user_in: UserCreate, 
    db: Session = Depends(get_db)
):
    """
    Register a new user in the system.
    """
    user = create_user(db, user_in)
    return user

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # Find user by email (OAuth2PasswordRequestForm uses 'username' by default)
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    return {
        "access_token": create_access_token(
            subject=user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Generate an OTP and send it via email (Mocked) for password recovery
    """
    generate_password_reset_otp(db, email=request.email)
    
    return {
        "message": "If an account with that email exists, we have sent a password reset OTP."
    }

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Verify the OTP and save the new password
    """
    verify_otp_and_reset_password(db, email=request.email, otp=request.otp, new_password=request.new_password)
    return {
        "message": "Password has been successfully reset."
    }