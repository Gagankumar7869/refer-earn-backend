from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.entities import (
    AuditAction,
    AuditLog,
    ReconciliationReport,
    Referral,
    ReferralStatus,
    RewardBalance,
    RewardLedger,
    User,
)
from app.schemas.referral import DiscrepancyItem, ReconciliationReportResponse


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ReconciliationService:
    def __init__(self, db: Session):
        self.db = db

    def run_reconciliation(self, admin_user: User) -> ReconciliationReportResponse:
        started_at = utcnow()

        users = list(self.db.execute(select(User).order_by(User.id.asc())).scalars().all())
        user_map = {u.id: u for u in users}

        balances = list(self.db.execute(select(RewardBalance)).scalars().all())
        balance_map = {b.user_id: b for b in balances}

        ledger_sums_stmt = select(
            RewardLedger.user_id,
            func.coalesce(func.sum(RewardLedger.points), 0),
        ).group_by(RewardLedger.user_id)
        ledger_sum_map = {
            int(uid): int(total) for uid, total in self.db.execute(ledger_sums_stmt).all()
        }

        successful_counts_stmt = (
            select(Referral.referrer_id, func.count(Referral.id))
            .where(Referral.status == ReferralStatus.SUCCESSFUL)
            .group_by(Referral.referrer_id)
        )
        expected_count_map = {
            int(uid): int(cnt) for uid, cnt in self.db.execute(successful_counts_stmt).all()
        }

        all_user_ids = sorted(
            set(user_map.keys())
            | set(balance_map.keys())
            | set(ledger_sum_map.keys())
            | set(expected_count_map.keys())
        )

        discrepancies: list[DiscrepancyItem] = []

        for uid in all_user_ids:
            user_obj = user_map.get(uid)
            email = user_obj.email if user_obj else f"unknown_user_{uid}"

            expected_balance = ledger_sum_map.get(uid, 0)
            actual_balance = balance_map[uid].balance if uid in balance_map else 0

            if expected_balance != actual_balance:
                discrepancies.append(
                    DiscrepancyItem(
                        user_id=uid,
                        user_email=email,
                        field="reward_balance",
                        expected_value=expected_balance,
                        actual_value=actual_balance,
                        difference=actual_balance - expected_balance,
                    )
                )

            expected_count = expected_count_map.get(uid, 0)
            actual_count = (
                balance_map[uid].successful_referral_count if uid in balance_map else 0
            )

            if expected_count != actual_count:
                discrepancies.append(
                    DiscrepancyItem(
                        user_id=uid,
                        user_email=email,
                        field="successful_referral_count",
                        expected_value=expected_count,
                        actual_value=actual_count,
                        difference=actual_count - expected_count,
                    )
                )

            latest_ledger_stmt = (
                select(RewardLedger)
                .where(RewardLedger.user_id == uid)
                .order_by(RewardLedger.id.desc())
                .limit(1)
            )
            latest_entry = self.db.execute(latest_ledger_stmt).scalar_one_or_none()
            if latest_entry and latest_entry.balance_after != expected_balance:
                discrepancies.append(
                    DiscrepancyItem(
                        user_id=uid,
                        user_email=email,
                        field="latest_ledger_balance_after",
                        expected_value=expected_balance,
                        actual_value=latest_entry.balance_after,
                        difference=latest_entry.balance_after - expected_balance,
                    )
                )

        completed_at = utcnow()
        status_label = "CLEAN" if len(discrepancies) == 0 else "DISCREPANCIES_FOUND"

        details_payload = {
            "discrepancies": [d.model_dump() for d in discrepancies],
            "summary": {
                "balance_drift_count": sum(
                    1 for d in discrepancies if d.field == "reward_balance"
                ),
                "counter_drift_count": sum(
                    1 for d in discrepancies if d.field == "successful_referral_count"
                ),
                "ledger_snapshot_drift_count": sum(
                    1 for d in discrepancies if d.field == "latest_ledger_balance_after"
                ),
            },
        }

        report = ReconciliationReport(
            run_by=admin_user.id,
            started_at=started_at,
            completed_at=completed_at,
            status=status_label,
            total_users_checked=len(all_user_ids),
            discrepancy_count=len(discrepancies),
            details=details_payload,
        )
        self.db.add(report)
        self.db.flush()

        audit = AuditLog(
            actor_id=admin_user.id,
            action=AuditAction.RECONCILE,
            target_type="RECONCILIATION_REPORT",
            target_id=report.id,
            referral_id=None,
            from_status=None,
            to_status=status_label,
            reason=f"Checked {len(all_user_ids)} users; found {len(discrepancies)} discrepancies",
            created_at=completed_at,
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(report)

        return ReconciliationReportResponse(
            audit_id=report.id,
            run_by=report.run_by,
            started_at=report.started_at,
            completed_at=report.completed_at,
            status=report.status,
            total_users_checked=report.total_users_checked,
            discrepancy_count=report.discrepancy_count,
            discrepancies=discrepancies,
            details=report.details,
        )

    def get_report_by_id(self, audit_id: int) -> ReconciliationReportResponse:
        report = self.db.get(ReconciliationReport, audit_id)
        if not report:
            raise NotFoundError(
                message=f"Reconciliation report with audit_id={audit_id} was not found",
                code="RECONCILIATION_REPORT_NOT_FOUND",
            )

        raw_discrepancies = report.details.get("discrepancies", [])
        discrepancies = [DiscrepancyItem(**item) for item in raw_discrepancies]

        return ReconciliationReportResponse(
            audit_id=report.id,
            run_by=report.run_by,
            started_at=report.started_at,
            completed_at=report.completed_at,
            status=report.status,
            total_users_checked=report.total_users_checked,
            discrepancy_count=report.discrepancy_count,
            discrepancies=discrepancies,
            details=report.details,
        )
