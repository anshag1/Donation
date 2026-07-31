import uuid

import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    TokenType,
    create_access_token,
    create_mfa_pending_token,
    create_refresh_token,
    decode_mfa_pending_token,
    decode_token,
    verify_password,
)
from app.models.admin_user import AdminUser
from app.repositories import admin_user_repo, revoked_token_repo
from app.schemas.auth import LoginResponse, TokenResponse
from app.services import audit_service, totp_service

# Deliberately identical for every failure mode (no such user, wrong password,
# locked account) — a distinct "account locked" message would itself leak
# that the account exists, defeating the point of the enumeration-resistant
# message below.
INVALID_CREDENTIALS_MESSAGE = "Invalid email or password"
INVALID_2FA_CODE_MESSAGE = "Invalid or expired verification code"


def _register_failed_attempt(db: Session, admin_user: AdminUser, *, ip_address: str | None) -> None:
    """Shared by password and TOTP-code failures — both count against the
    same lockout threshold, since either is a failed proof-of-identity."""
    settings = get_settings()
    locked = admin_user_repo.is_locked(admin_user)
    just_locked = False
    if not locked and admin_user.is_active:
        just_locked = admin_user_repo.register_failed_login(
            db,
            admin_user,
            threshold=settings.login_lockout_threshold,
            lockout_minutes=settings.login_lockout_minutes,
        )
    audit_service.record(
        db,
        organization_id=admin_user.organization_id,
        actor_admin_user_id=None,
        action="admin_account_locked" if just_locked else "admin_login_failed",
        entity_type="admin_user",
        entity_id=admin_user.id,
        ip_address=ip_address,
    )
    db.commit()


def _issue_session(db: Session, admin_user: AdminUser, *, ip_address: str | None) -> tuple[LoginResponse, str]:
    roles = admin_user.role_names
    access_token = create_access_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )
    refresh_token = create_refresh_token(
        admin_user_id=admin_user.id, organization_id=admin_user.organization_id, roles=roles
    )

    admin_user_repo.reset_failed_login(db, admin_user)
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

    return LoginResponse(access_token=access_token), refresh_token


def login(
    db: Session, *, email: str, password: str, ip_address: str | None = None
) -> tuple[LoginResponse, str | None, AdminUser]:
    """Returns (login response, refresh token or None, admin user). The
    refresh token is None (and no tokens are present in the response) when
    the account has 2FA enabled — the caller must then complete
    `verify_login_2fa` before getting a real session. Raises
    UnauthorizedError on any failure — the message is deliberately identical
    for "no such user", "wrong password", and "account locked" so login can't
    be used to enumerate registered emails or fingerprint account state.
    """
    admin_user = admin_user_repo.get_by_email(db, email)

    if admin_user is None:
        # No organization to attribute this to — nothing safe to audit-log.
        raise UnauthorizedError(INVALID_CREDENTIALS_MESSAGE)

    locked = admin_user_repo.is_locked(admin_user)
    # Always run the (slow, constant-time) password check even when locked,
    # so a timing side-channel can't distinguish "locked" from "wrong
    # password" — the account stays rejected either way.
    password_matches = verify_password(password, admin_user.password_hash)

    if locked or not admin_user.is_active or not password_matches:
        _register_failed_attempt(db, admin_user, ip_address=ip_address)
        raise UnauthorizedError(INVALID_CREDENTIALS_MESSAGE)

    if admin_user.two_factor_enabled:
        mfa_token = create_mfa_pending_token(admin_user.id)
        return LoginResponse(mfa_required=True, mfa_token=mfa_token), None, admin_user

    login_response, refresh_token = _issue_session(db, admin_user, ip_address=ip_address)
    return login_response, refresh_token, admin_user


def verify_login_2fa(
    db: Session, *, mfa_token: str, code: str, ip_address: str | None = None
) -> tuple[LoginResponse, str, AdminUser]:
    """Second step of login for 2FA-enabled accounts. `mfa_token` proves the
    password check already passed (see `login` above); this only needs to
    check the TOTP code and then issue real tokens."""
    try:
        admin_user_id = decode_mfa_pending_token(mfa_token)
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError(INVALID_2FA_CODE_MESSAGE) from exc

    admin_user = admin_user_repo.get_by_id(db, admin_user_id)
    if admin_user is None or not admin_user.is_active or not admin_user.two_factor_enabled:
        raise UnauthorizedError(INVALID_2FA_CODE_MESSAGE)

    if admin_user_repo.is_locked(admin_user):
        raise UnauthorizedError(INVALID_2FA_CODE_MESSAGE)

    if not admin_user.two_factor_secret or not totp_service.verify_code(
        secret=admin_user.two_factor_secret, code=code
    ):
        _register_failed_attempt(db, admin_user, ip_address=ip_address)
        raise UnauthorizedError(INVALID_2FA_CODE_MESSAGE)

    login_response, refresh_token = _issue_session(db, admin_user, ip_address=ip_address)
    return login_response, refresh_token, admin_user


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
