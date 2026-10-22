from datetime import datetime, timezone
import enum
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRole(str, enum.Enum):
    MEMBER = "MEMBER"
    ADMIN = "ADMIN"


class ReferralStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"


class LedgerEntryType(str, enum.Enum):
    REFERRAL_CREDIT = "REFERRAL_CREDIT"
    REFERRAL_REVERSAL = "REFERRAL_REVERSAL"


class AuditAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVERSE = "REVERSE"
    RECONCILE = "RECONCILE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.MEMBER)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        CheckConstraint("referrer_id <> referred_user_id", name="ck_referrals_no_self_referral"),
        Index("ix_referrals_status_created_at", "status", "created_at"),
        Index("ix_referrals_referrer_id", "referrer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    referred_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    referral_code_used: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus), nullable=False, default=ReferralStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reversal_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class RewardLedger(Base):
    __tablename__ = "reward_ledger"
    __table_args__ = (
        Index("ix_reward_ledger_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), nullable=False)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    reversal_of_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reward_ledger.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class RewardBalance(Base):
    __tablename__ = "reward_balances"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_referral_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class MilestoneDefinition(Base):
    __tablename__ = "milestone_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    threshold: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    perk: Mapped[str] = mapped_column(String(255), nullable=False)


class UserMilestone(Base):
    __tablename__ = "user_milestones"
    __table_args__ = (
        UniqueConstraint("user_id", "milestone_id", name="uq_user_milestone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestone_definitions.id"), nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_referral_id", "referral_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    referral_id: Mapped[Optional[int]] = mapped_column(ForeignKey("referrals.id"), nullable=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column( Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class ReconciliationReport(Base):
    __tablename__ = "reconciliation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_users_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discrepancy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)