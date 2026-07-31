import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.donation import Donation
from app.models.organization import Organization
from app.models.receipt import Receipt
from app.repositories import receipt_repo
from app.services.amount_in_words import amount_in_paise_to_words
from app.services.format_utils import format_inr_for_pdf
from app.services.pdf.receipt_pdf import ReceiptPdfData, render_receipt_pdf
from app.services.storage_service import get_storage_backend

logger = logging.getLogger("app.receipt")


def financial_year_for(dt: datetime) -> str:
    """Indian financial year runs 1 April - 31 March, e.g. "2025-26"."""
    if dt.month >= 4:
        start, end = dt.year, dt.year + 1
    else:
        start, end = dt.year - 1, dt.year
    return f"{start}-{str(end)[-2:]}"


def generate_receipt_for_donation(
    db: Session,
    settings: Settings,
    *,
    organization: Organization,
    donation: Donation,
    razorpay_payment_id: str,
    razorpay_order_id: str,
) -> Receipt:
    """Allocates the receipt number, renders the PDF, and stores it. Must run
    inside the same DB transaction as the donation/payment status update that
    triggers it, so a crash midway can't leave a captured payment without a
    receipt number reserved. See docs/02-user-flows.md §2.6.
    """
    now = datetime.now(timezone.utc)
    fy = financial_year_for(now)

    receipt_number = receipt_repo.allocate_next_receipt_number(
        db,
        organization_id=organization.id,
        receipt_prefix=organization.receipt_prefix,
        financial_year=fy,
    )

    pdf_bytes = render_receipt_pdf(
        ReceiptPdfData(
            organization_name=organization.name,
            receipt_number=receipt_number,
            donation_date=now,
            donor_name=donation.donor_snapshot_json["full_name"],
            donor_mobile=donation.donor_snapshot_json["mobile_number"],
            amount_display=format_inr_for_pdf(donation.amount_in_paise),
            amount_in_words=amount_in_paise_to_words(donation.amount_in_paise),
            purpose=donation.purpose or "General Donation",
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
        )
    )

    storage = get_storage_backend(settings)
    storage_key = f"receipts/{organization.id}/{receipt_number.replace('/', '_')}.pdf"
    storage.upload(key=storage_key, content=pdf_bytes, content_type="application/pdf")

    receipt = receipt_repo.create(
        db,
        organization_id=organization.id,
        donation_id=donation.id,
        receipt_number=receipt_number,
        financial_year=fy,
        pdf_storage_key=storage_key,
    )

    logger.info("Generated receipt %s for donation %s", receipt_number, donation.id)
    return receipt


def generate_duplicate_receipt(
    db: Session,
    settings: Settings,
    *,
    organization: Organization,
    donation: Donation,
    original_receipt: Receipt,
    razorpay_payment_id: str,
    razorpay_order_id: str,
) -> bytes:
    """Re-renders a watermarked copy without allocating a new receipt number
    or storage record — the original remains the canonical receipt. Used by
    the (future) admin "generate duplicate" action; see docs/02-user-flows.md §2.8."""
    pdf_bytes = render_receipt_pdf(
        ReceiptPdfData(
            organization_name=organization.name,
            receipt_number=original_receipt.receipt_number,
            donation_date=donation.created_at,
            donor_name=donation.donor_snapshot_json["full_name"],
            donor_mobile=donation.donor_snapshot_json["mobile_number"],
            amount_display=format_inr_for_pdf(donation.amount_in_paise),
            amount_in_words=amount_in_paise_to_words(donation.amount_in_paise),
            purpose=donation.purpose or "General Donation",
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            is_duplicate=True,
        )
    )
    original_receipt.duplicate_count += 1
    db.flush()
    return pdf_bytes
