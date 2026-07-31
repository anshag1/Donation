"""Razorpay webhook processing. See docs/02-user-flows.md §2.5 for the full
flowchart this implements: verify signature -> idempotent upsert into
webhook_events -> single transaction updates payment+donation -> on capture,
hand off receipt generation to a background task (app/worker/tasks.py) so the
webhook response isn't blocked on PDF rendering or SMTP latency.
"""

import json
import logging
import uuid

import razorpay
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import WebhookSignatureInvalidError
from app.models.donation import FAILED as DONATION_FAILED
from app.models.donation import SUCCESS as DONATION_SUCCESS
from app.models.donation import Donation
from app.models.payment import CAPTURED, FAILED
from app.models.webhook_event import WebhookEvent
from app.repositories import donation_repo
from app.services import audit_service

logger = logging.getLogger("app.webhook")

HANDLED_EVENT_TYPES = {"payment.captured", "payment.failed"}


def verify_signature(*, raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    try:
        # Utility.verify_webhook_signature is an instance method (takes `self`)
        # — calling it off the class directly silently misassigns arguments.
        razorpay.Utility().verify_webhook_signature(
            raw_body.decode("utf-8"), signature, webhook_secret
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def process_webhook(
    db: Session,
    settings: Settings,
    *,
    raw_body: bytes,
    signature: str | None,
) -> uuid.UUID | None:
    """Raises WebhookSignatureInvalidError on a bad/missing signature. Every
    other outcome (already processed, unhandled event type, success, failure)
    is a normal return — Razorpay must always get a fast 200 once the
    signature is valid, per docs/02-user-flows.md §2.5.

    Returns the donation_id to generate a receipt for, if this call is the
    one that just transitioned that donation to `success` — the caller (the
    webhook route) is responsible for dispatching that as a background task.
    Returns None otherwise.
    """
    if not settings.razorpay_webhook_configured:
        raise WebhookSignatureInvalidError("Webhook secret not configured on this server")
    if not signature or not verify_signature(
        raw_body=raw_body, signature=signature, webhook_secret=settings.razorpay_webhook_secret
    ):
        raise WebhookSignatureInvalidError("Signature verification failed")

    payload = json.loads(raw_body)
    event_id = payload.get("id") or ""
    event_type = payload.get("event") or ""

    if _already_processed(db, event_id):
        logger.info("Webhook event %s already processed — no-op", event_id)
        return None

    webhook_event = WebhookEvent(
        provider="razorpay",
        event_id=event_id,
        event_type=event_type,
        raw_payload=payload,
        processed=False,
    )
    db.add(webhook_event)
    db.flush()

    if event_type not in HANDLED_EVENT_TYPES:
        webhook_event.processed = True
        db.commit()
        return None

    entity = payload["payload"]["payment"]["entity"]
    razorpay_order_id = entity["order_id"]
    razorpay_payment_id = entity["id"]

    payment = donation_repo.get_payment_by_razorpay_order_id(db, razorpay_order_id)
    if payment is None:
        logger.error(
            "Webhook for unknown razorpay_order_id=%s (event %s)", razorpay_order_id, event_id
        )
        webhook_event.processed = True
        db.commit()
        return None

    donation = donation_repo.get_by_id_for_update(db, payment.donation_id)
    if donation is None:
        webhook_event.processed = True
        db.commit()
        return None

    webhook_event.organization_id = donation.organization_id

    needs_receipt = False
    if event_type == "payment.captured":
        needs_receipt = _apply_captured(
            donation=donation,
            razorpay_payment_id=razorpay_payment_id,
            method=entity.get("method"),
        )
        if needs_receipt:
            audit_service.record(
                db,
                organization_id=donation.organization_id,
                actor_admin_user_id=None,  # system-triggered, not an admin action
                action="donation_confirmed",
                entity_type="donation",
                entity_id=donation.id,
                after={"status": DONATION_SUCCESS, "razorpay_payment_id": razorpay_payment_id},
            )
    elif event_type == "payment.failed":
        donation.payment.status = FAILED
        donation.payment.failure_reason = entity.get("error_description")
        donation.status = DONATION_FAILED
        audit_service.record(
            db,
            organization_id=donation.organization_id,
            actor_admin_user_id=None,
            action="donation_payment_failed",
            entity_type="donation",
            entity_id=donation.id,
            after={"status": DONATION_FAILED, "failure_reason": entity.get("error_description")},
        )

    webhook_event.processed = True
    db.commit()

    return donation.id if needs_receipt else None


def _already_processed(db: Session, event_id: str) -> bool:
    stmt = select(WebhookEvent).where(
        WebhookEvent.provider == "razorpay", WebhookEvent.event_id == event_id
    )
    existing = db.execute(stmt).scalar_one_or_none()
    return bool(existing and existing.processed)


def _apply_captured(*, donation: Donation, razorpay_payment_id: str, method: str | None) -> bool:
    """Returns True if this call is the one moving the donation into `success`
    (i.e. a receipt now needs generating), False if it was already there."""
    if donation.status == DONATION_SUCCESS:
        return False  # already handled by a prior delivery carrying the same outcome

    donation.payment.status = CAPTURED
    donation.payment.razorpay_payment_id = razorpay_payment_id
    donation.payment.method = method
    donation.payment.captured_at = func.now()
    donation.status = DONATION_SUCCESS
    return True
