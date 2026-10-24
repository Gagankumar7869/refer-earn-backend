from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.entities import User
from app.schemas.referral import (
    AdminReferralDetailResponse,
    AdminRejectRequest,
    AdminReverseRequest,
    PaginatedAdminReferralsResponse,
    ReconciliationReportResponse,
    ReferralResponse,
)
from app.services.admin_referral_service import AdminReferralService
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/api/v1/referrals/admin", tags=["Admin Referrals"])


@router.get("/list", response_model=PaginatedAdminReferralsResponse)
def list_all_referrals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="PENDING, SUCCESSFUL, REJECTED, REVERSED"),
    referrer_id: Optional[int] = Query(default=None, ge=1),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = AdminReferralService(db)
    return service.list_referrals(
        page=page,
        page_size=page_size,
        status_str=status,
        referrer_id=referrer_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.post("/approve/{referred_user_id}", response_model=ReferralResponse)
def approve_referral(
    referred_user_id: int = Path(..., ge=1),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = AdminReferralService(db)
    return service.approve_referral(admin_user=admin_user, referred_user_id=referred_user_id)


@router.post("/reject/{referred_user_id}", response_model=ReferralResponse)
def reject_referral(
    referred_user_id: int = Path(..., ge=1),
    payload: Optional[AdminRejectRequest] = Body(default=None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = AdminReferralService(db)
    reason = payload.reason if payload else "Rejected by admin"
    return service.reject_referral(
        admin_user=admin_user, referred_user_id=referred_user_id, reason=reason
    )


@router.post("/reverse/{referred_user_id}", response_model=ReferralResponse)
def reverse_referral(
    referred_user_id: int = Path(..., ge=1),
    payload: Optional[AdminReverseRequest] = Body(default=None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = AdminReferralService(db)
    reason = payload.reason if payload else "Reversed by admin"
    return service.reverse_referral(
        admin_user=admin_user, referred_user_id=referred_user_id, reason=reason
    )


@router.post("/reconcile", response_model=ReconciliationReportResponse)
def reconcile_rewards(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = ReconciliationService(db)
    return service.run_reconciliation(admin_user=admin_user)


@router.get(
    "/reconciliation-report/{audit_id}",
    response_model=ReconciliationReportResponse,
)
def get_reconciliation_report(
    audit_id: int = Path(..., ge=1),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = ReconciliationService(db)
    return service.get_report_by_id(audit_id=audit_id)


@router.get("/{referral_id}", response_model=AdminReferralDetailResponse)
def get_referral_details(
    referral_id: int = Path(..., ge=1),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = AdminReferralService(db)
    return service.get_referral_details(referral_id=referral_id)
