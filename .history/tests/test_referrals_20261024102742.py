from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.entities import (
    LedgerEntryType,
    MilestoneDefinition,
    Referral,
    RewardBalance,
    RewardLedger,
    User,
    UserMilestone,
    UserRole,
)

test_engine = create_engine(
    settings.TEST_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=15,
    max_overflow=20,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    assert "_test" in settings.TEST_DATABASE_URL, "Test suite must run against a _test database!"
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()
    try:
        milestones = [
            MilestoneDefinition(threshold=5, name="Pioneer", description="5 referrals", perk="Badge"),
            MilestoneDefinition(threshold=10, name="Trailblazer", description="10 referrals", perk="Kit"),
            MilestoneDefinition(threshold=25, name="Visionary", description="25 referrals", perk="Waiver"),
            MilestoneDefinition(threshold=50, name="Icon", description="50 referrals", perk="VIP"),
        ]
        db.add_all(milestones)
        db.flush()

        pw_hash = hash_password("Pass123!")

        admin = User(
            name="Test Admin",
            email="admin@test.com",
            password_hash=pw_hash,
            referral_code="ADM00001",
            role=UserRole.ADMIN,
        )
        referrer = User(
            name="Referrer A",
            email="referrer@test.com",
            password_hash=pw_hash,
            referral_code="REF10000",
            role=UserRole.MEMBER,
        )
        member_b = User(
            name="Member B",
            email="memberb@test.com",
            password_hash=pw_hash,
            referral_code="MBR20000",
            role=UserRole.MEMBER,
        )
        db.add_all([admin, referrer, member_b])
        db.flush()

        for u in (admin, referrer, member_b):
            db.add(RewardBalance(user_id=u.id, balance=0, successful_referral_count=0))

        for i in range(1, 7):
            extra_user = User(
                name=f"User {i}",
                email=f"user{i}@test.com",
                password_hash=pw_hash,
                referral_code=f"USR0000{i}",
                role=UserRole.MEMBER,
            )
            db.add(extra_user)
            db.flush()
            db.add(RewardBalance(user_id=extra_user.id, balance=0, successful_referral_count=0))

        db.commit()
    finally:
        db.close()
    yield


def get_auth_headers(email: str, password: str = "Pass123!") -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_referral_creation_self_referral_and_duplicate_block():
    headers_a = get_auth_headers("referrer@test.com")
    headers_b = get_auth_headers("memberb@test.com")

    
    self_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_a)
    assert self_resp.status_code == 409
    assert self_resp.json()["error"]["code"] == "SELF_REFERRAL_NOT_ALLOWED"

    
    unknown_resp = client.post("/api/v1/referrals", json={"referral_code": "NOEXIST9"}, headers=headers_b)
    assert unknown_resp.status_code == 404
    assert unknown_resp.json()["error"]["code"] == "REFERRAL_CODE_NOT_FOUND"

    
    valid_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    assert valid_resp.status_code == 201
    assert valid_resp.json()["status"] == "PENDING"

    
    dup_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "DUPLICATE_REFERRAL_ATTRIBUTION"


def test_authorization_and_member_isolation():
    headers_b = get_auth_headers("memberb@test.com")

    
    unauth_resp = client.get("/api/v1/referrals/me")
    assert unauth_resp.status_code == 401

    
    forbidden_resp = client.get("/api/v1/referrals/admin/list", headers=headers_b)
    assert forbidden_resp.status_code == 403
    assert forbidden_resp.json()["error"]["code"] == "FORBIDDEN"


def test_admin_approve_ledger_and_idempotency():
    headers_a = get_auth_headers("referrer@test.com")
    headers_b = get_auth_headers("memberb@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    create_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    referred_id = create_resp.json()["referred_user_id"]


    app_resp = client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "SUCCESSFUL"

    
    dup_app = client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)
    assert dup_app.status_code == 409
    assert dup_app.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"

    
    me_resp = client.get("/api/v1/referrals/me", headers=headers_a)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["reward_balance"] == 100
    assert me_data["referral_counts"]["successful"] == 1

    tx_resp = client.get("/api/v1/referrals/transactions", headers=headers_a)
    assert tx_resp.status_code == 200
    assert tx_resp.json()["total_items"] == 1
    assert tx_resp.json()["items"][0]["points"] == 100


def test_concurrent_approvals_grant_reward_exactly_once():
    headers_b = get_auth_headers("memberb@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    create_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    referred_id = create_resp.json()["referred_user_id"]

    def approve_task():
        with TestClient(app) as local_client:
            return local_client.post(
                f"/api/v1/referrals/admin/approve/{referred_id}",
                headers=headers_admin,
            ).status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(approve_task) for _ in range(8)]
        status_codes = [f.result() for f in futures]

    assert status_codes.count(200) == 1
    assert status_codes.count(409) == 7

    db = TestingSessionLocal()
    try:
        referrer = db.execute(select(User).where(User.email == "referrer@test.com")).scalar_one()
        balance = db.get(RewardBalance, referrer.id)
        ledger_rows = db.execute(
            select(RewardLedger).where(RewardLedger.user_id == referrer.id)
        ).scalars().all()
        assert balance.balance == 100
        assert balance.successful_referral_count == 1
        assert len(ledger_rows) == 1
    finally:
        db.close()


def test_admin_rejection_grants_no_rewards():
    headers_b = get_auth_headers("memberb@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    create_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    referred_id = create_resp.json()["referred_user_id"]

    rej_resp = client.post(
        f"/api/v1/referrals/admin/reject/{referred_id}",
        json={"reason": "Suspicious signup"},
        headers=headers_admin,
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "REJECTED"
    assert rej_resp.json()["rejection_reason"] == "Suspicious signup"

    
    app_after_rej = client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)
    assert app_after_rej.status_code == 409


def test_reversal_creates_compensating_entry_and_updates_balance():
    headers_a = get_auth_headers("referrer@test.com")
    headers_b = get_auth_headers("memberb@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    create_resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    referred_id = create_resp.json()["referred_user_id"]
    referral_id = create_resp.json()["id"]

    client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)

    
    rev_resp = client.post(
        f"/api/v1/referrals/admin/reverse/{referred_id}",
        json={"reason": "Chargeback fraud"},
        headers=headers_admin,
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "REVERSED"

    
    rev_again = client.post(f"/api/v1/referrals/admin/reverse/{referred_id}", headers=headers_admin)
    assert rev_again.status_code == 409

    
    tx_resp = client.get("/api/v1/referrals/transactions", headers=headers_a)
    items = tx_resp.json()["items"]
    assert len(items) == 2
    assert items[0]["entry_type"] == LedgerEntryType.REFERRAL_REVERSAL.value
    assert items[0]["points"] == -100
    assert items[0]["balance_after"] == 0
    assert items[0]["reversal_of_entry_id"] == items[1]["id"]

    
    detail_resp = client.get(f"/api/v1/referrals/admin/{referral_id}", headers=headers_admin)
    assert detail_resp.status_code == 200
    history = detail_resp.json()["lifecycle_history"]
    assert len(history) == 2
    assert history[0]["action"] == "APPROVE"
    assert history[1]["action"] == "REVERSE"


def test_milestone_unlock_at_5_and_retention_after_reversal():
    headers_a = get_auth_headers("referrer@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    referred_ids = []
    for i in range(1, 6):
        u_headers = get_auth_headers(f"user{i}@test.com")
        r = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=u_headers)
        assert r.status_code == 201
        referred_ids.append(r.json()["referred_user_id"])

    
    for rid in referred_ids[:4]:
        client.post(f"/api/v1/referrals/admin/approve/{rid}", headers=headers_admin)

    ms_before = client.get("/api/v1/referrals/milestones", headers=headers_a).json()
    assert ms_before["current_tier"] is None
    assert ms_before["next_tier"] == "Pioneer"
    assert ms_before["referrals_remaining_to_next"] == 1

    
    client.post(f"/api/v1/referrals/admin/approve/{referred_ids[4]}", headers=headers_admin)

    ms_at_5 = client.get("/api/v1/referrals/milestones", headers=headers_a).json()
    assert ms_at_5["current_tier"] == "Pioneer"
    assert ms_at_5["next_tier"] == "Trailblazer"
    assert ms_at_5["referrals_remaining_to_next"] == 5
    pioneer_item = ms_at_5["milestones"][0]
    assert pioneer_item["status"] == "ACHIEVED"
    assert pioneer_item["currently_meets_threshold"] is True

    
    client.post(f"/api/v1/referrals/admin/reverse/{referred_ids[4]}", headers=headers_admin)
    ms_after_rev = client.get("/api/v1/referrals/milestones", headers=headers_a).json()
    assert ms_after_rev["successful_referral_count"] == 4
    pioneer_after = ms_after_rev["milestones"][0]
    assert pioneer_after["status"] == "ACHIEVED"
    assert pioneer_after["achieved_at"] is not None
    assert pioneer_after["currently_meets_threshold"] is False


def test_reconciliation_detects_balance_and_counter_drift():
    headers_b = get_auth_headers("memberb@test.com")
    headers_admin = get_auth_headers("admin@test.com")

    r = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    referred_id = r.json()["referred_user_id"]
    client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)

    
    clean_resp = client.post("/api/v1/referrals/admin/reconcile", headers=headers_admin)
    assert clean_resp.status_code == 200
    assert clean_resp.json()["status"] == "CLEAN"
    assert clean_resp.json()["discrepancy_count"] == 0

    
    db = TestingSessionLocal()
    try:
        referrer = db.execute(select(User).where(User.email == "referrer@test.com")).scalar_one()
        bal = db.get(RewardBalance, referrer.id)
        bal.balance = 999
        bal.successful_referral_count = 7
        db.commit()
    finally:
        db.close()

    
    drift_resp = client.post("/api/v1/referrals/admin/reconcile", headers=headers_admin)
    assert drift_resp.status_code == 200
    drift_data = drift_resp.json()
    assert drift_data["status"] == "DISCREPANCIES_FOUND"
    assert drift_data["discrepancy_count"] == 2
    fields_flagged = {d["field"] for d in drift_data["discrepancies"]}
    assert fields_flagged == {"reward_balance", "successful_referral_count"}

    
    audit_id = drift_data["audit_id"]
    rep_resp = client.get(
        f"/api/v1/referrals/admin/reconciliation-report/{audit_id}",
        headers=headers_admin,
    )
    assert rep_resp.status_code == 200
    assert rep_resp.json()["audit_id"] == audit_id
