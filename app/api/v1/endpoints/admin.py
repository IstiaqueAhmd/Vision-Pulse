from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import List
from datetime import datetime, timedelta

from app.db.session import get_db
from app.core.config import settings
from app.models.user import User
from app.models.video import Video
from app.models.credit import CreditTransaction, CreditPackage
from app.schemas.credit import CreditPackageCreate, CreditPackageUpdate, CreditPackageResponse, GiveCreditRequest, GiveCreditResponse
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.models.logs import Logs
from app.models.payments import Payment
from app.api.deps import get_current_admin_user
from app.schemas.user import AdminUserResponse, UpdateUserRoleRequest
from app.schemas.subscription import AssignPlanRequest
from app.schemas.logs import LogsResponse
from app.schemas.payments import BillingOverviewResponse
from app.schemas.admin import AdminOverviewResponse
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate, FAQResponse
from app.models.policies import Policies
from app.schemas.policies import PoliciesCreate, PoliciesUpdate, PoliciesResponse

router = APIRouter()

@router.get("/users", response_model=List[AdminUserResponse])
def get_users(
    skip: int = Query(0, ge=0, description="Skip N users for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Limit to N users for pagination"),
    time_filter: str = Query("all", description="Filter users by registration date: all, 7d, 30d, 90d"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    query = db.query(User)
    
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
        
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
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
        plan_name = current_plan.name if current_plan else None
        
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
            created_at=user.created_at,
            subscription_plan=plan_name
        ))
    return result

@router.put("/{user_id}/role")
def update_user_role(
    user_id: int,
    role_update: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    new_role = role_update.role
    if new_role not in ["user", "admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    current_role = current_admin.role
    target_current_role = target_user.role

    # Rank hierarchy determines permission
    hierarchy = {"user": 1, "admin": 2, "super_admin": 3}

    # Can't change role of someone with a higher rank
    # Note: If target current role is invalid, treat it as least privileged (e.g. 1) to allow fixing, but for now we assume DB is consistent.
    if hierarchy.get(target_current_role, 1) > hierarchy.get(current_role, 1):
        raise HTTPException(status_code=403, detail="Not allowed to change role of a user with a higher rank")

    # Admins cannot assign super_admin role
    if current_role == "admin" and new_role == "super_admin":
        raise HTTPException(status_code=403, detail="Admins cannot assign super_admin role")

    target_user.role = new_role
    db.commit()
    db.refresh(target_user)

    return {
        "message": f"Successfully updated user role to {new_role}",
        "user_id": target_user.id,
        "new_role": new_role
    }


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

@router.post("/credit-packages", response_model=CreditPackageResponse)
def create_credit_package(
    package_in: CreditPackageCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin endpoint to create a new credit package.
    """
    existing_package = db.query(CreditPackage).filter(CreditPackage.name == package_in.name).first()
    if existing_package:
        raise HTTPException(status_code=400, detail="A credit package with this name already exists")

    package = CreditPackage(
        name=package_in.name,
        credits=package_in.credits,
        price=package_in.price,
        product_id=package_in.product_id,
        stripe_price_id=package_in.stripe_price_id,
        plan_type=package_in.plan_type,
        status=package_in.status
    )
    db.add(package)
    db.commit()
    db.refresh(package)
    return package

@router.get("/credit-packages", response_model=List[CreditPackageResponse])
def list_credit_packages(
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to list all credit packages.
    """
    packages = db.query(CreditPackage).order_by(CreditPackage.created_at.desc()).all()
    return packages

@router.get("/credit-packages/{package_id}", response_model=CreditPackageResponse)
def get_credit_package(
    package_id: int,
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to get a single credit package by ID.
    """
    package = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Credit package not found")
    return package

@router.put("/credit-packages/{package_id}", response_model=CreditPackageResponse)
def update_credit_package(
    package_id: int,
    package_in: CreditPackageUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin endpoint to update a credit package.
    """
    package = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Credit package not found")

    if (
        package_in.name is None
        and package_in.credits is None
        and package_in.price is None
        and package_in.product_id is None
        and package_in.stripe_price_id is None
        and package_in.plan_type is None
        and package_in.status is None
    ):
        raise HTTPException(status_code=400, detail="No fields provided for update")

    if package_in.name is not None:
        duplicate_name = db.query(CreditPackage).filter(
            CreditPackage.name == package_in.name,
            CreditPackage.id != package_id
        ).first()
        if duplicate_name:
            raise HTTPException(status_code=400, detail="A credit package with this name already exists")

    if package_in.name is not None:
        package.name = package_in.name
    if package_in.credits is not None:
        package.credits = package_in.credits
    if package_in.price is not None:
        package.price = package_in.price
    if package_in.product_id is not None:
        package.product_id = package_in.product_id
    if package_in.stripe_price_id is not None:
        package.stripe_price_id = package_in.stripe_price_id
    if package_in.plan_type is not None:
        package.plan_type = package_in.plan_type
    if package_in.status is not None:
        package.status = package_in.status

    db.commit()
    db.refresh(package)
    return package

@router.delete("/credit-packages/{package_id}")
def delete_credit_package(
    package_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Admin endpoint to delete a credit package.
    """
    package = db.query(CreditPackage).filter(CreditPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="Credit package not found")
    db.delete(package)
    db.commit()
    return {"message": "Credit package deleted successfully"}

@router.get("/billing", response_model=BillingOverviewResponse)
def get_billing_overview(
    skip: int = Query(0, ge=0, description="Skip N records for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit to N records for pagination"),
    time_filter: str = Query("all", description="Filter records by date: all, 7d, 30d, 90d"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    query = db.query(Payment)
    
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
            
        query = query.filter(Payment.created_at >= date_threshold)
    
    # Calculate totals — amount is stored in cents (Stripe convention), divide by 100 for dollars.
    # payment_type values in use: "credit_package", "subscription", "refund"
    revenue_q = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_type.in_(["credit_package", "subscription"]),
        Payment.status == "completed",
    )
    refunds_q = db.query(func.sum(Payment.amount)).filter(Payment.payment_type == "refund")

    if time_filter != "all":
        revenue_q = revenue_q.filter(Payment.created_at >= date_threshold)
        refunds_q = refunds_q.filter(Payment.created_at >= date_threshold)

    total_revenue = (revenue_q.scalar() or 0) 
    refund_amount = (refunds_q.scalar() or 0)
    net_revenue = total_revenue - refund_amount
    
    records = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    
    return BillingOverviewResponse(
        total_revenue=float(total_revenue),
        refund_amount=float(refund_amount),
        net_revenue=float(net_revenue),
        records=records
    )

@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    time_filter: str = Query("all", description="Filter records by date: all, 7d, 30d, 90d"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    now = datetime.utcnow()
    date_threshold = None
    if time_filter != "all":
        if time_filter == "7d":
            date_threshold = now - timedelta(days=7)
        elif time_filter == "30d":
            date_threshold = now - timedelta(days=30)
        elif time_filter == "90d":
            date_threshold = now - timedelta(days=90)
        else:
            raise HTTPException(status_code=400, detail="Invalid time_filter value. Use 'all', '7d', '30d', or '90d'.")

    users_q = db.query(User).filter(User.role == "user")
    active_users_q = db.query(User).filter(User.role == "user", User.status == "active")
    videos_q = db.query(Video)
    credits_q = db.query(func.sum(CreditTransaction.amount)).filter(CreditTransaction.type == "spend")
    revenue_q = db.query(func.sum(Payment.amount)).filter(
        Payment.payment_type.in_(["credit_package", "subscription"]),
        Payment.status == "completed",
    )
    refunds_q = db.query(func.count(Payment.id)).filter(Payment.payment_type == "refund")

    # Time series queries
    credits_time_q = db.query(
        cast(CreditTransaction.created_at, Date).label('date'),
        func.sum(CreditTransaction.amount).label('count')
    ).filter(CreditTransaction.type == "spend")

    videos_time_q = db.query(
        cast(Video.created_at, Date).label('date'),
        func.count(Video.id).label('count')
    )

    plan_dist_q = db.query(
        SubscriptionPlan.name.label('plan_name'),
        func.count(UserSubscription.user_id).label('user_count')
    ).join(SubscriptionPlan, UserSubscription.plan_id == SubscriptionPlan.id)\
     .filter(UserSubscription.status == "active")

    # Apply global time filter 
    if date_threshold:
        users_q = users_q.filter(User.created_at >= date_threshold)
        active_users_q = active_users_q.filter(User.created_at >= date_threshold)
        videos_q = videos_q.filter(Video.created_at >= date_threshold)
        credits_q = credits_q.filter(CreditTransaction.created_at >= date_threshold)
        revenue_q = revenue_q.filter(Payment.created_at >= date_threshold)
        refunds_q = refunds_q.filter(Payment.created_at >= date_threshold)
        credits_time_q = credits_time_q.filter(CreditTransaction.created_at >= date_threshold)
        videos_time_q = videos_time_q.filter(Video.created_at >= date_threshold)
        plan_dist_q = plan_dist_q.filter(UserSubscription.start_date >= date_threshold)

    # Resolve scalars
    total_users = users_q.count() or 0
    active_users = active_users_q.count() or 0
    total_videos = videos_q.count() or 0
    credits_consumed = credits_q.scalar() or 0
    total_revenue = revenue_q.scalar() or 0.0
    refunds_issued = refunds_q.scalar() or 0

    # Execute time series and grouping
    credits_time_results = credits_time_q.group_by('date').order_by('date').all()
    videos_time_results = videos_time_q.group_by('date').order_by('date').all()
    plan_dist_results = plan_dist_q.group_by(SubscriptionPlan.name).all()

    def format_date(d):
        return d.strftime("%a") if time_filter == "7d" else str(d)

    credits_used_over_time = [{"date": format_date(r.date), "count": float(r.count)} for r in credits_time_results]
    videos_generated_over_time = [{"date": format_date(r.date), "count": float(r.count)} for r in videos_time_results]
    plan_distribution = [{"plan_name": r.plan_name, "user_count": r.user_count} for r in plan_dist_results]

    return AdminOverviewResponse(
        total_users=total_users,
        active_users=active_users,
        total_videos_generated=total_videos,
        credits_consumed=credits_consumed,
        total_revenue=float(total_revenue),
        refunds_issued=refunds_issued,
        credits_used_over_time=credits_used_over_time,
        videos_generated_over_time=videos_generated_over_time,
        plan_distribution=plan_distribution
    )


@router.post("/faq", response_model=FAQResponse)
def create_faq(
    faq_in: FAQCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Create a new FAQ.
    """
    faq = FAQ(
        Question=faq_in.Question,
        Answer=faq_in.Answer
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq


@router.put("/faq/{faq_id}", response_model=FAQResponse)
def update_faq(
    faq_id: int,
    faq_in: FAQUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Update an existing FAQ entry.
    """
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
        
    if faq_in.Question is not None:
        faq.Question = faq_in.Question
    if faq_in.Answer is not None:
        faq.Answer = faq_in.Answer
        
    db.commit()
    db.refresh(faq)
    return faq


@router.delete("/faq/{faq_id}")
def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete a specific FAQ entry.
    """
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
        
    db.delete(faq)
    db.commit()
    return {"message": "FAQ deleted successfully"}

@router.get("/faq", response_model=List[FAQResponse])
def get_faqs(
    skip: int = Query(0, ge=0, description="Skip N records for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Limit to N records for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get all FAQs.
    """
    faqs = db.query(FAQ).offset(skip).limit(limit).all()
    return faqs

@router.get("/policies", response_model=List[PoliciesResponse])
def get_policies(db: Session = Depends(get_db)):
    """
    Get all policies records.
    """
    policies = db.query(Policies).all()
    return policies

@router.post("/policies", response_model=PoliciesResponse)
def create_policies(
    policies_in: PoliciesCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Create a new policies record.
    """
    policy = Policies(
        privacy_policy=policies_in.privacy_policy,
        terms_of_service=policies_in.terms_of_service,
        refund_policy=policies_in.refund_policy,
        updated_by=current_admin.id
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy

@router.put("/policies/{policy_id}", response_model=PoliciesResponse)
def update_policies(
    policy_id: int,
    policies_in: PoliciesUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Update an existing policies record.
    """
    policy = db.query(Policies).filter(Policies.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policies record not found")
        
    if policies_in.privacy_policy is not None:
        policy.privacy_policy = policies_in.privacy_policy
    if policies_in.terms_of_service is not None:
        policy.terms_of_service = policies_in.terms_of_service
    if policies_in.refund_policy is not None:
        policy.refund_policy = policies_in.refund_policy
        
    policy.updated_by = current_admin.id
    db.commit()
    db.refresh(policy)
    return policy

@router.delete("/policies/{policy_id}")
def delete_policies(
    policy_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Delete a specific policies record.
    """
    policy = db.query(Policies).filter(Policies.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policies record not found")
        
    db.delete(policy)
    db.commit()
    return {"message": "Policies record deleted successfully"}


@router.post("/users/{user_id}/give-credit", response_model=GiveCreditResponse)
def give_credit_to_user(
    user_id: int,
    payload: GiveCreditRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Grant a specified number of credits to a user.
    Only accessible by admin or super_admin users.
    """
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be a positive integer")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Add credits to the user balance
    user.credits += payload.amount

    # Record the transaction
    transaction = CreditTransaction(
        user_id=user.id,
        amount=payload.amount,
        type="admin_grant",
        source="admin_grant",
        reference_id=payload.note
    )
    db.add(transaction)
    db.commit()
    db.refresh(user)
    db.refresh(transaction)

    return GiveCreditResponse(
        message=f"Successfully granted {payload.amount} credits to user '{user.email}'",
        user_id=user.id,
        credits_granted=payload.amount,
        new_balance=user.credits,
        transaction_id=transaction.id
    )

