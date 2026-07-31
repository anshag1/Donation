"""Password hashing and JWT issuance/verification.

Native FastAPI auth (see docs/05-architecture.md — decided over Better
Auth/Clerk so the admin_users table + RBAC stay the single source of truth,
with no second system to keep in sync).
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt
from pydantic import BaseModel

from app.config import get_settings

ALGORITHM = "HS256"


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str  # admin_user_id
    org_id: str
    roles: list[str]
    type: TokenType
    iat: datetime
    exp: datetime
    jti: str  # unique per token — lets refresh tokens be revoked/rotated


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def _create_token(
    *, admin_user_id: uuid.UUID, organization_id: uuid.UUID, roles: list[str], token_type: TokenType, expires_delta: timedelta
) -> str:
    """Encodes iat/exp as numeric Unix timestamps (RFC 7519 NumericDate) —
    NOT ISO datetime strings. PyJWT's own expiry check assumes `exp` is
    numeric; encoding it as a string silently breaks verification on every
    token (a real bug caught while smoke-testing login end-to-end)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_user_id),
        "org_id": str(organization_id),
        "roles": roles,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def create_access_token(*, admin_user_id: uuid.UUID, organization_id: uuid.UUID, roles: list[str]) -> str:
    settings = get_settings()
    return _create_token(
        admin_user_id=admin_user_id,
        organization_id=organization_id,
        roles=roles,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(*, admin_user_id: uuid.UUID, organization_id: uuid.UUID, roles: list[str]) -> str:
    settings = get_settings()
    return _create_token(
        admin_user_id=admin_user_id,
        organization_id=organization_id,
        roles=roles,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def decode_token(token: str) -> TokenPayload:
    """Raises jwt.PyJWTError (expired/invalid signature/malformed) on failure —
    callers (app/deps.py) translate that into UnauthorizedError."""
    settings = get_settings()
    raw = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    return TokenPayload.model_validate(raw)
