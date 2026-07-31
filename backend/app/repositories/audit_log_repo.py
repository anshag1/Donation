import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog


def list_paginated(
    db: Session,
    organization_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    entity_type: str | None = None,
    actor_admin_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    """Returns (items, total) where each item is (AuditLog, actor_email)."""
    base = (
        select(AuditLog, AdminUser.email)
        .outerjoin(AdminUser, AdminUser.id == AuditLog.actor_admin_user_id)
        .where(AuditLog.organization_id == organization_id)
    )
    if entity_type is not None:
        base = base.where(AuditLog.entity_type == entity_type)
    if actor_admin_user_id is not None:
        base = base.where(AuditLog.actor_admin_user_id == actor_admin_user_id)
    if date_from is not None:
        base = base.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        base = base.where(AuditLog.created_at <= date_to)

    total = db.execute(select(func.count()).select_from(base.with_only_columns(AuditLog.id).subquery())).scalar_one()
    rows = db.execute(
        base.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [(row[0], row[1]) for row in rows], total
