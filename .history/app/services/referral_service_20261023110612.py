import math
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.entities import User
from app.repositories.referral_repository import ReferralRepository
from app.schemas.referral import (
    LedgerTransactionItem,
    MemberMeDashboardResponse,
    MemberMilestonesResponse,
    MilestoneSummary,
    MilestoneTierItem,
    PaginatedTransactionsResponse,
    ReferralActivityItem,
    ReferralCountsSummary,
    ReferralResponse,
)


class ReferralService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReferralRepository(db)

    def create_referral(self, current_user: User, referral_code: str) -> ReferralResponse:
        normalized_code = referral_code.strip().upper()

        referrer = self.repo.get_user_by_referral_code(normalized_code)
        if not referrer:
            raise NotFoundError(
                message=f"Referral code '{normalized_code}' was not found",
                code="REFERRAL_CODE_NOT_FOUND",
            )

        if referrer.id == current_user.id:
            raise ConflictError(
                message="Users cannot refer themselves",
                code="SELF_REFERRAL_NOT_ALLOWED",
            )

        existing = self.repo.get_referral_by_referred_user(current_user.id)
        if existing:
            raise ConflictError(
                message="User has already been attributed to a referrer",
                code="DUPLICATE_REFERRAL_ATTRIBUTION",
            )

        try:
            referral = self.repo.create_referral(
                referrer_id=referrer.id,
                referred_user_id=current_user.id,
                referral_code_used=normalized_code,
            )
            self.db.commit()
            self.db.refresh(referral)
            return ReferralResponse.model_validate(referral)
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(
                message="User has already been attributed to a referrer",
                code="DUPLICATE_REFERRAL_ATTRIBUTION",
            )

    def get_member_dashboard(self, current_user: User) -> MemberMeDashboardResponse:
        balance_row = self.repo.get_or_create_balance(current_user.id)
        self.db.commit()

        counts_map = self.repo.get_referral_status_counts(current_user.id)
        total_referrals = sum(counts_map.values())
        successful_count = balance_row.successful_referral_count

        milestone_summary = self._compute_milestone_summary(successful_count)
        recent_rows = self.repo.get_recent_referrals_for_referrer(current_user.id, limit=10)

        activity = [
            ReferralActivityItem(
                referral_id=ref.id,
                referred_user_id=referred_user.id,
                referred_user_name=referred_user.name,
                status=ref.status.value,
                created_at=ref.created_at,
                approved_at=ref.approved_at,
            )
            for ref, referred_user in recent_rows
        ]

        return MemberMeDashboardResponse(
            user_id=current_user.id,
            name=current_user.name,
            email=current_user.email,
            referral_code=current_user.referral_code,
            referral_link=f"https://app.eduskills.com/register?ref={current_user.referral_code}",
            reward_balance=balance_row.balance,
            referral_counts=ReferralCountsSummary(
                total=total_referrals,
                pending=counts_map["PENDING"],
                successful=counts_map["SUCCESSFUL"],
                rejected=counts_map["REJECTED"],
                reversed=counts_map["REVERSED"],
            ),
            milestone_progress=milestone_summary,
            recent_activity=activity,
        )

    def get_member_milestones(self, current_user: User) -> MemberMilestonesResponse:
        balance_row = self.repo.get_or_create_balance(current_user.id)
        self.db.commit()

        successful_count = balance_row.successful_referral_count
        definitions = self.repo.get_all_milestone_definitions()
        achieved_map = self.repo.get_user_milestones(current_user.id)
        summary = self._compute_milestone_summary(successful_count)

        tier_items: list[MilestoneTierItem] = []
        in_progress_assigned = False

        for m in definitions:
            achieved_record = achieved_map.get(m.id)
            currently_meets = successful_count >= m.threshold

            if achieved_record is not None or currently_meets:
                status = "ACHIEVED"
            elif not in_progress_assigned:
                status = "IN_PROGRESS"
                in_progress_assigned = True
            else:
                status = "LOCKED"

            tier_items.append(
                MilestoneTierItem(
                    id=m.id,
                    threshold=m.threshold,
                    name=m.name,
                    description=m.description,
                    perk=m.perk,
                    status=status,
                    achieved_at=achieved_record.achieved_at if achieved_record else None,
                    currently_meets_threshold=currently_meets,
                )
            )

        return MemberMilestonesResponse(
            successful_referral_count=successful_count,
            current_tier=summary.current_tier,
            next_tier=summary.next_tier,
            referrals_remaining_to_next=summary.referrals_remaining_to_next,
            milestones=tier_items,
        )

    def get_member_transactions(
        self, current_user: User, page: int, page_size: int
    ) -> PaginatedTransactionsResponse:
        items, total = self.repo.get_user_transactions_paginated(
            user_id=current_user.id, page=page, page_size=page_size
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return PaginatedTransactionsResponse(
            items=[LedgerTransactionItem.model_validate(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
        )

    def _compute_milestone_summary(self, successful_count: int) -> MilestoneSummary:
        definitions = self.repo.get_all_milestone_definitions()
        current_tier = None
        next_tier = None
        next_threshold = None

        for m in definitions:
            if successful_count >= m.threshold:
                current_tier = m.name
            elif next_tier is None:
                next_tier = m.name
                next_threshold = m.threshold

        remaining = max(0, next_threshold - successful_count) if next_threshold is not None else 0
        return MilestoneSummary(
            current_tier=current_tier,
            next_tier=next_tier,
            next_threshold=next_threshold,
            successful_referrals=successful_count,
            referrals_remaining_to_next=remaining,
        )