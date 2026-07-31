import hashlib
import hmac
import json
import uuid

import pytest

from app.config import get_settings
from app.core.exceptions import WebhookSignatureInvalidError
from app.models.donation import SUCCESS
from app.models.payment import CAPTURED
from app.services import webhook_service

WEBHOOK_SECRET = get_settings().razorpay_webhook_secret


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _captured_payload(*, event_id: str, razorpay_order_id: str, razorpay_payment_id: str) -> bytes:
    payload = {
        "id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "method": "upi",
                }
            }
        },
    }
    return json.dumps(payload).encode("utf-8")


def test_verify_signature_accepts_correctly_signed_body():
    body = b'{"hello": "world"}'
    signature = _sign(body)
    assert webhook_service.verify_signature(
        raw_body=body, signature=signature, webhook_secret=WEBHOOK_SECRET
    )


def test_verify_signature_rejects_tampered_body():
    body = b'{"hello": "world"}'
    signature = _sign(body)
    tampered_body = b'{"hello": "mallory"}'
    assert not webhook_service.verify_signature(
        raw_body=tampered_body, signature=signature, webhook_secret=WEBHOOK_SECRET
    )


def test_process_webhook_rejects_missing_signature(db):
    body = _captured_payload(
        event_id="evt_1", razorpay_order_id="order_x", razorpay_payment_id="pay_x"
    )
    with pytest.raises(WebhookSignatureInvalidError):
        webhook_service.process_webhook(db, get_settings(), raw_body=body, signature=None)


def test_process_webhook_rejects_invalid_signature(db):
    body = _captured_payload(
        event_id="evt_2", razorpay_order_id="order_x", razorpay_payment_id="pay_x"
    )
    with pytest.raises(WebhookSignatureInvalidError):
        webhook_service.process_webhook(
            db, get_settings(), raw_body=body, signature="0" * 64
        )


def test_process_webhook_captures_payment_and_is_idempotent(db, donation_with_payment):
    donation, payment = donation_with_payment
    event_id = f"evt_{uuid.uuid4().hex}"
    razorpay_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    body = _captured_payload(
        event_id=event_id,
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
    )
    signature = _sign(body)

    result = webhook_service.process_webhook(
        db, get_settings(), raw_body=body, signature=signature
    )
    assert result == donation.id

    db.refresh(donation)
    db.refresh(payment)
    assert donation.status == SUCCESS
    assert payment.status == CAPTURED
    assert payment.razorpay_payment_id == razorpay_payment_id

    # Replaying the exact same event must be a no-op (idempotency) — it must
    # NOT return a donation_id a second time (which would trigger a second
    # receipt generation for the same payment).
    replay_result = webhook_service.process_webhook(
        db, get_settings(), raw_body=body, signature=signature
    )
    assert replay_result is None


def test_process_webhook_unknown_order_id_does_not_raise(db):
    event_id = f"evt_{uuid.uuid4().hex}"
    body = _captured_payload(
        event_id=event_id, razorpay_order_id="order_does_not_exist", razorpay_payment_id="pay_x"
    )
    signature = _sign(body)
    result = webhook_service.process_webhook(db, get_settings(), raw_body=body, signature=signature)
    assert result is None
