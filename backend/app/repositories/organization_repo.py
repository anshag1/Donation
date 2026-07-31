import uuid

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.organization import OrganizationUpdateRequest


def get_by_id(db: Session, organization_id: uuid.UUID) -> Organization | None:
    return db.get(Organization, organization_id)


def update(db: Session, organization: Organization, request: OrganizationUpdateRequest) -> Organization:
    updates = request.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(organization, field, value)
    db.flush()
    return organization
