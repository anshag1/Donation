from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedRefreshToken


def is_revoked(db: Session, jti: str) -> bool:
    stmt = select(RevokedRefreshToken).where(RevokedRefreshToken.jti == jti)
    return db.execute(stmt).scalar_one_or_none() is not None


def revoke(db: Session, *, jti: str, expires_at: datetime) -> None:
    """Idempotent — revoking an already-revoked jti (e.g. a rare double
    request) is a no-op rather than a unique-constraint crash."""
    if is_revoked(db, jti):
        return
    db.add(RevokedRefreshToken(jti=jti, expires_at=expires_at))
    db.flush()
