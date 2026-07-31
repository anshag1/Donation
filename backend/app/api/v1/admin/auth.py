from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.deps import CurrentAdmin, CurrentAdminDep, DbDep
from app.repositories import admin_user_repo
from app.schemas.admin_user import AcceptInviteRequest
from app.schemas.auth import (
    CurrentAdminOut,
    LoginRequest,
    LoginResponse,
    TokenResponse,
    TwoFactorCodeRequest,
    TwoFactorLoginVerifyRequest,
    TwoFactorSetupResponse,
)
from app.schemas.common import ApiResponse
from app.services import audit_service, auth_service, totp_service

router = APIRouter(prefix="/auth", tags=["admin:auth"])

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        # Secure cookies are never sent by a client over plain HTTP — true in
        # any real deployment (staging/production, always behind TLS), but
        # deliberately false for "development" (local plain-http dev server)
        # AND "test" (httpx TestClient talks plain http://testserver; a
        # Secure-flagged cookie would silently vanish from every subsequent
        # request, which is exactly the bug this comment is here to prevent
        # reintroducing — it broke every refresh-token test on first write).
        secure=settings.environment not in ("development", "test"),
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )


@router.post("/login", response_model=ApiResponse[LoginResponse])
@limiter.limit("5/minute")
def login(
    request: Request, body: LoginRequest, response: Response, db: Session = DbDep
) -> ApiResponse[LoginResponse]:
    login_response, refresh_token, _admin_user = auth_service.login(
        db, email=body.email, password=body.password, ip_address=request.client.host if request.client else None
    )
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=login_response)


@router.post("/login/verify-2fa", response_model=ApiResponse[LoginResponse])
@limiter.limit("5/minute")
def login_verify_2fa(
    request: Request, body: TwoFactorLoginVerifyRequest, response: Response, db: Session = DbDep
) -> ApiResponse[LoginResponse]:
    login_response, refresh_token, _admin_user = auth_service.verify_login_2fa(
        db,
        mfa_token=body.mfa_token,
        code=body.code,
        ip_address=request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=login_response)


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
def refresh(request: Request, response: Response, db: Session = DbDep) -> ApiResponse[TokenResponse]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedError("No refresh token cookie present")

    token_response, new_refresh_token = auth_service.refresh(db, refresh_token=refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return ApiResponse(data=token_response)


@router.post("/accept-invite", response_model=ApiResponse[None])
@limiter.limit("5/minute")
def accept_invite(request: Request, body: AcceptInviteRequest, db: Session = DbDep) -> ApiResponse[None]:
    """Public by design — a newly-invited admin has no session yet. The raw
    token (see admin_user_repo.create) is the only proof of identity here;
    same generic message whether the token is unknown, already used, or
    expired, so this can't be used to probe for valid-but-expired tokens."""
    admin_user = admin_user_repo.get_by_invite_token(db, body.token)
    if (
        admin_user is None
        or admin_user.invite_expires_at is None
        or admin_user.invite_expires_at < datetime.now(UTC)
    ):
        raise UnauthorizedError("This invite link is invalid or has expired")

    admin_user_repo.accept_invite(db, admin_user, new_password_hash=hash_password(body.password))
    audit_service.record(
        db,
        organization_id=admin_user.organization_id,
        actor_admin_user_id=admin_user.id,
        action="admin_invite_accepted",
        entity_type="admin_user",
        entity_id=admin_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=None)


@router.post("/logout", response_model=ApiResponse[None])
def logout(request: Request, response: Response, db: Session = DbDep) -> ApiResponse[None]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    auth_service.logout(db, refresh_token=refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return ApiResponse(data=None)


@router.get("/me", response_model=ApiResponse[CurrentAdminOut])
def me(current_admin: CurrentAdmin = CurrentAdminDep, db: Session = DbDep) -> ApiResponse[CurrentAdminOut]:
    admin_user = admin_user_repo.get_by_id(db, current_admin.admin_user_id)
    if admin_user is None:
        raise UnauthorizedError("Account no longer exists")

    return ApiResponse(
        data=CurrentAdminOut(
            id=admin_user.id,
            organization_id=admin_user.organization_id,
            email=admin_user.email,
            full_name=admin_user.full_name,
            roles=admin_user.role_names,
            two_factor_enabled=admin_user.two_factor_enabled,
        )
    )


@router.post("/2fa/setup", response_model=ApiResponse[TwoFactorSetupResponse])
def setup_2fa(
    current_admin: CurrentAdmin = CurrentAdminDep, db: Session = DbDep
) -> ApiResponse[TwoFactorSetupResponse]:
    """Generates a new secret and stores it (but does NOT enable 2FA yet —
    that only happens once the caller proves they can generate a valid code
    from it, via /2fa/enable). Safe to call repeatedly; each call replaces
    any not-yet-confirmed secret from a previous, abandoned attempt."""
    admin_user = admin_user_repo.get_by_id(db, current_admin.admin_user_id)
    if admin_user is None:
        raise UnauthorizedError("Account no longer exists")
    if admin_user.two_factor_enabled:
        raise ValidationAppError("Two-factor authentication is already enabled — disable it first to re-enroll")

    secret = totp_service.generate_secret()
    admin_user.two_factor_secret = secret
    db.commit()

    otpauth_uri = totp_service.provisioning_uri(secret=secret, account_email=admin_user.email)
    return ApiResponse(
        data=TwoFactorSetupResponse(
            secret=secret,
            otpauth_uri=otpauth_uri,
            qr_code_data_uri=totp_service.qr_code_data_uri(otpauth_uri),
        )
    )


@router.post("/2fa/enable", response_model=ApiResponse[None])
def enable_2fa(
    body: TwoFactorCodeRequest,
    request: Request,
    current_admin: CurrentAdmin = CurrentAdminDep,
    db: Session = DbDep,
) -> ApiResponse[None]:
    admin_user = admin_user_repo.get_by_id(db, current_admin.admin_user_id)
    if admin_user is None:
        raise UnauthorizedError("Account no longer exists")
    if not admin_user.two_factor_secret:
        raise ValidationAppError("Call /2fa/setup first")
    if not totp_service.verify_code(secret=admin_user.two_factor_secret, code=body.code):
        raise ValidationAppError("Invalid verification code")

    admin_user.two_factor_enabled = True
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="admin_2fa_enabled",
        entity_type="admin_user",
        entity_id=admin_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=None)


@router.post("/2fa/disable", response_model=ApiResponse[None])
def disable_2fa(
    body: TwoFactorCodeRequest,
    request: Request,
    current_admin: CurrentAdmin = CurrentAdminDep,
    db: Session = DbDep,
) -> ApiResponse[None]:
    admin_user = admin_user_repo.get_by_id(db, current_admin.admin_user_id)
    if admin_user is None:
        raise UnauthorizedError("Account no longer exists")
    if not admin_user.two_factor_enabled or not admin_user.two_factor_secret:
        raise ValidationAppError("Two-factor authentication is not enabled")
    if not totp_service.verify_code(secret=admin_user.two_factor_secret, code=body.code):
        raise ValidationAppError("Invalid verification code")

    admin_user.two_factor_enabled = False
    admin_user.two_factor_secret = None
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="admin_2fa_disabled",
        entity_type="admin_user",
        entity_id=admin_user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=None)
