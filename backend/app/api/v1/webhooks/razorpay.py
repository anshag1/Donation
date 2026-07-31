from fastapi import APIRouter, BackgroundTasks, Header, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import DbDep
from app.services.webhook_service import process_webhook
from app.worker.tasks import generate_receipt_and_email

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = DbDep,
    x_razorpay_signature: str | None = Header(default=None),
) -> dict:
    """Signature verified against the RAW body before any parsing — see
    app/services/webhook_service.py and docs/02-user-flows.md §2.5. Raises
    WebhookSignatureInvalidError (-> 400) on failure, which the global
    exception handler in main.py converts to the standard error envelope.

    Declared `async def` (rather than the `def` used elsewhere for DB-touching
    routes) because reading the raw body for signature verification requires
    `await request.body()`. Webhook volume is far lower than the public
    donation endpoints, so the brief synchronous DB work here does not risk
    starving the event loop the way it would on a high-traffic route.
    """
    raw_body = await request.body()
    settings = get_settings()
    donation_id_needing_receipt = process_webhook(
        db, settings, raw_body=raw_body, signature=x_razorpay_signature
    )
    if donation_id_needing_receipt is not None:
        background_tasks.add_task(generate_receipt_and_email, donation_id_needing_receipt)
    return {"data": {"received": True}, "error": None}
