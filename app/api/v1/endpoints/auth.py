from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest, GoogleAuthRequest
from app.schemas.token import Token, LoginResponse
from app.services.auth_service import create_user, generate_password_reset_otp, verify_otp, reset_password, authenticate_google_user
from app.services.google_auth_service import verify_google_token
from app.api.deps import get_current_user, oauth2_scheme

router = APIRouter()

# In-memory blocklist for revoked tokens.
# For production, consider using Redis or a database table instead.
token_blocklist: set[str] = set()

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

@router.post("/login", response_model=LoginResponse)
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
        "user": user,
    }

@router.post("/google", response_model=LoginResponse)
def google_auth(
    request: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Accepts a Google ID token from the frontend, verifies it against Google's API,
    and logs the user in (or signs them up if it's their first time).
    """
    # 1. Verify the Google Token
    google_user_info = verify_google_token(request.token)
    
    # 2. Get or create the user in our database
    user = authenticate_google_user(
        db=db, 
        email=google_user_info["email"], 
        name=google_user_info["name"]
    )
    
    # 3. Issue our application's JWT access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    return {
        "access_token": create_access_token(
            subject=user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user": user,
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

@router.post("/verify-otp")
def verify_otp_endpoint(
    request: VerifyOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Verify the OTP sent to the user's email.
    """
    verify_otp(db, email=request.email, otp=request.otp)
    return {
        "message": "OTP verified successfully. You may now reset your password."
    }

@router.post("/reset-password")
def reset_password_endpoint(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Save the new password (requires prior OTP verification).
    """
    reset_password(db, email=request.email, new_password=request.new_password)
    return {
        "message": "Password has been successfully reset."
    }

@router.post("/logout")
def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
):
    """
    Logout the current user by blocklisting their JWT token.
    The token will be rejected on any subsequent request.
    """
    token_blocklist.add(token)
    return {
        "message": "Successfully logged out."
    }