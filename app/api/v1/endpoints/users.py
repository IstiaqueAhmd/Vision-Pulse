import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, Form, UploadFile
from sqlalchemy import func, extract, String
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.notification import Notification, NotificationSettings
from app.models.user import User
from app.models.video import Video
from app.models.credit import CreditTransaction
from app.models.subscription import UserSubscription
from app.schemas.notification import NotificationResponse, NotificationCountResponse, NotificationSettingsUpdateRequest, NotificationSettingsUpdateResponse
from app.schemas.user import UserResponse, UpdateUserStatusRequest, DashboardResponse, RecentVideoSummary, CreditDataPoint, CreditOverviewChart
from app.schemas.support import ContactSupportRequest, ContactSupportResponse
from app.schemas.credit import CreditWalletResponse, CreditTransactionResponse
from app.api.deps import get_current_user, get_current_admin_user
from app.services.email_service import send_support_email

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns an aggregated dashboard overview for the authenticated user:
    - Credit usage, remaining balance, and subscription reset date
    - Total videos generated and videos generated this month
    - The 3 most recent videos
    - Credit overview filtered by this month and all time
    """
    now = datetime.now(timezone.utc)
    current_month = now.month
    current_year = now.year

    # ── Credits used (all time, absolute value) ────────────────────
    credits_used_raw = (
        db.query(func.coalesce(func.sum(CreditTransaction.amount), 0))
        .filter(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.type == "spend",
        )
        .scalar()
    ) or 0
    credits_used = abs(credits_used_raw)

    credits_remaining = current_user.credits

    # ── Subscription reset date ────────────────────────────────────
    active_sub = (
        db.query(UserSubscription)
        .filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.status == "active",
        )
        .order_by(UserSubscription.created_at.desc())
        .first()
    )
    credits_reset_date = active_sub.renewal_date if active_sub else None

    # ── Video statistics ───────────────────────────────────────────
    total_videos = (
        db.query(func.count(Video.id))
        .filter(Video.user_id == current_user.id)
        .scalar()
    ) or 0

    videos_this_month = (
        db.query(func.count(Video.id))
        .filter(
            Video.user_id == current_user.id,
            extract("month", Video.created_at) == current_month,
            extract("year", Video.created_at) == current_year,
        )
        .scalar()
    ) or 0

    # ── Recent videos (latest 3) ──────────────────────────────────
    recent_video_rows = (
        db.query(Video)
        .filter(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
        .limit(3)
        .all()
    )
    recent_videos = [RecentVideoSummary.model_validate(v) for v in recent_video_rows]

    # ── Credit overview: THIS MONTH (daily data points) ─────────────
    import calendar
    days_in_month = calendar.monthrange(current_year, current_month)[1]

    # Query daily spend totals for the current month
    daily_rows = (
        db.query(
            func.cast(func.date(CreditTransaction.created_at), String).label("day"),
            func.coalesce(func.sum(CreditTransaction.amount), 0).label("total"),
        )
        .filter(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.type == "spend",
            extract("month", CreditTransaction.created_at) == current_month,
            extract("year", CreditTransaction.created_at) == current_year,
        )
        .group_by(func.date(CreditTransaction.created_at))
        .all()
    )
    daily_map = {row.day: abs(row.total) for row in daily_rows}

    this_month_data = []
    for day_num in range(1, days_in_month + 1):
        date_str = f"{current_year}-{current_month:02d}-{day_num:02d}"
        this_month_data.append(CreditDataPoint(
            date=date_str,
            credits_used=daily_map.get(date_str, 0),
        ))

    # ── Credit overview: ALL TIME (monthly data points) ───────────
    monthly_rows = (
        db.query(
            extract("year", CreditTransaction.created_at).label("yr"),
            extract("month", CreditTransaction.created_at).label("mo"),
            func.coalesce(func.sum(CreditTransaction.amount), 0).label("total"),
        )
        .filter(
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.type == "spend",
        )
        .group_by("yr", "mo")
        .order_by("yr", "mo")
        .all()
    )
    all_time_data = [
        CreditDataPoint(
            date=f"{int(row.yr)}-{int(row.mo):02d}",
            credits_used=abs(row.total),
        )
        for row in monthly_rows
    ]

    return DashboardResponse(
        credits_used=credits_used,
        credits_remaining=credits_remaining,
        credits_reset_date=credits_reset_date,
        total_videos=total_videos,
        videos_this_month=videos_this_month,
        recent_videos=recent_videos,
        credits_overview_this_month=CreditOverviewChart(
            label="this_month", data=this_month_data,
        ),
        credits_overview_all_time=CreditOverviewChart(
            label="all_time", data=all_time_data,
        ),
    )


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
        from app.core.config import settings
        # Ensure the directory exists
        profile_dir = settings.OUTPUT_DIR / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate new file name
        ext = os.path.splitext(profile_image.filename)[1]
        if not ext:
            ext = ".png" # fallback
            
        unique_filename = f"{uuid.uuid4()}{ext}"
        file_path = profile_dir / unique_filename
        
        # Save the uploaded file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)
            
        # Optional: Delete old profile picture if it was stored locally
        if current_user.profile_image_url and current_user.profile_image_url.startswith("/outputs/profiles/"):
            old_filename = current_user.profile_image_url.split("/")[-1]
            old_file_path = profile_dir / old_filename
            if old_file_path.exists():
                try:
                    old_file_path.unlink()
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

@router.get("/notifications/settings", response_model=NotificationSettingsUpdateResponse)
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = db.query(NotificationSettings).filter(NotificationSettings.user_id == current_user.id).first()
    if not settings:
        settings = NotificationSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.put("/notifications/settings", response_model=NotificationSettingsUpdateResponse)
def update_notification_settings(
    request: NotificationSettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = db.query(NotificationSettings).filter(NotificationSettings.user_id == current_user.id).first()
    if not settings:
        settings = NotificationSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.commit()
    db.refresh(settings)
    return settings


@router.post("/support/contact", response_model=ContactSupportResponse)
def contact_support(
    request: ContactSupportRequest
):
    """
    Submit a support message which is sent as an email to the support team.
    """
    success = send_support_email(
        fullname=request.fullname,
        user_email=request.email,
        subject=request.subject,
        topic=request.topic,
        message=request.message
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send support email")
        
    return ContactSupportResponse(
        succss=True,
        inquiry=request
    )


@router.get("/settings/credit-wallet", response_model=CreditWalletResponse)
def get_credit_wallet(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the authenticated user's credit wallet overview with paginated transaction history.

    Query params:
    - **page**: page number, 1-indexed (default 1)
    - **page_size**: records per page, 1–100 (default 20)
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if not (1 <= page_size <= 100):
        raise HTTPException(status_code=400, detail="page_size must be between 1 and 100")

    # Sum of all credits earned / purchased / granted
    purchased = db.query(func.coalesce(func.sum(CreditTransaction.amount), 0)).filter(
        CreditTransaction.user_id == current_user.id,
        CreditTransaction.type.in_(["earn", "purchase", "subscription"]),
    ).scalar() or 0

    # Sum of all credits spent (normalised to a positive number)
    used_raw = db.query(func.coalesce(func.sum(CreditTransaction.amount), 0)).filter(
        CreditTransaction.user_id == current_user.id,
        CreditTransaction.type == "spend",
    ).scalar() or 0
    used = abs(used_raw)

    # Total row count for this user (used to compute total_pages)
    total_transactions = db.query(func.count(CreditTransaction.id)).filter(
        CreditTransaction.user_id == current_user.id,
    ).scalar() or 0

    import math
    total_pages = math.ceil(total_transactions / page_size) if total_transactions else 1

    transactions = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == current_user.id)
        .order_by(CreditTransaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CreditWalletResponse(
        user_credits=current_user.credits,
        purchased=purchased,
        used=used,
        remaining=current_user.credits,
        page=page,
        page_size=page_size,
        total_transactions=total_transactions,
        total_pages=total_pages,
        transaction_history=transactions,
    )
