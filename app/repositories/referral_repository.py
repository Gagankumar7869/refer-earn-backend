from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    MilestoneDefinition,
    Referral,
    ReferralStatus,
    RewardBalance,
    RewardLedger,
    User,
    UserMilestone,
)


class ReferralRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_referral_code(self, code: str) -> Optional[User]:
        stmt = select(User).where(User.referral_code == code)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_referral_by_referred_user(
        self, referred_user_id: int, for_update: bool = False
    ) -> Optional[Referral]:
        stmt = select(Referral).where(Referral.referred_user_id == referred_user_id)
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def get_referral_by_id(self, referral_id: int) -> Optional[Referral]:
        return self.db.get(Referral, referral_id)

    def create_referral(
        self, referrer_id: int, referred_user_id: int, referral_code_used: str
    ) -> Referral:
        referral = Referral(
            referrer_id=referrer_id,
            referred_user_id=referred_user_id,
            referral_code_used=referral_code_used,
            status=ReferralStatus.PENDING,
        )
        self.db.add(referral)
        self.db.flush()
        return referral

    def get_or_create_balance(self, user_id: int, for_update: bool = False) -> RewardBalance:
        stmt = select(RewardBalance).where(RewardBalance.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        balance_row = self.db.execute(stmt).scalar_one_or_none()
        if not balance_row:
            balance_row = RewardBalance(
                user_id=user_id, balance=0, successful_referral_count=0
            )
            self.db.add(balance_row)
            self.db.flush()
            if for_update:
                balance_row = self.db.execute(stmt).scalar_one()
        return balance_row

    def get_referral_status_counts(self, referrer_id: int) -> dict[str, int]:
        stmt = (
            select(Referral.status, func.count(Referral.id))
            .where(Referral.referrer_id == referrer_id)
            .group_by(Referral.status)
        )
        rows = self.db.execute(stmt).all()
        counts = {
            ReferralStatus.PENDING.value: 0,
            ReferralStatus.SUCCESSFUL.value: 0,
            ReferralStatus.REJECTED.value: 0,
            ReferralStatus.REVERSED.value: 0,
        }
        for status_enum, count in rows:
            counts[status_enum.value] = int(count)
        return counts

    def get_recent_referrals_for_referrer(
        self, referrer_id: int, limit: int = 10
    ) -> list[tuple[Referral, User]]:
        stmt = (
            select(Referral, User)
            .join(User, User.id == Referral.referred_user_id)
            .where(Referral.referrer_id == referrer_id)
            .order_by(Referral.created_at.desc(), Referral.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).all())

    def get_all_milestone_definitions(self) -> list[MilestoneDefinition]:
        stmt = select(MilestoneDefinition).order_by(MilestoneDefinition.threshold.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_user_milestones(self, user_id: int) -> dict[int, UserMilestone]:
        stmt = select(UserMilestone).where(UserMilestone.user_id == user_id)
        rows = self.db.execute(stmt).scalars().all()
        return {row.milestone_id: row for row in rows}

    def get_user_transactions_paginated(
        self, user_id: int, page: int, page_size: int
    ) -> tuple[list[RewardLedger], int]:
        count_stmt = (
            select(func.count(RewardLedger.id)).where(RewardLedger.user_id == user_id)
        )
        total = int(self.db.execute(count_stmt).scalar_one() or 0)

        offset = (page - 1) * page_size
        stmt = (
            select(RewardLedger)
            .where(RewardLedger.user_id == user_id)
            .order_by(RewardLedger.created_at.desc(), RewardLedger.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_admin_referrals(
        self,
        page: int,
        page_size: int,
        status: Optional[ReferralStatus] = None,
        referrer_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> tuple[list[Referral], int]:
        conditions = []
        if status is not None:
            conditions.append(Referral.status == status)
        if referrer_id is not None:
            conditions.append(Referral.referrer_id == referrer_id)
        if from_date is not None:
            conditions.append(Referral.created_at >= from_date)
        if to_date is not None:
            conditions.append(Referral.created_at <= to_date)

        count_stmt = select(func.count(Referral.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        total = int(self.db.execute(count_stmt).scalar_one() or 0)

        offset = (page - 1) * page_size
        stmt = select(Referral)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = (
            stmt.order_by(Referral.created_at.desc(), Referral.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
