import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.organization import Organization
from app.models.role import SUPER_ADMIN
from app.repositories import admin_user_repo
from app.schemas.admin_user import (
    AdminUserCreatedOut,
    AdminUserCreateRequest,
    AdminUserListItem,
    AdminUserUpdateRequest,
)
from app.schemas.common import ApiResponse, PaginatedData
from app.services import audit_service, email_service

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


def _to_list_item(user) -> AdminUserListItem:
    return AdminUserListItem(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=user.role_names,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("", response_model=ApiResponse[PaginatedData[AdminUserListItem]])
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[PaginatedData[AdminUserListItem]]:
    users, total = admin_user_repo.list_all(
        db, current_admin.organization_id, page=page, page_size=page_size
    )
    return ApiResponse(
        data=PaginatedData(
            items=[_to_list_item(u) for u in users], page=page, page_size=page_size, total=total
        )
    )


@router.post("", response_model=ApiResponse[AdminUserCreatedOut])
def create_user(
    body: AdminUserCreateRequest,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[AdminUserCreatedOut]:
    settings = get_settings()
    try:
        user, raw_invite_token = admin_user_repo.create(db, current_admin.organization_id, body)
        organization = db.get(Organization, current_admin.organization_id)
        invite_url = f"{settings.frontend_origin.rstrip('/')}/admin/accept-invite?token={raw_invite_token}"
        sent = email_service.send_admin_invite_email(
            settings,
            to_email=user.email,
            full_name=user.full_name,
            organization_name=organization.name if organization else "your organization",
            invite_url=invite_url,
        )
        audit_service.record(
            db,
            organization_id=current_admin.organization_id,
            actor_admin_user_id=current_admin.admin_user_id,
            action="admin_user_created",
            entity_type="admin_user",
            entity_id=user.id,
            after={"email": body.email, "roles": body.roles},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"A user with email '{body.email}' already exists") from exc
    db.refresh(user)
    return ApiResponse(
        data=AdminUserCreatedOut(**_to_list_item(user).model_dump(), invite_url=None if sent else invite_url)
    )


@router.patch("/{user_id}", response_model=ApiResponse[AdminUserListItem])
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[AdminUserListItem]:
    if user_id == current_admin.admin_user_id and body.is_active is False:
        raise ForbiddenError("You cannot deactivate your own account")
    if user_id == current_admin.admin_user_id and body.roles is not None and SUPER_ADMIN not in body.roles:
        raise ForbiddenError("You cannot remove your own super_admin role")

    user = admin_user_repo.get_by_id_in_org(db, current_admin.organization_id, user_id)
    if user is None:
        raise NotFoundError("User not found")

    before = {"roles": user.role_names, "is_active": user.is_active}
    user = admin_user_repo.update(db, user, body)
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="admin_user_updated",
        entity_type="admin_user",
        entity_id=user.id,
        before=before,
        after={"roles": user.role_names, "is_active": user.is_active},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    return ApiResponse(data=_to_list_item(user))
