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


def send_admin_invite_email(
    settings: Settings, *, to_email: str, full_name: str, organization_name: str, invite_url: str
) -> bool:
    """Returns True if the email was actually dispatched to Resend. When
    Resend isn't configured, the caller (admin/users.py) falls back to
    surfacing `invite_url` directly in the API response to the super_admin
    who created the account — the same "real no-op, not a swallowed
    exception" pattern as `send_receipt_email` above.

    Deliberately does NOT log `invite_url` itself: it embeds a raw,
    single-use bearer token that's sufficient on its own to set that
    account's password (including a freshly-created super_admin account)
    via POST /auth/accept-invite. Application logs are routinely read by a
    wider audience (log aggregation, SRE, support) than the API response,
    which only reaches the super_admin who made the request — logging the
    token would hand out an account-takeover credential to anyone with log
    access, for as long as logs are retained (often well past the token's
    7-day validity)."""
    if not settings.resend_configured:
        logger.info(
            "RESEND_API_KEY not set — skipping real send. Would have emailed "
            "an invite link to %s (%s).",
            to_email,
            full_name,
        )
        return False

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"You've been invited to {organization_name}'s donation platform",
            "html": f"""
            <div style="font-family: Inter, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
              <h2 style="color:#3730a3;">Welcome, {full_name}!</h2>
              <p>You've been added as an admin for <strong>{organization_name}</strong>'s
              donation management platform.</p>
              <p><a href="{invite_url}" style="color:#3730a3;">Click here to set your password and sign in</a></p>
              <p style="color:#64748b; font-size: 13px;">This link expires in 7 days.</p>
            </div>
            """,
        }
    )
    return True


def send_password_reset_email(
    settings: Settings, *, to_email: str, full_name: str, reset_url: str
) -> bool:
    """Returns True if the email was actually dispatched to Resend.

    Unlike `send_admin_invite_email` above, there is NO API-response fallback
    here: `POST /auth/forgot-password` is called anonymously by whoever is
    trying to recover the account, not by an already-authenticated
    super_admin, so returning the reset link in the response would let
    anyone request a password reset for any email and get the takeover
    credential back directly — the exact bug class the invite-email logging
    fix (see docs/09-session-handoff.md) closed, reintroduced via a
    different channel. When Resend isn't configured, this logs only that a
    reset was requested — never the token/URL — so local-dev testing of this
    flow requires either a real Resend key or monkeypatching this function
    directly (see tests/integration/test_password_reset.py)."""
    if not settings.resend_configured:
        logger.info(
            "RESEND_API_KEY not set — skipping real send. A password reset "
            "was requested for %s (%s); no email sent.",
            to_email,
            full_name,
        )
        return False

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "Reset your donation platform admin password",
            "html": f"""
            <div style="font-family: Inter, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
              <h2 style="color:#3730a3;">Password reset requested</h2>
              <p>Hi {full_name}, we received a request to reset your admin password.</p>
              <p><a href="{reset_url}" style="color:#3730a3;">Click here to set a new password</a></p>
              <p style="color:#64748b; font-size: 13px;">This link expires in 1 hour. If you didn't
              request this, you can safely ignore this email — your password won't change.</p>
            </div>
            """,
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
