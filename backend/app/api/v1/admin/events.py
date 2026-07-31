import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import ADMIN, COORDINATOR, SUPER_ADMIN, TREASURER, VIEWER
from app.repositories import event_repo
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.event import AdminEventOut, EventCreateRequest, EventUpdateRequest
from app.services import audit_service

router = APIRouter(prefix="/admin/events", tags=["admin:events"])

EVENT_WRITE_ROLES = (SUPER_ADMIN, ADMIN, COORDINATOR)


@router.get("", response_model=ApiResponse[PaginatedData[AdminEventOut]])
def list_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*EVENT_WRITE_ROLES, TREASURER, VIEWER)),
) -> ApiResponse[PaginatedData[AdminEventOut]]:
    events, total = event_repo.list_paginated(
        db, current_admin.organization_id, page=page, page_size=page_size
    )
    return ApiResponse(
        data=PaginatedData(
            items=[AdminEventOut.model_validate(e) for e in events],
            page=page,
            page_size=page_size,
            total=total,
        )
    )


@router.post("", response_model=ApiResponse[AdminEventOut])
def create_event(
    body: EventCreateRequest,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*EVENT_WRITE_ROLES)),
) -> ApiResponse[AdminEventOut]:
    try:
        event = event_repo.create(db, current_admin.organization_id, body)
        audit_service.record(
            db,
            organization_id=current_admin.organization_id,
            actor_admin_user_id=current_admin.admin_user_id,
            action="event_created",
            entity_type="event",
            entity_id=event.id,
            after=body.model_dump(mode="json"),
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(f"An event with slug '{body.slug}' already exists") from exc
    return ApiResponse(data=AdminEventOut.model_validate(event))


@router.get("/{event_id}", response_model=ApiResponse[AdminEventOut])
def get_event(
    event_id: uuid.UUID,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*EVENT_WRITE_ROLES, TREASURER, VIEWER)),
) -> ApiResponse[AdminEventOut]:
    event = event_repo.get_by_id(db, current_admin.organization_id, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    return ApiResponse(data=AdminEventOut.model_validate(event))


@router.patch("/{event_id}", response_model=ApiResponse[AdminEventOut])
def update_event(
    event_id: uuid.UUID,
    body: EventUpdateRequest,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*EVENT_WRITE_ROLES)),
) -> ApiResponse[AdminEventOut]:
    event = event_repo.get_by_id(db, current_admin.organization_id, event_id)
    if event is None:
        raise NotFoundError("Event not found")

    before = AdminEventOut.model_validate(event).model_dump(mode="json")
    event = event_repo.update(db, event, body)
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="event_updated",
        entity_type="event",
        entity_id=event.id,
        before=before,
        after=body.model_dump(mode="json", exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=AdminEventOut.model_validate(event))


@router.delete("/{event_id}", response_model=ApiResponse[None])
def delete_event(
    event_id: uuid.UUID,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*EVENT_WRITE_ROLES)),
) -> ApiResponse[None]:
    event = event_repo.get_by_id(db, current_admin.organization_id, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    if event_repo.has_any_donations(db, event.id):
        raise ValidationAppError(
            "This event has donations recorded against it and cannot be deleted — close it instead"
        )

    event_repo.soft_delete(db, event)
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="event_deleted",
        entity_type="event",
        entity_id=event.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=None)
