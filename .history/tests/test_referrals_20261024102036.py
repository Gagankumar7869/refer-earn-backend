from concurrent.futures import ThreadPoolExecutor, as_completed
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.entities import (
    MilestoneDefinition,
    Referral,
    ReferralStatus,
    RewardBalance,
    RewardLedger,
    User,
    UserRole,
)


test_engine = create_engine(settings.TEST_DATABASE_URL, pool_pre_ping=True)
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
    
    assert "_test" in settings.TEST_DATABASE_URL, "Test suite must run against a test database!"
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()
    try:
        
        db.add(MilestoneDefinition(threshold=5, name="Pioneer", description="5 referrals", perk="Badge"))
        db.add(MilestoneDefinition(threshold=10, name="Trailblazer", description="10 referrals", perk="Kit"))
        db.flush()

        
        admin = User(
            name="Test Admin",
            email="admin@test.com",
            password_hash=hash_password("Admin123!"),
            referral_code="ADM00001",
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.flush()
        db.add(RewardBalance(user_id=admin.id, balance=0, successful_referral_count=0))

       
        referrer = User(
            name="Referrer A",
            email="referrer@test.com",
            password_hash=hash_password("Pass123!"),
            referral_code="REF10000",
            role=UserRole.MEMBER,
        )
        db.add(referrer)
        db.flush()
        db.add(RewardBalance(user_id=referrer.id, balance=0, successful_referral_count=0))

        
        member_b = User(
            name="Member B",
            email="memberb@test.com",
            password_hash=hash_password("Pass123!"),
            referral_code="MBR20000",
            role=UserRole.MEMBER,
        )
        db.add(member_b)
        db.flush()
        db.add(RewardBalance(user_id=member_b.id, balance=0, successful_referral_count=0))

        db.commit()
    finally:
        db.close()
    yield


def get_auth_headers(email: str, password: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_referral_and_duplicate_block():
    headers_b = get_auth_headers("memberb@test.com", "Pass123!")

    
    resp = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"
    assert data["referral_code_used"] == "REF10000"

    
    resp_dup = client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)
    assert resp_dup.status_code == 409
    assert resp_dup.json()["error"]["code"] == "DUPLICATE_REFERRAL_ATTRIBUTION"


def test_admin_approve_and_idempotency():
    headers_b = get_auth_headers("memberb@test.com", "Pass123!")
    client.post("/api/v1/referrals", json={"referral_code": "REF10000"}, headers=headers_b)

    db = TestingSessionLocal()
    ref = db.execute(select(Referral)).scalar_one()
    referred_id = ref.referred_user_id
    db.close()

    headers_admin = get_auth_headers("admin@test.com", "Admin123!")

    
    resp_app = client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)
    assert resp_app.status_code == 200
    assert resp_app.json()["status"] == "SUCCESSFUL"

    
    resp_app2 = client.post(f"/api/v1/referrals/admin/approve/{referred_id}", headers=headers_admin)
    assert resp_app2.status_code == 409
    assert resp_app2.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"


def test_reconciliation_clean():
    headers_admin = get_auth_headers("admin@test.com", "Admin123!")
    resp = client.post("/api/v1/referrals/admin/reconcile", headers=headers_admin)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CLEAN"
    assert data["discrepancy_count"] == 0