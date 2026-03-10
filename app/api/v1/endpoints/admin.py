from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta

from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.video import Video
from app.models.credit import CreditTransaction, CreditPackage
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.logs import Logs
from app.api.deps import get_current_admin_user
from app.schemas.user import AdminUserResponse
from app.schemas.subscription import AssignPlanRequest
from app.schemas.logs import LogsResponse

router = APIRouter()

@router.get("/users", response_model=List[AdminUserResponse])
def get_users(
    skip: int = Query(0, ge=0, description="Skip N users for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Limit to N users for pagination"),
    time_filter: str = Query("all", description="Filter users by registration date: all, 7d, 30d, 90d"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    query = db.query(User).filter(User.role == "user")
    
    # Apply time filter
    if time_filter != "all":
        now = datetime.utcnow()
        if time_filter == "7d":
            date_threshold = now - timedelta(days=7)
        elif time_filter == "30d":
            date_threshold = now - timedelta(days=30)
        elif time_filter == "90d":
            date_threshold = now - timedelta(days=90)
        else:
            raise HTTPException(status_code=400, detail="Invalid time_filter value. Use 'all', '7d', '30d', or '90d'.")
        
        query = query.filter(User.created_at >= date_threshold)
        
    users = query.offset(skip).limit(limit).all()
    
    if not users:
        return []
        
    user_ids = [u.id for u in users]
    
    # 1. Fetch Videos Count per user
    video_counts = db.query(
        Video.user_id, func.count(Video.id)
    ).filter(Video.user_id.in_(user_ids)).group_by(Video.user_id).all()
    video_map = {uid: count for uid, count in video_counts}
    
    # 2. Prepare Payment and Credit Lookup Data
    plans = db.query(SubscriptionPlan).all()
    plan_map = {p.id: p for p in plans}
    
    # Pre-fetch user's active subscriptions
    active_subs = db.query(UserSubscription).filter(
        UserSubscription.user_id.in_(user_ids),
        UserSubscription.status == "active"
    ).all()
    active_sub_map = {sub.user_id: sub for sub in active_subs}
    
    packages = db.query(CreditPackage).all()
    pkg_map = {p.credits: p.price for p in packages}
    
    transactions = db.query(CreditTransaction).filter(
        CreditTransaction.user_id.in_(user_ids),
        CreditTransaction.type.in_(["purchase", "subscription", "spend"])
    ).all()
    
    user_tx_map = {uid: {'purchase_amount': 0.0, 'sub_count': 0, 'spend': 0} for uid in user_ids}
    for tx in transactions:
        if tx.type == "spend":
            user_tx_map[tx.user_id]['spend'] += tx.amount
        elif tx.type == "purchase":
            price = pkg_map.get(tx.amount, 0.0) 
            user_tx_map[tx.user_id]['purchase_amount'] += price
        elif tx.type == "subscription":
            user_tx_map[tx.user_id]['sub_count'] += 1

    # 3. Build Result List
    result = []
    for user in users:
        active_sub = active_sub_map.get(user.id)
        current_plan = plan_map.get(active_sub.plan_id) if active_sub else None
        plan_price = current_plan.monthly_price if current_plan else 0.0
        
        tx_data = user_tx_map[user.id]
        
        total_payment = tx_data['purchase_amount'] + (tx_data['sub_count'] * plan_price)
        credits_used = tx_data['spend']
        videos_gen = video_map.get(user.id, 0)
        
        result.append(AdminUserResponse(
            name=user.name,
            email=user.email,
            id=user.id,
            is_verified=user.is_verified,
            total_payment_made=total_payment,
            credits_left=user.credits,
            credits_used=credits_used,
            total_videos_generated=videos_gen,
            status=user.status,
            role=user.role,
            created_at=user.created_at
        ))
    return result

@router.post("/assign-plan")
def assign_subscription_plan(
    request: AssignPlanRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    # 1. Verify User
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Verify Plan
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == request.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # 3. Handle existing active subscriptions
    active_subscriptions = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "active"
    ).all()
    
    now = datetime.utcnow()
    for sub in active_subscriptions:
        sub.status = "expired"
        sub.end_date = now

    # 4. Create new subscription record
    end_date = now + timedelta(days=request.duration_days)
    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        start_date=now,
        end_date=end_date,
        status="active"
    )
    db.add(new_subscription)

    # 5. Update User record (No longer updating string property)
    user.credits += plan.monthly_credits

    # 6. Commit changes
    db.commit()

    return {
        "message": f"Successfully assigned plan '{plan.name}' to user '{user.email}'",
        "user_id": user.id,
        "new_plan": plan.name,
        "new_credits_balance": user.credits,
        "expires_at": end_date
    }

@router.get("/logs", response_model=List[LogsResponse])
def get_logs(
    skip: int = Query(0, ge=0, description="Skip N logs for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit to N logs for pagination"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Get all logs paginated, ordered by date_time descending
    """
    logs = db.query(Logs).order_by(Logs.date_time.desc()).offset(skip).limit(limit).all()
    return logs

@router.delete("/logs/{log_id}")
def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete a specific log by ID
    """
    log = db.query(Logs).filter(Logs.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
        
    db.delete(log)
    db.commit()
    
    return {"message": "Log deleted successfully"}