import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.donation import Donation
from app.models.event import Event
from app.schemas.event import EventCreateRequest, EventUpdateRequest


def get_by_id(db: Session, organization_id: uuid.UUID, event_id: uuid.UUID) -> Event | None:
    stmt = select(Event).where(
        Event.organization_id == organization_id,
        Event.id == event_id,
        Event.deleted_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none()


def list_paginated(
    db: Session, organization_id: uuid.UUID, *, page: int, page_size: int
) -> tuple[list[Event], int]:
    base = select(Event).where(
        Event.organization_id == organization_id, Event.deleted_at.is_(None)
    )
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(
            base.order_by(Event.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(items), total


def create(db: Session, organization_id: uuid.UUID, request: EventCreateRequest) -> Event:
    event = Event(
        organization_id=organization_id,
        title=request.title,
        slug=request.slug,
        description=request.description,
        banner_url=request.banner_url,
        status=request.status,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    db.add(event)
    db.flush()
    return event


def update(db: Session, event: Event, request: EventUpdateRequest) -> Event:
    updates = request.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(event, field, value)
    db.flush()
    return event


def has_any_donations(db: Session, event_id: uuid.UUID) -> bool:
    stmt = select(Donation.id).where(Donation.event_id == event_id).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None


def soft_delete(db: Session, event: Event) -> None:
    event.deleted_at = func.now()
    db.flush()
