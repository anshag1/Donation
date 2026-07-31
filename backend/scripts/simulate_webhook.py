"""Exercises the full post-payment pipeline (webhook verify -> donation
success -> receipt numbering -> PDF render -> storage -> email attempt)
against the LOCAL DEV database, without needing a real Razorpay account.

It stands in only for the one step that genuinely requires Razorpay
credentials — creating a real payment order — by inserting a pending
donation/payment directly, exactly like `donation_service.initiate_donation`
would, then sending the backend a correctly-signed `payment.captured`
webhook, exactly as Razorpay would.

Usage (from backend/, with the venv active and uvicorn already running):
    python -m scripts.simulate_webhook
    python -m scripts.simulate_webhook --amount 25000 --email you@example.com

See docs/08-local-development.md for the full walkthrough.
"""

import argparse
import hashlib
import hmac
import json
import uuid

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.organization import Organization
from app.repositories import donation_repo, donor_repo
from app.schemas.donation import DonorInput


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amount", type=int, default=50000, help="Amount in paise (default: ₹500.00)")
    parser.add_argument("--full-name", default="Local Test Donor")
    parser.add_argument("--mobile", default="9876500123")
    parser.add_argument("--email", default="local-test-donor@example.com")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.razorpay_webhook_configured:
        raise SystemExit(
            "RAZORPAY_WEBHOOK_SECRET is not set in backend/.env — set it to any "
            "value for local testing (it only needs to match between this script "
            "and the running server)."
        )

    db = SessionLocal()
    try:
        organization = db.execute(select(Organization).limit(1)).scalar_one_or_none()
        if organization is None:
            raise SystemExit("No organization found — run `python -m scripts.seed` first.")

        donor = donor_repo.get_or_create(
            db,
            organization.id,
            DonorInput(full_name=args.full_name, mobile_number=args.mobile, email=args.email),
        )
        donation = donation_repo.create(
            db,
            organization_id=organization.id,
            donor_id=donor.id,
            event_id=None,
            amount_in_paise=args.amount,
            currency="INR",
            purpose="Local webhook simulation",
            donor_snapshot_json={
                "full_name": args.full_name,
                "mobile_number": args.mobile,
                "email": args.email,
            },
        )
        fake_order_id = f"order_sim{uuid.uuid4().hex[:14]}"
        donation_repo.create_payment(
            db,
            organization_id=organization.id,
            donation_id=donation.id,
            razorpay_order_id=fake_order_id,
            amount_in_paise=args.amount,
        )
        db.commit()
        donation_id = donation.id
        print(f"Created pending donation {donation_id} (order {fake_order_id})")
    finally:
        db.close()

    fake_payment_id = f"pay_sim{uuid.uuid4().hex[:14]}"
    payload = {
        "id": f"evt_sim{uuid.uuid4().hex}",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {"id": fake_payment_id, "order_id": fake_order_id, "method": "upi"}
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = _sign(raw_body, settings.razorpay_webhook_secret)

    response = httpx.post(
        f"{args.base_url}/api/v1/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": signature},
        timeout=10.0,
    )
    print(f"Webhook POST -> {response.status_code} {response.json()}")

    status_response = httpx.get(f"{args.base_url}/api/v1/donations/{donation_id}/status", timeout=10.0)
    status = status_response.json()["data"]
    print(f"Donation status: {status['status']}")
    if status.get("receipt_number"):
        print(f"Receipt number: {status['receipt_number']}")
        print(f"Download at:    {args.base_url}{status['receipt_download_url']}")


if __name__ == "__main__":
    main()
