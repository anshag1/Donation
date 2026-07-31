"""End-to-end: POST /donations/initiate -> simulate a correctly-signed
Razorpay webhook -> assert the donation reaches `success` with a receipt
number, a stored PDF, and (since RESEND_API_KEY is unset in tests) a
gracefully-skipped email — mirroring exactly what a real donor does, minus
needing a live Razorpay account. See docs/02-user-flows.md §2.1.
"""

import hashlib
import hmac
import json
import uuid

from app.config import get_settings
from app.services.storage_service import LOCAL_STORAGE_ROOT

WEBHOOK_SECRET = get_settings().razorpay_webhook_secret


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_full_donation_flow_success(client, organization, monkeypatch, db):
    fake_order_id = f"order_{uuid.uuid4().hex[:14]}"
    monkeypatch.setattr(
        "app.services.donation_service.create_razorpay_order",
        lambda settings, *, donation_id, amount_in_paise, currency="INR": fake_order_id,
    )

    initiate_response = client.post(
        "/api/v1/donations/initiate",
        json={
            "event_id": None,
            "donor": {
                "full_name": "Jane Donor",
                "mobile_number": "9876500001",
                "email": "jane.donor@example.com",
            },
            "amount_in_paise": 250000,
            "purpose": "Integration test donation",
        },
    )
    assert initiate_response.status_code == 200, initiate_response.text
    body = initiate_response.json()["data"]
    assert body["razorpay_order_id"] == fake_order_id
    donation_id = body["donation_id"]

    status_before = client.get(f"/api/v1/donations/{donation_id}/status")
    assert status_before.json()["data"]["status"] == "pending"

    razorpay_payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    webhook_payload = {
        "id": f"evt_{uuid.uuid4().hex}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": razorpay_payment_id,
                    "order_id": fake_order_id,
                    "method": "upi",
                }
            }
        },
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    signature = _sign(raw_body)

    webhook_response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert webhook_response.status_code == 200, webhook_response.text

    status_after = client.get(f"/api/v1/donations/{donation_id}/status").json()["data"]
    assert status_after["status"] == "success"
    assert status_after["receipt_number"] is not None
    assert status_after["receipt_number"].startswith("TEST/")
    assert status_after["receipt_download_url"] is not None

    # The receipt PDF was actually rendered and written to local storage —
    # since SUPABASE_* env vars are unset, LocalFilesystemStorage is in play.
    receipt_number = status_after["receipt_number"]
    storage_key = f"receipts/{organization.id}/{receipt_number.replace('/', '_')}.pdf"
    pdf_path = LOCAL_STORAGE_ROOT / storage_key
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_donation_initiate_rejects_invalid_mobile_number(client, organization):
    response = client.post(
        "/api/v1/donations/initiate",
        json={
            "event_id": None,
            "donor": {"full_name": "Bad Mobile", "mobile_number": "abc123"},
            "amount_in_paise": 10000,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_webhook_with_bad_signature_is_rejected(client, organization, donation_with_payment):
    _, payment = donation_with_payment
    payload = {
        "id": "evt_bad_sig",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {"id": "pay_x", "order_id": payment.razorpay_order_id, "method": "upi"}
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    response = client.post(
        "/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"X-Razorpay-Signature": "0" * 64, "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"
