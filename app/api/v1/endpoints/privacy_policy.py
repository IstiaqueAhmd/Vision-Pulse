from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.privacy_policy import PrivacyPolicy
from app.schemas.privacy_policy import PrivacyPolicyCreate, PrivacyPolicyUpdate, PrivacyPolicyResponse
from app.api.deps import get_current_admin_user

router = APIRouter()

@router.get("/", response_model=PrivacyPolicyResponse)
def get_privacy_policy(db: Session = Depends(get_db)):
    policy = db.query(PrivacyPolicy).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Privacy policy not found",
        )
    return policy

@router.post("/", response_model=PrivacyPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_privacy_policy(
    policy_in: PrivacyPolicyCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
):
    # Check if a policy already exists
    existing_policy = db.query(PrivacyPolicy).first()
    if existing_policy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Privacy policy already exists. Use PUT to update it.",
        )
    
    new_policy = PrivacyPolicy(content=policy_in.content)
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy

@router.put("/", response_model=PrivacyPolicyResponse)
def update_privacy_policy(
    policy_in: PrivacyPolicyUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin_user)
):
    policy = db.query(PrivacyPolicy).first()
    if not policy:
        # If not found, create one automatically
        policy = PrivacyPolicy(content=policy_in.content)
        db.add(policy)
    else:
        policy.content = policy_in.content
        
    db.commit()
    db.refresh(policy)
    return policy
