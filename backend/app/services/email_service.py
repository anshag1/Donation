"""Transactional email via Resend. When RESEND_API_KEY is absent, this is a
real no-op provider (logs the would-be send) rather than a try/except swallow
— see docs/05-architecture.md's storage/email "adapter, not a shortcut" note.
"""

import logging

import resend

from app.config import Settings

logger = logging.getLogger("app.email")


def send_receipt_email(
    settings: Settings,
    *,
    to_email: str,
    donor_name: str,
    receipt_number: str,
    amount_display: str,
    organization_name: str,
    pdf_bytes: bytes,
    pdf_filename: str,
) -> bool:
    """Returns True if the email was actually dispatched to Resend."""
    if not settings.resend_configured:
        logger.info(
            "RESEND_API_KEY not set — skipping real send. Would have emailed "
            "receipt %s to %s (%s).",
            receipt_number,
            to_email,
            donor_name,
        )
        return False

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"Your donation receipt from {organization_name} ({receipt_number})",
            "html": _render_email_html(
                donor_name=donor_name,
                receipt_number=receipt_number,
                amount_display=amount_display,
                organization_name=organization_name,
            ),
            "attachments": [
                {
                    "filename": pdf_filename,
                    "content": list(pdf_bytes),
                }
            ],
        }
    )
    return True


def _render_email_html(
    *, donor_name: str, receipt_number: str, amount_display: str, organization_name: str
) -> str:
    return f"""
    <div style="font-family: Inter, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color:#3730a3;">Thank you, {donor_name}!</h2>
      <p>Your donation of <strong>{amount_display}</strong> to <strong>{organization_name}</strong>
      has been received and recorded.</p>
      <p>Receipt number: <strong>{receipt_number}</strong></p>
      <p>Your official receipt is attached to this email as a PDF.</p>
      <p style="color:#64748b; font-size: 13px; margin-top: 32px;">
        This is an automated message from {organization_name}'s donation platform.
      </p>
    </div>
    """
