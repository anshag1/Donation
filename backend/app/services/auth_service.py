import uuid

import jwt
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.admin_user import AdminUser
from app.repositories import admin_user_repo, revoked_token_repo
from app.schemas.auth import TokenResponse
from app.services import audit_service


def login(
    db: Session, *, email: str, password: str, ip_address: str | None = None
) -> tuple[TokenResponse, str, AdminUser]:
    """Returns (access token response, refresh token, admin user). Raises
    UnauthorizedError on any failure — the message is deliberately identical
    for "no such user" and "wrong password" so login can't be used to enumerate
    registered emails.
    """
    admin_user = admin_user_repo.get_by_email(db, email)

    if admin_user is None:
        # No organization to attribute this to — nothing safe to audit-log.
        raise UnauthorizedError("Invalid email or password")

    if not admin_user.is_active or not verify_password(password, admin_user.password_hash):
        audit_service.record(
            db,
            organization_id=admin_user.organization_id,
            actor_admin_user_id=None,
            action="admin_login_failed",
            entity_type="admin_user",
            entity_id=admin_user.id,
            ip_address=ip_address,
        )
        db.commit()
        raise UnauthorizedError("Invalid email or password")

    roles = admin_user.role_names
    access_token = create_access_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )
    refresh_token = create_refresh_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )

    admin_user_repo.touch_last_login(db, admin_user)
    audit_service.record(
        db,
        organization_id=admin_user.organization_id,
        actor_admin_user_id=admin_user.id,
        action="admin_login",
        entity_type="admin_user",
        entity_id=admin_user.id,
        ip_address=ip_address,
    )
    db.commit()

    return TokenResponse(access_token=access_token), refresh_token, admin_user


def refresh(db: Session, *, refresh_token: str) -> tuple[TokenResponse, str]:
    """Rotates the refresh token on every use AND revokes the token being
    exchanged (inserted into `revoked_refresh_tokens` keyed by its `jti`) —
    closing the replay window a stolen-but-not-yet-used refresh token would
    otherwise have. See docs/06-deployment-security.md.
    """
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired refresh token") from exc

    if payload.type != TokenType.REFRESH:
        raise UnauthorizedError("Access token used where refresh token required")

    if revoked_token_repo.is_revoked(db, payload.jti):
        raise UnauthorizedError("This session has been signed out")

    admin_user = admin_user_repo.get_by_id(db, uuid.UUID(payload.sub))
    if admin_user is None or not admin_user.is_active:
        raise UnauthorizedError("Account no longer active")

    roles = admin_user.role_names
    new_access_token = create_access_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )
    new_refresh_token = create_refresh_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )

    revoked_token_repo.revoke(db, jti=payload.jti, expires_at=payload.exp)
    db.commit()

    return TokenResponse(access_token=new_access_token), new_refresh_token


def logout(db: Session, *, refresh_token: str | None) -> None:
    """Revokes the given refresh token's jti so it can never be exchanged
    again. Silently no-ops on a missing/invalid/already-expired token —
    logout must always succeed from the client's point of view."""
    if not refresh_token:
        return
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError:
        return
    if payload.type != TokenType.REFRESH:
        return

    revoked_token_repo.revoke(db, jti=payload.jti, expires_at=payload.exp)
    db.commit()
