import uuid

from pydantic import BaseModel, EmailStr, Field

TOTP_CODE_RE = r"^[0-9]{6}$"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Either tokens are issued directly (no 2FA on this account), or
    `mfa_required` is set and the client must call `/auth/login/verify-2fa`
    with `mfa_token` + a TOTP code before it gets any tokens at all."""

    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_token: str | None = None


class TwoFactorLoginVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(pattern=TOTP_CODE_RE)


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(pattern=TOTP_CODE_RE)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code_data_uri: str


class CurrentAdminOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    two_factor_enabled: bool
