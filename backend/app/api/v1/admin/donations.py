import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.organization import Organization
from app.models.role import ADMIN, COORDINATOR, SUPER_ADMIN, TREASURER, VIEWER
from app.repositories import donation_repo, receipt_repo
from app.schemas.common import ApiResponse, PaginatedData
from app.schemas.donation import (
    AdminDonationDetail,
    AdminDonationListItem,
    AdminPaymentOut,
    AdminReceiptOut,
)
from app.services import audit_service, email_service, receipt_service
from app.services.format_utils import format_inr
from app.services.storage_service import get_storage_backend

router = APIRouter(prefix="/admin/donations", tags=["admin:donations"])

RECEIPT_ACTION_ROLES = (SUPER_ADMIN, ADMIN, TREASURER)


def _to_list_item(donation, receipt_number: str | None, event_title: str | None) -> AdminDonationListItem:
    return AdminDonationListItem(
        id=donation.id,
        donor_name=donation.donor_snapshot_json.get("full_name", ""),
        donor_mobile=donation.donor_snapshot_json.get("mobile_number", ""),
        event_title=event_title,
        amount_in_paise=donation.amount_in_paise,
        status=donation.status,
        purpose=donation.purpose,
        receipt_number=receipt_number,
        created_at=donation.created_at,
    )


@router.get("", response_model=ApiResponse[PaginatedData[AdminDonationListItem]])
def list_donations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    event_id: uuid.UUID | None = None,
    donor_id: uuid.UUID | None = None,
    status: str | None = None,
    min_amount_in_paise: int | None = Query(default=None, ge=0),
    max_amount_in_paise: int | None = Query(default=None, ge=0),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*RECEIPT_ACTION_ROLES, COORDINATOR, VIEWER)),
) -> ApiResponse[PaginatedData[AdminDonationListItem]]:
    rows, total = donation_repo.list_paginated_admin(
        db,
        current_admin.organization_id,
        page=page,
        page_size=page_size,
        event_id=event_id,
        donor_id=donor_id,
        status=status,
        min_amount_in_paise=min_amount_in_paise,
        max_amount_in_paise=max_amount_in_paise,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    return ApiResponse(
        data=PaginatedData(
            items=[_to_list_item(d, r, e) for d, r, e in rows],
            page=page,
            page_size=page_size,
            total=total,
        )
    )


@router.get("/{donation_id}", response_model=ApiResponse[AdminDonationDetail])
def get_donation(
    donation_id: uuid.UUID,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*RECEIPT_ACTION_ROLES, COORDINATOR, VIEWER)),
) -> ApiResponse[AdminDonationDetail]:
    donation = donation_repo.get_full_detail(db, current_admin.organization_id, donation_id)
    if donation is None:
        raise NotFoundError("Donation not found")

    settings = get_settings()
    event_title = donation.event.title if donation.event_id and donation.event else None

    receipt_out = None
    if donation.receipt is not None:
        storage = get_storage_backend(settings)
        receipt_out = AdminReceiptOut(
            receipt_number=donation.receipt.receipt_number,
            duplicate_count=donation.receipt.duplicate_count,
            emailed_at=donation.receipt.emailed_at,
            download_url=storage.get_signed_url(key=donation.receipt.pdf_storage_key),
        )

    payment_out = None
    if donation.payment is not None:
        payment_out = AdminPaymentOut(
            razorpay_order_id=donation.payment.razorpay_order_id,
            razorpay_payment_id=donation.payment.razorpay_payment_id,
            status=donation.payment.status,
            method=donation.payment.method,
            failure_reason=donation.payment.failure_reason,
            captured_at=donation.payment.captured_at,
        )

    return ApiResponse(
        data=AdminDonationDetail(
            id=donation.id,
            organization_id=donation.organization_id,
            donor_id=donation.donor_id,
            donor_snapshot=donation.donor_snapshot_json,
            event_id=donation.event_id,
            event_title=event_title,
            amount_in_paise=donation.amount_in_paise,
            currency=donation.currency,
            purpose=donation.purpose,
            status=donation.status,
            created_at=donation.created_at,
            payment=payment_out,
            receipt=receipt_out,
        )
    )


@router.post("/{donation_id}/receipt/resend-email", response_model=ApiResponse[None])
def resend_receipt_email(
    donation_id: uuid.UUID,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*RECEIPT_ACTION_ROLES)),
) -> ApiResponse[None]:
    donation = donation_repo.get_full_detail(db, current_admin.organization_id, donation_id)
    if donation is None:
        raise NotFoundError("Donation not found")
    if donation.receipt is None:
        raise ValidationAppError("This donation does not have a receipt yet")

    donor_email = donation.donor_snapshot_json.get("email")
    if not donor_email:
        raise ValidationAppError("This donor did not provide an email address")

    settings = get_settings()
    organization = db.get(Organization, current_admin.organization_id)
    assert organization is not None

    storage = get_storage_backend(settings)
    pdf_bytes = storage.download(key=donation.receipt.pdf_storage_key)

    sent = email_service.send_receipt_email(
        settings,
        to_email=donor_email,
        donor_name=donation.donor_snapshot_json.get("full_name", ""),
        receipt_number=donation.receipt.receipt_number,
        amount_display=format_inr(donation.amount_in_paise),
        organization_name=organization.name,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{donation.receipt.receipt_number.replace('/', '_')}.pdf",
    )
    if sent:
        receipt_repo.mark_emailed(db, donation.receipt)

    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="receipt_resend_email",
        entity_type="donation",
        entity_id=donation.id,
        after={"receipt_number": donation.receipt.receipt_number, "sent": sent},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return ApiResponse(data=None)


@router.post("/{donation_id}/receipt/duplicate")
def generate_duplicate_receipt(
    donation_id: uuid.UUID,
    request: Request,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*RECEIPT_ACTION_ROLES)),
) -> Response:
    donation = donation_repo.get_full_detail(db, current_admin.organization_id, donation_id)
    if donation is None:
        raise NotFoundError("Donation not found")
    if donation.receipt is None:
        raise ValidationAppError("This donation does not have a receipt yet")
    if donation.payment is None:
        raise ValidationAppError("This donation has no payment on record")

    settings = get_settings()
    organization = db.get(Organization, current_admin.organization_id)
    assert organization is not None

    pdf_bytes = receipt_service.generate_duplicate_receipt(
        db,
        settings,
        organization=organization,
        donation=donation,
        original_receipt=donation.receipt,
        razorpay_payment_id=donation.payment.razorpay_payment_id or "",
        razorpay_order_id=donation.payment.razorpay_order_id,
    )

    audit_service.record(
        db,
        organization_id=current_admin.organization_id,
        actor_admin_user_id=current_admin.admin_user_id,
        action="receipt_duplicate_generated",
        entity_type="donation",
        entity_id=donation.id,
        after={"receipt_number": donation.receipt.receipt_number},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    filename = f"{donation.receipt.receipt_number.replace('/', '_')}_DUPLICATE.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
