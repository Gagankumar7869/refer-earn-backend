from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.entities import User
from app.schemas.auth import LoginRequest, TokenResponse, UserProfileResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    stmt = select(User).where(User.email == payload.email.lower().strip())
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")

    token = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        user=UserProfileResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.value,
            referral_code=user.referral_code,
        ),
    )


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.value,
        referral_code=current_user.referral_code,
    )