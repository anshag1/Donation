import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_admin_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert-only — there is deliberately no update/delete function for this
    table. See docs/06-deployment-security.md §6.3 (Audit Logging)."""
    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_admin_user_id=actor_admin_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip_address=ip_address,
        )
    )
    db.flush()
