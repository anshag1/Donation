import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import SUPER_ADMIN, TREASURER
from app.repositories import audit_log_repo
from app.schemas.audit_log import AuditLogOut
from app.schemas.common import ApiResponse, PaginatedData

router = APIRouter(prefix="/admin/audit-logs", tags=["admin:audit-logs"])


@router.get("", response_model=ApiResponse[PaginatedData[AuditLogOut]])
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    entity_type: str | None = None,
    actor_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN, TREASURER)),
) -> ApiResponse[PaginatedData[AuditLogOut]]:
    rows, total = audit_log_repo.list_paginated(
        db,
        current_admin.organization_id,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        actor_admin_user_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
    items = [
        AuditLogOut(
            id=log.id,
            actor_admin_user_id=log.actor_admin_user_id,
            actor_email=actor_email,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before=log.before,
            after=log.after,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log, actor_email in rows
    ]
    return ApiResponse(data=PaginatedData(items=items, page=page, page_size=page_size, total=total))
