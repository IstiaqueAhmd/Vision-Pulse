from sqlalchemy.orm import Session
from app.models.subscription import SubscriptionPlan
from app.schemas.subscription import SubscriptionPlanCreate, SubscriptionPlanUpdate
from typing import Optional, List

def create_plan(db: Session, plan_in: SubscriptionPlanCreate) -> SubscriptionPlan:
    db_plan = SubscriptionPlan(
        name=plan_in.name,
        monthly_price=plan_in.monthly_price,
        product_id=plan_in.product_id,
        monthly_credits=plan_in.monthly_credits,
        video_limit_per_month=plan_in.video_limit_per_month,
        priority_level=plan_in.priority_level,
        commercial_usage_allowed=plan_in.commercial_usage_allowed,
        max_video_duration=plan_in.max_video_duration,
        plan_status=plan_in.plan_status,
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

def get_plan(db: Session, plan_id: int) -> Optional[SubscriptionPlan]:
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()

def get_plans(db: Session, skip: int = 0, limit: int = 100) -> List[SubscriptionPlan]:
    return db.query(SubscriptionPlan).offset(skip).limit(limit).all()

def update_plan(db: Session, plan_id: int, plan_in: SubscriptionPlanUpdate) -> Optional[SubscriptionPlan]:
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        return None
    
    update_data = plan_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_plan, field, value)
    
    db.commit()
    db.refresh(db_plan)
    return db_plan

def delete_plan(db: Session, plan_id: int) -> Optional[SubscriptionPlan]:
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if db_plan:
        db.delete(db_plan)
        db.commit()
    return db_plan

def toggle_plan_status(db: Session, plan_id: int) -> Optional[SubscriptionPlan]:
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        return None
    
    db_plan.plan_status = "inactive" if db_plan.plan_status == "active" else "active"
    db.commit()
    db.refresh(db_plan)
    return db_plan
