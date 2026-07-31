import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import ADMIN, COORDINATOR, SUPER_ADMIN, TREASURER, VIEWER
from app.repositories import donor_repo
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.donor import DonorDetail, DonorDonationHistoryItem, DonorListItem

router = APIRouter(prefix="/admin/donors", tags=["admin:donors"])

ALL_AUTHENTICATED_ROLES = (SUPER_ADMIN, ADMIN, TREASURER, COORDINATOR, VIEWER)


@router.get("", response_model=ApiResponse[PaginatedData[DonorListItem]])
def list_donors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = None,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*ALL_AUTHENTICATED_ROLES)),
) -> ApiResponse[PaginatedData[DonorListItem]]:
    rows, total = donor_repo.list_paginated(
        db, current_admin.organization_id, page=page, page_size=page_size, q=q
    )
    items = [
        DonorListItem(
            id=donor.id,
            full_name=donor.full_name,
            mobile_number=donor.mobile_number,
            email=donor.email,
            total_donated_in_paise=total_donated,
            donation_count=count,
            last_donation_at=last_at,
        )
        for donor, total_donated, count, last_at in rows
    ]
    return ApiResponse(data=PaginatedData(items=items, page=page, page_size=page_size, total=total))


@router.get("/{donor_id}", response_model=ApiResponse[DonorDetail])
def get_donor(
    donor_id: uuid.UUID,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*ALL_AUTHENTICATED_ROLES)),
) -> ApiResponse[DonorDetail]:
    donor = donor_repo.get_by_id(db, current_admin.organization_id, donor_id)
    if donor is None:
        raise NotFoundError("Donor not found")

    donations = donor_repo.list_donations_for_donor(db, donor.id)
    history = [
        DonorDonationHistoryItem(
            id=donation.id,
            amount_in_paise=donation.amount_in_paise,
            status=donation.status,
            purpose=donation.purpose,
            event_title=event_title,
            receipt_number=receipt_number,
            created_at=donation.created_at,
        )
        for donation, receipt_number, event_title in donations
    ]

    return ApiResponse(
        data=DonorDetail(
            id=donor.id,
            full_name=donor.full_name,
            mobile_number=donor.mobile_number,
            email=donor.email,
            address=donor.address,
            pan_number=donor.pan_number,
            created_at=donor.created_at,
            donations=history,
        )
    )
