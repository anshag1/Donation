from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import SUPER_ADMIN
from app.repositories import organization_repo
from app.schemas.common import ApiResponse
from app.schemas.organization import OrganizationOut, OrganizationUpdateRequest
from app.services import audit_service

router = APIRouter(prefix="/admin/organization", tags=["admin:organization"])


@router.get("", response_model=ApiResponse[OrganizationOut])
def get_organization(
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[OrganizationOut]:
    organization = organization_repo.get_by_id(db, current_admin.organization_id)
    if organization is None:
        raise AppError("Organization not found for this account")
    return ApiResponse(data=OrganizationOut.model_validate(organization, from_attributes=True))


@router.patch("", response_model=ApiResponse[OrganizationOut])
def update_organization(
    body: OrganizationUpdateRequest,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[OrganizationOut]:
    organization = organization_repo.get_by_id(db, current_admin.organization_id)
    if organization is None:
        raise AppError("Organization not found for this account")

    before = OrganizationOut.model_validate(organization, from_attributes=True).model_dump(mode="json")
    organization = organization_repo.update(db, organization, body)
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="organization_updated",
        entity_type="organization",
        entity_id=organization.id,
        before=before,
        after=body.model_dump(mode="json", exclude_unset=True),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=OrganizationOut.model_validate(organization, from_attributes=True))
