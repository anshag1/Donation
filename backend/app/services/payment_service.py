"""Razorpay order creation. If RAZORPAY_KEY_ID/SECRET are absent (local-first
dev without a Razorpay account yet), this raises a clear PaymentOrderFailedError
rather than crashing — see docs/06-deployment-security.md and the plan's
"local-first" credentials decision.
"""

import logging
import uuid

import razorpay

from app.config import Settings
from app.core.exceptions import PaymentOrderFailedError

logger = logging.getLogger("app.payment")


def create_razorpay_order(
    settings: Settings, *, donation_id: uuid.UUID, amount_in_paise: int, currency: str = "INR"
) -> str:
    if not settings.razorpay_configured:
        raise PaymentOrderFailedError(
            "Razorpay is not configured on this server (RAZORPAY_KEY_ID / "
            "RAZORPAY_KEY_SECRET missing). Add test-mode keys to backend/.env "
            "to enable real checkout — see docs/08-local-development.md."
        )

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    try:
        order = client.order.create(
            {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": str(donation_id),
                "notes": {"donation_id": str(donation_id)},
            }
        )
    except Exception as exc:  # razorpay raises its own BadRequestError/ServerError types
        logger.exception("Razorpay order creation failed for donation %s", donation_id)
        raise PaymentOrderFailedError("Could not create payment order") from exc

    return order["id"]
