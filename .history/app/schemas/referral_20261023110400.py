from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReferralCreateRequest(BaseModel):
    referral_code: str = Field(..., min_length=4, max_length=32, pattern=r"^[A-Za-z0-9]+$")


class ReferralResponse(BaseModel):
    id: int
    referrer_id: int
    referred_user_id: int
    referral_code_used: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    reversed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    reversal_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class ReferralCountsSummary(BaseModel):
    total: int
    pending: int
    successful: int
    rejected: int
    reversed: int


class MilestoneSummary(BaseModel):
    current_tier: Optional[str] = None
    next_tier: Optional[str] = None
    next_threshold: Optional[int] = None
    successful_referrals: int
    referrals_remaining_to_next: int


class ReferralActivityItem(BaseModel):
    referral_id: int
    referred_user_id: int
    referred_user_name: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None


class MemberMeDashboardResponse(BaseModel):
    user_id: int
    name: str
    email: str
    referral_code: str
    referral_link: str
    reward_balance: int
    referral_counts: ReferralCountsSummary
    milestone_progress: MilestoneSummary
    recent_activity: list[ReferralActivityItem]


class MilestoneTierItem(BaseModel):
    id: int
    threshold: int
    name: str
    description: str
    perk: str
    status: str  # "ACHIEVED", "IN_PROGRESS", "LOCKED"
    achieved_at: Optional[datetime] = None
    currently_meets_threshold: bool


class MemberMilestonesResponse(BaseModel):
    successful_referral_count: int
    current_tier: Optional[str] = None
    next_tier: Optional[str] = None
    referrals_remaining_to_next: int
    milestones: list[MilestoneTierItem]


class LedgerTransactionItem(BaseModel):
    id: int
    referral_id: int
    entry_type: str
    points: int
    balance_after: int
    reversal_of_entry_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTransactionsResponse(BaseModel):
    items: list[LedgerTransactionItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AdminRejectRequest(BaseModel):
    reason: Optional[str] = Field(default="Rejected by admin", max_length=500)


class AdminReverseRequest(BaseModel):
    reason: Optional[str] = Field(default="Reversed by admin", max_length=500)


class PaginatedAdminReferralsResponse(BaseModel):
    items: list[ReferralResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class AuditHistoryItem(BaseModel):
    id: int
    actor_id: int
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminReferralDetailResponse(BaseModel):
    referral: ReferralResponse
    referrer_name: str
    referrer_email: str
    referred_user_name: str
    referred_user_email: str
    lifecycle_history: list[AuditHistoryItem]


class DiscrepancyItem(BaseModel):
    user_id: int
    user_email: str
    field: str
    expected_value: int
    actual_value: int
    difference: int


class ReconciliationReportResponse(BaseModel):
    audit_id: int
    run_by: int
    started_at: datetime
    completed_at: datetime
    status: str
    total_users_checked: int
    discrepancy_count: int
    discrepancies: list[DiscrepancyItem]
    details: dict[str, Any]