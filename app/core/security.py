from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def build_session_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(timezone.utc) + timedelta(minutes=settings.session_timeout_minutes)


def create_access_token(
    *,
    user_id: str,
    session_id: str,
    expires_at: datetime,
    secret_key: str,
    algorithm: str,
) -> str:
    if not secret_key:
        raise ValueError("JWT signing secret is not configured")
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "exp": expires_at,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> dict[str, Any]:
    if not secret_key:
        raise ValueError("JWT signing secret is not configured")
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def new_session_id() -> str:
    return uuid4().hex
