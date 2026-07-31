"""Shared FastAPI dependencies.

get_current_admin is the ONLY place organization_id and roles are extracted
from a request for admin routes — every repository call downstream takes that
organization_id explicitly. No admin endpoint accepts organization_id from the
request body/query and trusts it instead.
"""

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import TokenType, decode_token
from app.database import get_db
from app.models.organization import Organization


@dataclass(frozen=True)
class CurrentAdmin:
    admin_user_id: uuid.UUID
    organization_id: uuid.UUID
    roles: list[str]


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise UnauthorizedError("Missing bearer token")
    return auth_header.split(" ", 1)[1].strip()


def get_current_admin(request: Request) -> CurrentAdmin:
    token = _extract_bearer_token(request)
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    if payload.type != TokenType.ACCESS:
        raise UnauthorizedError("Refresh token used where access token required")

    return CurrentAdmin(
        admin_user_id=uuid.UUID(payload.sub),
        organization_id=uuid.UUID(payload.org_id),
        roles=payload.roles,
    )


CurrentAdminDep = Depends(get_current_admin)
DbDep = Depends(get_db)


def get_public_organization(db: Session = DbDep) -> Organization:
    """Resolves "the" organization for donor-facing public routes.

    v1 serves a single organization, so this simply loads the one seeded row.
    This is the ONLY place that decision is made — the future multi-tenant
    rollout (resolving by subdomain/custom-domain/slug instead) is a one-line
    change here, not a change to every public route handler. See
    docs/07-roadmap.md's multi-org roadmap entry.
    """
    organization = db.execute(select(Organization).limit(1)).scalar_one_or_none()
    if organization is None:
        raise AppError("No organization configured on this server — run alembic/seed.py")
    return organization


PublicOrgDep = Depends(get_public_organization)
