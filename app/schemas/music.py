from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserBase(BaseModel):
    name: str = Field(..., description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")

class UserResponse(UserBase):
    id: int
    credits: int
    subscription_plan: str
    created_at: datetime

    class Config:
        from_attributes = True

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)

class GoogleAuthRequest(BaseModel):
    token: str = Field(..., description="Google ID Token from the frontend sign-in flow")
