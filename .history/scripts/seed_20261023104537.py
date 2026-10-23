from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.entities import MilestoneDefinition, RewardBalance, User, UserRole

MILESTONES = [
    {
        "threshold": 5,
        "name": "Pioneer",
        "description": "Reach 5 successful referrals",
        "perk": "Priority community badge and early feature access",
    },
    {
        "threshold": 10,
        "name": "Trailblazer",
        "description": "Reach 10 successful referrals",
        "perk": "Exclusive Trailblazer merchandise kit",
    },
    {
        "threshold": 25,
        "name": "Visionary",
        "description": "Reach 25 successful referrals",
        "perk": "1-year premium subscription waiver",
    },
    {
        "threshold": 50,
        "name": "Icon",
        "description": "Reach 50 successful referrals",
        "perk": "VIP lifetime membership and annual summit invite",
    },
]

USERS = [
    {
        "name": "System Admin",
        "email": "admin@eduskills.com",
        "password": "AdminPassword123!",
        "referral_code": "ADMIN001",
        "role": UserRole.ADMIN,
    },
    {
        "name": "Alice Referrer",
        "email": "alice@example.com",
        "password": "MemberPassword123!",
        "referral_code": "ALICE100",
        "role": UserRole.MEMBER,
    },
    {
        "name": "Bob Member",
        "email": "bob@example.com",
        "password": "MemberPassword123!",
        "referral_code": "BOB20000",
        "role": UserRole.MEMBER,
    },
    {
        "name": "Charlie Member",
        "email": "charlie@example.com",
        "password": "MemberPassword123!",
        "referral_code": "CHARLIE3",
        "role": UserRole.MEMBER,
    },
]


def run_seed() -> None:
    db = SessionLocal()
    try:
        for m in MILESTONES:
            existing = db.execute(
                select(MilestoneDefinition).where(MilestoneDefinition.threshold == m["threshold"])
            ).scalar_one_or_none()
            if not existing:
                db.add(MilestoneDefinition(**m))

        db.flush()

        for u in USERS:
            existing_user = db.execute(
                select(User).where(User.email == u["email"])
            ).scalar_one_or_none()
            if not existing_user:
                new_user = User(
                    name=u["name"],
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    referral_code=u["referral_code"],
                    role=u["role"],
                )
                db.add(new_user)
                db.flush()
                db.add(
                    RewardBalance(
                        user_id=new_user.id,
                        balance=0,
                        successful_referral_count=0,
                    )
                )

        db.commit()
        print("Seed completed successfully! Milestones and default users are ready.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()