from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.deps import DbDep, PublicOrgDep
from app.models.event import ACTIVE, Event
from app.models.organization import Organization
from app.schemas.common import ApiResponse
from app.schemas.event import PublicEventOut

router = APIRouter(prefix="/events", tags=["public:events"])


@router.get("/public", response_model=ApiResponse[list[PublicEventOut]])
def list_public_events(
    db: Session = DbDep, organization: Organization = PublicOrgDep
) -> ApiResponse[list[PublicEventOut]]:
    stmt = select(Event).where(
        Event.organization_id == organization.id,
        Event.status == ACTIVE,
        Event.deleted_at.is_(None),
    )
    events = db.execute(stmt).scalars().all()
    return ApiResponse(data=[PublicEventOut.model_validate(e) for e in events])


@router.get("/public/{slug}", response_model=ApiResponse[PublicEventOut])
def get_public_event(
    slug: str, db: Session = DbDep, organization: Organization = PublicOrgDep
) -> ApiResponse[PublicEventOut]:
    stmt = select(Event).where(
        Event.organization_id == organization.id,
        Event.slug == slug,
        Event.deleted_at.is_(None),
    )
    event = db.execute(stmt).scalar_one_or_none()
    if event is None:
        raise NotFoundError("Event not found")
    return ApiResponse(data=PublicEventOut.model_validate(event))
