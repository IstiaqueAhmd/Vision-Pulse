from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.api.deps import get_current_admin_user, get_current_user
from app.models.user import User
from app.schemas.subscription import SubscriptionPlanCreate, SubscriptionPlanInDB, SubscriptionPlanUpdate
from app.services import subscription_service

router = APIRouter()

@router.post("/", response_model=SubscriptionPlanInDB, status_code=status.HTTP_201_CREATED)
def create_subscription_plan(
    *,
    db: Session = Depends(get_db),
    plan_in: SubscriptionPlanCreate,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    Create a new subscription plan (Admin only).
    """
    from app.models.subscription import SubscriptionPlan
    existing_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_in.name).first()
    if existing_plan:
        raise HTTPException(status_code=400, detail="Plan with this name already exists.")
    
    plan = subscription_service.create_plan(db=db, plan_in=plan_in)
    return plan

@router.get("/", response_model=List[SubscriptionPlanInDB])
def read_subscription_plans(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve all subscription plans. Publicly accessible.
    """
    plans = subscription_service.get_plans(db=db, skip=skip, limit=limit)
    return plans

@router.get("/{plan_id}", response_model=SubscriptionPlanInDB)
def read_subscription_plan(
    plan_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve specific subscription plan by ID.
    """
    plan = subscription_service.get_plan(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    return plan

@router.put("/{plan_id}", response_model=SubscriptionPlanInDB)
def update_subscription_plan(
    *,
    db: Session = Depends(get_db),
    plan_id: int,
    plan_in: SubscriptionPlanUpdate,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    Update a subscription plan (Admin only).
    """
    plan = subscription_service.get_plan(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    
    updated_plan = subscription_service.update_plan(db=db, plan_id=plan_id, plan_in=plan_in)
    return updated_plan

@router.delete("/{plan_id}", response_model=SubscriptionPlanInDB)
def delete_subscription_plan(
    *,
    db: Session = Depends(get_db),
    plan_id: int,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    Delete a subscription plan (Admin only).
    """
    plan = subscription_service.delete_plan(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    return plan

@router.put("/{plan_id}/toggle-status", response_model=SubscriptionPlanInDB)
def toggle_subscription_plan_status(
    *,
    db: Session = Depends(get_db),
    plan_id: int,
    current_admin: User = Depends(get_current_admin_user),
):
    """
    Toggle a subscription plan's status between active and inactive (Admin only).
    """
    plan = subscription_service.toggle_plan_status(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    return plan
