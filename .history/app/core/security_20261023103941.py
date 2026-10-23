from datetime import datetime, timedelta, timezone
import secrets
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

password_hasher = PasswordHash.recommended()

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired", code="TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid authentication token", code="INVALID_TOKEN")


def generate_referral_code(length: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))