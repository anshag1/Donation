"""TOTP (RFC 6238) two-factor authentication — enrollment QR + code
verification. `admin_users.two_factor_secret` already existed as a schema
placeholder (see docs/07-roadmap.md); this is the actual flow on top of it.
"""

import base64
from io import BytesIO

import pyotp
import qrcode

ISSUER_NAME = "Donation Platform"


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(*, secret: str, account_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER_NAME)


def qr_code_data_uri(otpauth_uri: str) -> str:
    """Renders the QR as a PNG, base64-embedded — no external image host, no
    new frontend dependency (the client just uses it as an <img src>)."""
    image = qrcode.make(otpauth_uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_code(*, secret: str, code: str) -> bool:
    """valid_window=1 tolerates +/-30s of clock drift between server and the
    donor's authenticator app, matching common TOTP implementations."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
