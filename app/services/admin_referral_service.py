from datetime import datetime, timezone
import math
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.entities import (
    AuditAction,
    AuditLog,
    LedgerEntryType,
    MilestoneDefinition,
    Referral,
    ReferralStatus,
    RewardLedger,
    User,
    UserMilestone,
)
from app.repositories.referral_repository import ReferralRepository
from app.schemas.referral import (
    AdminReferralDetailResponse,
    AuditHistoryItem,
    PaginatedAdminReferralsResponse,
    ReferralResponse,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AdminReferralService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReferralRepository(db)

    def list_referrals(
        self,
        page: int,
        page_size: int,
        status_str: Optional[str] = None,
        referrer_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> PaginatedAdminReferralsResponse:
        status_enum: Optional[ReferralStatus] = None
        if status_str is not None:
            try:
                status_enum = ReferralStatus(status_str.strip().upper())
            except ValueError:
                raise ValidationError(
                    message=f"Invalid status filter '{status_str}'. Must be one of: PENDING, SUCCESSFUL, REJECTED, REVERSED",
                    code="INVALID_STATUS_FILTER",
                )

        if from_date and to_date and from_date > to_date:
            raise ValidationError(
                message="from_date cannot be later than to_date",
                code="INVALID_DATE_RANGE",
            )

        items, total = self.repo.list_admin_referrals(
            page=page,
            page_size=page_size,
            status=status_enum,
            referrer_id=referrer_id,
            from_date=from_date,
            to_date=to_date,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedAdminReferralsResponse(
            items=[ReferralResponse.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        )

    def approve_referral(self, admin_user: User, referred_user_id: int) -> ReferralResponse:
        try:
            referral = self.repo.get_referral_by_referred_user(
                referred_user_id=referred_user_id, for_update=True
            )
            if not referral:
                raise NotFoundError(
                    message=f"Referral for referred_user_id={referred_user_id} was not found",
                    code="REFERRAL_NOT_FOUND",
                )

            if referral.status != ReferralStatus.PENDING:
                raise ConflictError(
                    message=f"Cannot approve referral in '{referral.status.value}' state. Only PENDING referrals can be approved.",
                    code="INVALID_LIFECYCLE_TRANSITION",
                )

            balance_row = self.repo.get_or_create_balance(
                user_id=referral.referrer_id, for_update=True
            )

            reward_points = settings.REFERRAL_REWARD_POINTS
            new_balance = balance_row.balance + reward_points
            new_successful_count = balance_row.successful_referral_count + 1
            now = utcnow()

            from_status = referral.status.value
            referral.status = ReferralStatus.SUCCESSFUL
            referral.approved_at = now
            referral.reviewed_by = admin_user.id

            ledger_entry = RewardLedger(
                user_id=referral.referrer_id,
                referral_id=referral.id,
                entry_type=LedgerEntryType.REFERRAL_CREDIT,
                points=reward_points,
                balance_after=new_balance,
                idempotency_key=f"referral:{referral.id}:approval",
                created_at=now,
            )
            self.db.add(ledger_entry)

            balance_row.balance = new_balance
            balance_row.successful_referral_count = new_successful_count
            balance_row.updated_at = now

            self._evaluate_and_grant_milestones(
                user_id=referral.referrer_id,
                successful_count=new_successful_count,
                now=now,
            )

            audit = AuditLog(
                actor_id=admin_user.id,
                action=AuditAction.APPROVE,
                target_type="REFERRAL",
                target_id=referral.id,
                referral_id=referral.id,
                from_status=from_status,
                to_status=ReferralStatus.SUCCESSFUL.value,
                reason="Approved by admin",
                created_at=now,
            )
            self.db.add(audit)

            self.db.commit()
            self.db.refresh(referral)
            return ReferralResponse.model_validate(referral)
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(
                message="Referral approval already processed or conflicting concurrent update",
                code="IDEMPOTENCY_CONFLICT",
            )
        except Exception:
            self.db.rollback()
            raise

    def reject_referral(
        self, admin_user: User, referred_user_id: int, reason: Optional[str] = None
    ) -> ReferralResponse:
        try:
            referral = self.repo.get_referral_by_referred_user(
                referred_user_id=referred_user_id, for_update=True
            )
            if not referral:
                raise NotFoundError(
                    message=f"Referral for referred_user_id={referred_user_id} was not found",
                    code="REFERRAL_NOT_FOUND",
                )

            if referral.status != ReferralStatus.PENDING:
                raise ConflictError(
                    message=f"Cannot reject referral in '{referral.status.value}' state. Only PENDING referrals can be rejected.",
                    code="INVALID_LIFECYCLE_TRANSITION",
                )

            now = utcnow()
            from_status = referral.status.value
            clean_reason = (reason or "Rejected by admin").strip()

            referral.status = ReferralStatus.REJECTED
            referral.rejected_at = now
            referral.reviewed_by = admin_user.id
            referral.rejection_reason = clean_reason

            audit = AuditLog(
                actor_id=admin_user.id,
                action=AuditAction.REJECT,
                target_type="REFERRAL",
                target_id=referral.id,
                referral_id=referral.id,
                from_status=from_status,
                to_status=ReferralStatus.REJECTED.value,
                reason=clean_reason,
                created_at=now,
            )
            self.db.add(audit)

            self.db.commit()
            self.db.refresh(referral)
            return ReferralResponse.model_validate(referral)
        except Exception:
            self.db.rollback()
            raise

    def reverse_referral(
        self, admin_user: User, referred_user_id: int, reason: Optional[str] = None
    ) -> ReferralResponse:
        try:
            referral = self.repo.get_referral_by_referred_user(
                referred_user_id=referred_user_id, for_update=True
            )
            if not referral:
                raise NotFoundError(
                    message=f"Referral for referred_user_id={referred_user_id} was not found",
                    code="REFERRAL_NOT_FOUND",
                )

            if referral.status != ReferralStatus.SUCCESSFUL:
                raise ConflictError(
                    message=f"Cannot reverse referral in '{referral.status.value}' state. Only SUCCESSFUL referrals can be reversed.",
                    code="INVALID_LIFECYCLE_TRANSITION",
                )

            balance_row = self.repo.get_or_create_balance(
                user_id=referral.referrer_id, for_update=True
            )

            credit_stmt = select(RewardLedger).where(
                RewardLedger.referral_id == referral.id,
                RewardLedger.entry_type == LedgerEntryType.REFERRAL_CREDIT,
            )
            original_credit = self.db.execute(credit_stmt).scalar_one_or_none()
            if not original_credit:
                raise ConflictError(
                    message="Original credit ledger entry not found for this referral",
                    code="MISSING_ORIGINAL_CREDIT",
                )

            debit_points = -abs(original_credit.points)
            new_balance = balance_row.balance + debit_points
            new_successful_count = max(0, balance_row.successful_referral_count - 1)
            now = utcnow()
            from_status = referral.status.value
            clean_reason = (reason or "Reversed by admin").strip()

            referral.status = ReferralStatus.REVERSED
            referral.reversed_at = now
            referral.reviewed_by = admin_user.id
            referral.reversal_reason = clean_reason

            reversal_entry = RewardLedger(
                user_id=referral.referrer_id,
                referral_id=referral.id,
                entry_type=LedgerEntryType.REFERRAL_REVERSAL,
                points=debit_points,
                balance_after=new_balance,
                idempotency_key=f"referral:{referral.id}:reversal",
                reversal_of_entry_id=original_credit.id,
                created_at=now,
            )
            self.db.add(reversal_entry)

            balance_row.balance = new_balance
            balance_row.successful_referral_count = new_successful_count
            balance_row.updated_at = now

            audit = AuditLog(
                actor_id=admin_user.id,
                action=AuditAction.REVERSE,
                target_type="REFERRAL",
                target_id=referral.id,
                referral_id=referral.id,
                from_status=from_status,
                to_status=ReferralStatus.REVERSED.value,
                reason=clean_reason,
                created_at=now,
            )
            self.db.add(audit)

            self.db.commit()
            self.db.refresh(referral)
            return ReferralResponse.model_validate(referral)
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(
                message="Referral reversal already processed",
                code="IDEMPOTENCY_CONFLICT",
            )
        except Exception:
            self.db.rollback()
            raise

    def get_referral_details(self, referral_id: int) -> AdminReferralDetailResponse:
        referral = self.repo.get_referral_by_id(referral_id)
        if not referral:
            raise NotFoundError(
                message=f"Referral with id={referral_id} was not found",
                code="REFERRAL_NOT_FOUND",
            )

        referrer = self.db.get(User, referral.referrer_id)
        referred_user = self.db.get(User, referral.referred_user_id)

        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.referral_id == referral.id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
        audits = list(self.db.execute(audit_stmt).scalars().all())

        return AdminReferralDetailResponse(
            referral=ReferralResponse.model_validate(referral),
            referrer_name=referrer.name if referrer else "Unknown",
            referrer_email=referrer.email if referrer else "Unknown",
            referred_user_name=referred_user.name if referred_user else "Unknown",
            referred_user_email=referred_user.email if referred_user else "Unknown",
            lifecycle_history=[AuditHistoryItem.model_validate(a) for a in audits],
        )

    def _evaluate_and_grant_milestones(
        self, user_id: int, successful_count: int, now: datetime
    ) -> None:
        eligible_stmt = select(MilestoneDefinition).where(
            MilestoneDefinition.threshold <= successful_count
        )
        eligible_milestones = list(self.db.execute(eligible_stmt).scalars().all())
        if not eligible_milestones:
            return

        existing_map = self.repo.get_user_milestones(user_id)
        for milestone in eligible_milestones:
            if milestone.id not in existing_map:
                self.db.add(
                    UserMilestone(
                        user_id=user_id,
                        milestone_id=milestone.id,
                        achieved_at=now,
                    )
                )
