from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserBase(BaseModel):
    name: str = Field(..., description="Full name of the user")
    email: EmailStr = Field(..., description="Valid email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")

class UserResponse(UserBase):
    id: int
    profile_image_url: str | None = None
    is_verified: bool
    credits: int
    status: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: str | None = Field(None, description="Full name of the user")
    profile_image_url: str | None = Field(None, description="URL of the user's profile image")

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResendOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

class VerifyOTPSimpleRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8)

class GoogleAuthRequest(BaseModel):
    token: str = Field(..., description="Google ID Token from the frontend sign-in flow")

class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)

class AdminUserResponse(UserBase):
    id: int
    is_verified: bool
    total_payment_made: float
    credits_left: int
    credits_used: int
    total_videos_generated: int
    status: str
    role: str
    created_at: datetime
    subscription_plan: str | None = None

    class Config:
        from_attributes = True

class UpdateUserStatusRequest(BaseModel):
    status: str = Field(..., description="User status: 'active' or 'suspended'")

class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., description="User role: 'user', 'admin', or 'super_admin'")


# ── Dashboard schemas ──────────────────────────────────────────────

class RecentVideoSummary(BaseModel):
    id: int
    title: str
    thumbnail_path: str | None = None
    status: str
    duration: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True

class CreditDataPoint(BaseModel):
    """A single data point for the credits-used chart."""
    date: str = Field(..., description="Date label, e.g. '2026-06-01' (daily) or '2026-06' (monthly)")
    credits_used: int = Field(0, description="Credits spent in this period (positive number)")

class CreditOverviewChart(BaseModel):
    """Time-series chart data for credits used over time."""
    label: str = Field(..., description="'this_month' or 'all_time'")
    data: list[CreditDataPoint]

class DashboardResponse(BaseModel):
    # Credit information
    credits_used: int
    credits_remaining: int
    credits_reset_date: datetime | None = Field(None, description="Next subscription renewal date")

    # Video statistics
    total_videos: int
    videos_this_month: int
    recent_videos: list[RecentVideoSummary]

    # Credit overview charts
    credits_overview_this_month: CreditOverviewChart
    credits_overview_all_time: CreditOverviewChart

