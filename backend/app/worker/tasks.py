"""Background task bodies, run via FastAPI's BackgroundTasks (in-process,
after the response is sent). Each task opens its OWN database session rather
than reusing the request-scoped one — the request's session may already be
torn down by the time a background task runs, and sharing it across the
request/background boundary is a well-known FastAPI footgun.

v1 scale doesn't need a durable task queue; if donation volume ever makes an
in-process task an unacceptable risk to lose on redeploy, promote this to
Celery/RQ + Redis without changing the call sites — see docs/07-roadmap.md.
"""

import logging
import uuid

from app.config import get_settings
from app.database import SessionLocal
from app.models.donation import Donation
from app.models.organization import Organization
from app.repositories import receipt_repo
from app.services import email_service, receipt_service
from app.services.format_utils import format_inr
from app.services.storage_service import get_storage_backend

logger = logging.getLogger("app.worker")


def generate_receipt_and_email(donation_id: uuid.UUID) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        donation = db.get(Donation, donation_id)
        if donation is None:
            logger.error("generate_receipt_and_email: donation %s not found", donation_id)
            return

        organization = db.get(Organization, donation.organization_id)
        if organization is None:
            logger.error("generate_receipt_and_email: organization for donation %s not found", donation_id)
            return

        assert donation.payment is not None
        receipt = receipt_service.generate_receipt_for_donation(
            db,
            settings,
            organization=organization,
            donation=donation,
            razorpay_payment_id=donation.payment.razorpay_payment_id or "",
            razorpay_order_id=donation.payment.razorpay_order_id,
        )
        db.commit()

        donor_email = donation.donor_snapshot_json.get("email")
        if donor_email:
            storage = get_storage_backend(settings)
            pdf_bytes = storage.download(key=receipt.pdf_storage_key)
            sent = email_service.send_receipt_email(
                settings,
                to_email=donor_email,
                donor_name=donation.donor_snapshot_json["full_name"],
                receipt_number=receipt.receipt_number,
                amount_display=format_inr(donation.amount_in_paise),
                organization_name=organization.name,
                pdf_bytes=pdf_bytes,
                pdf_filename=f"{receipt.receipt_number.replace('/', '_')}.pdf",
            )
            if sent:
                receipt_repo.mark_emailed(db, receipt)
                db.commit()
    except Exception:
        db.rollback()
        logger.exception("generate_receipt_and_email failed for donation %s", donation_id)
    finally:
        db.close()
