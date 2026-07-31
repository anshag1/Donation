from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.core.file_validation import validate_image_upload
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import SUPER_ADMIN
from app.repositories import organization_repo
from app.schemas.common import ApiResponse
from app.schemas.organization import OrganizationOut, OrganizationUpdateRequest
from app.services import audit_service
from app.services.storage_service import get_storage_backend

router = APIRouter(prefix="/admin/organization", tags=["admin:organization"])


def _upload_org_asset(
    *,
    db: Session,
    request: Request,
    current_admin: CurrentAdmin,
    file: UploadFile,
    asset_name: str,
    field_setter,
    audit_action: str,
) -> OrganizationOut:
    organization = organization_repo.get_by_id(db, current_admin.organization_id)
    if organization is None:
        raise AppError("Organization not found for this account")

    content = file.file.read()
    content_type, extension = validate_image_upload(content)

    settings = get_settings()
    key = f"org-assets/{current_admin.organization_id}/{asset_name}.{extension}"
    get_storage_backend(settings).upload(key=key, content=content, content_type=content_type)

    before = OrganizationOut.model_validate(organization, from_attributes=True).model_dump(mode="json")
    url = f"{str(request.base_url).rstrip('/')}/api/v1/assets/{key}"
    field_setter(organization, url)
    db.flush()

    after = OrganizationOut.model_validate(organization, from_attributes=True).model_dump(mode="json")
    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action=audit_action,
        entity_type="organization",
        entity_id=organization.id,
        before=before,
        after=after,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return OrganizationOut.model_validate(organization, from_attributes=True)


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


@router.post("/logo", response_model=ApiResponse[OrganizationOut])
def upload_logo(
    request: Request,
    db: Session = DbDep,
    file: UploadFile = File(...),
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[OrganizationOut]:
    result = _upload_org_asset(
        db=db,
        request=request,
        current_admin=current_admin,
        file=file,
        asset_name="logo",
        field_setter=lambda org, url: setattr(org, "logo_url", url),
        audit_action="organization_logo_uploaded",
    )
    return ApiResponse(data=result)


@router.post("/signature", response_model=ApiResponse[OrganizationOut])
def upload_signature(
    request: Request,
    db: Session = DbDep,
    file: UploadFile = File(...),
    current_admin: CurrentAdmin = Depends(require_role(SUPER_ADMIN)),
) -> ApiResponse[OrganizationOut]:
    result = _upload_org_asset(
        db=db,
        request=request,
        current_admin=current_admin,
        file=file,
        asset_name="signature",
        field_setter=lambda org, url: setattr(org, "signature_image_url", url),
        audit_action="organization_signature_uploaded",
    )
    return ApiResponse(data=result)
