import logging
import uuid

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter
from app.deps import DbDep, PublicOrgDep
from app.models.organization import Organization
from app.repositories import donation_repo, receipt_repo
from app.schemas.common import ApiResponse
from app.schemas.donation import (
    DonationClientCallback,
    DonationInitiateRequest,
    DonationInitiateResponse,
    DonationStatusResponse,
)
from app.services.donation_service import initiate_donation
from app.services.storage_service import get_storage_backend

logger = logging.getLogger("app.donations")

router = APIRouter(prefix="/donations", tags=["public:donations"])


@router.post("/initiate", response_model=ApiResponse[DonationInitiateResponse])
@limiter.limit("10/minute")
def initiate(
    request: Request,
    body: DonationInitiateRequest,
    db: Session = DbDep,
    organization: Organization = PublicOrgDep,
) -> ApiResponse[DonationInitiateResponse]:
    settings = get_settings()
    result = initiate_donation(db, settings, organization=organization, request=body)
    return ApiResponse(data=result)


@router.get("/{donation_id}/status", response_model=ApiResponse[DonationStatusResponse])
def get_status(
    donation_id: uuid.UUID,
    db: Session = DbDep,
    organization: Organization = PublicOrgDep,
) -> ApiResponse[DonationStatusResponse]:
    settings = get_settings()
    donation = donation_repo.get_by_id(db, organization.id, donation_id)
    if donation is None:
        raise NotFoundError("Donation not found")

    receipt = receipt_repo.get_by_donation_id(db, donation.id)
    download_url = None
    if receipt is not None:
        download_url = get_storage_backend(settings).get_signed_url(key=receipt.pdf_storage_key)

    return ApiResponse(
        data=DonationStatusResponse(
            status=donation.status,
            receipt_number=receipt.receipt_number if receipt else None,
            receipt_download_url=download_url,
        )
    )


@router.post("/{donation_id}/client-callback", response_model=ApiResponse[None])
def client_callback(
    donation_id: uuid.UUID,
    body: DonationClientCallback,
    organization: Organization = PublicOrgDep,
) -> ApiResponse[None]:
    """Informational only — logged for reconciliation telemetry. Never flips
    donation status; only the verified Razorpay webhook does that. See
    docs/02-user-flows.md §2.1."""
    logger.info(
        "Client callback for donation=%s org=%s order=%s payment=%s client_status=%s",
        donation_id,
        organization.id,
        body.razorpay_order_id,
        body.razorpay_payment_id,
        body.client_status,
    )
    return ApiResponse(data=None)
