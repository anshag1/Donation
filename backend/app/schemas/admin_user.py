import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.role import ALL_ROLES


def _validate_roles(v: list[str]) -> list[str]:
    invalid = set(v) - set(ALL_ROLES)
    if invalid:
        raise ValueError(f"Unknown role(s): {', '.join(sorted(invalid))}. Valid: {', '.join(ALL_ROLES)}")
    if not v:
        raise ValueError("At least one role is required")
    return v


class AdminUserListItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    roles: list[str]

    @field_validator("roles")
    @classmethod
    def _roles_valid(cls, v: list[str]) -> list[str]:
        return _validate_roles(v)


class AdminUserCreatedOut(AdminUserListItem):
    """Extends the normal list item with the invite link — visible ONLY in
    the response to the super_admin who just created this user, and only
    when Resend isn't configured to actually send it (local-dev fallback;
    see docs/06-deployment-security.md's "no real send but real no-op
    behavior" pattern already used for email/storage)."""

    invite_url: str | None = None


class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=200)


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    roles: list[str] | None = None
    is_active: bool | None = None

    @field_validator("roles")
    @classmethod
    def _roles_valid(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return _validate_roles(v)
