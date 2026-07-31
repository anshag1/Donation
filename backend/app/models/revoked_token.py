from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class RevokedRefreshToken(Base, UUIDPKMixin):
    """Refresh-token revocation list, keyed by JWT `jti`. A row here means
    that refresh token can never be used again — checked on every
    /auth/refresh call, and populated both by explicit logout and by normal
    rotation (the old token is revoked the moment it's exchanged for a new
    one, closing the replay window this pass's original design left open).
    See docs/06-deployment-security.md.
    """

    __tablename__ = "revoked_refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
