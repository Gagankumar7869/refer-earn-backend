from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.entities import User
from app.schemas.referral import (
    MemberMeDashboardResponse,
    MemberMilestonesResponse,
    PaginatedTransactionsResponse,
    ReferralCreateRequest,
    ReferralResponse,
)
from app.services.referral_service import ReferralService

router = APIRouter(prefix="/api/v1/referrals", tags=["Member Referrals"])


@router.post(
    "",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_referral(
    payload: ReferralCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReferralService(db)
    return service.create_referral(current_user=current_user, referral_code=payload.referral_code)


@router.get("/me", response_model=MemberMeDashboardResponse)
def get_my_referral_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReferralService(db)
    return service.get_member_dashboard(current_user=current_user)


@router.get("/milestones", response_model=MemberMilestonesResponse)
def get_my_milestones(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReferralService(db)
    return service.get_member_milestones(current_user=current_user)


@router.get("/transactions", response_model=PaginatedTransactionsResponse)
def get_my_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReferralService(db)
    return service.get_member_transactions(
        current_user=current_user, page=page, page_size=page_size
    )