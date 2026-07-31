from fastapi import APIRouter, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.rate_limit import limiter
from app.deps import CurrentAdmin, CurrentAdminDep, DbDep
from app.repositories import admin_user_repo
from app.schemas.auth import CurrentAdminOut, LoginRequest, TokenResponse
from app.schemas.common import ApiResponse
from app.services import auth_service

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


@router.post("/login", response_model=ApiResponse[TokenResponse])
@limiter.limit("5/minute")
def login(
    request: Request, body: LoginRequest, response: Response, db: Session = DbDep
) -> ApiResponse[TokenResponse]:
    token_response, refresh_token, _admin_user = auth_service.login(
        db, email=body.email, password=body.password, ip_address=request.client.host if request.client else None
    )
    _set_refresh_cookie(response, refresh_token)
    return ApiResponse(data=token_response)


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
def refresh(request: Request, response: Response, db: Session = DbDep) -> ApiResponse[TokenResponse]:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise UnauthorizedError("No refresh token cookie present")

    token_response, new_refresh_token = auth_service.refresh(db, refresh_token=refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return ApiResponse(data=token_response)


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
        )
    )
