"""Self-service password reset — lets an admin recover access without a
super_admin (or a direct database edit) manually intervening. Covers:
no account-enumeration via /forgot-password, the reset token is never
logged or returned in the response (unlike the invite flow, which is safe
to return to an already-authenticated super_admin — this endpoint is called
anonymously), token expiry/reuse rejection, and that a successful reset also
clears any active account lockout. See app/repositories/admin_user_repo.py
and app/api/v1/admin/auth.py.
"""

import hashlib
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from tests.conftest import ADMIN_TEST_PASSWORD


def _capture_reset_url(monkeypatch) -> dict:
    """Monkeypatches the email service to capture the reset_url that WOULD
    have been sent, without needing Resend configured or a live send. This
    endpoint deliberately never returns the token in its own response (see
    its docstring), so tests can't extract it from the HTTP response the way
    the invite-flow tests do."""
    captured = {}

    def _fake_send(settings, *, to_email, full_name, reset_url):
        captured["to_email"] = to_email
        captured["full_name"] = full_name
        captured["reset_url"] = reset_url
        return False

    monkeypatch.setattr("app.api.v1.admin.auth.email_service.send_password_reset_email", _fake_send)
    return captured


def test_forgot_password_always_returns_success_for_unknown_email(client):
    response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.org"})
    assert response.status_code == 200
    assert response.json()["error"] is None


def test_forgot_password_returns_success_and_does_not_expose_token(client, admin_user, monkeypatch):
    captured = _capture_reset_url(monkeypatch)
    response = client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    assert response.status_code == 200
    # The response body must never contain the reset token — only the email
    # service (mocked here) sees it.
    assert response.json() == {"data": None, "error": None}
    assert captured["to_email"] == admin_user.email
    assert "token=" in captured["reset_url"]


def test_forgot_password_token_is_never_logged(client, admin_user, monkeypatch, caplog):
    """Regression test mirroring test_invite_token_is_never_logged — a
    forgot-password token is just as much an account-takeover credential as
    an invite token, and must never end up in application logs."""
    captured = _capture_reset_url(monkeypatch)
    with caplog.at_level("DEBUG"):
        client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    reset_token = captured["reset_url"].split("token=", 1)[-1]
    assert reset_token not in caplog.text


def test_full_forgot_and_reset_password_flow(client, admin_user, monkeypatch, db):
    captured = _capture_reset_url(monkeypatch)
    client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    reset_token = captured["reset_url"].split("token=", 1)[-1]

    reset_response = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token, "password": "BrandNewPassw0rd!"}
    )
    assert reset_response.status_code == 200, reset_response.text

    db.refresh(admin_user)
    assert admin_user.password_reset_token_hash is None
    assert admin_user.password_reset_expires_at is None

    # Old password no longer works...
    old_login = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    assert old_login.status_code == 401

    # ...only the new one does.
    new_login = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": "BrandNewPassw0rd!"}
    )
    assert new_login.status_code == 200
    assert new_login.json()["data"]["access_token"]


def test_reset_password_rejects_garbage_token(client):
    response = client.post(
        "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "password": "BrandNewPassw0rd!"}
    )
    assert response.status_code == 401


def test_reset_password_rejects_expired_token(client, admin_user, db):
    """Constructs a token whose hash we know (so we can present the matching
    raw token) but whose expiry is already in the past, to specifically
    exercise the expiry check rather than the "token not found" path."""
    raw_token = "test-raw-token-for-expiry-check"
    admin_user.password_reset_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    admin_user.password_reset_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    response = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "password": "BrandNewPassw0rd!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "This password reset link is invalid or has expired"


def test_reset_password_token_cannot_be_reused(client, admin_user, monkeypatch):
    captured = _capture_reset_url(monkeypatch)
    client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    reset_token = captured["reset_url"].split("token=", 1)[-1]

    first = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token, "password": "FirstNewPassw0rd!"}
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token, "password": "SecondNewPassw0rd!"}
    )
    assert second.status_code == 401


def test_reset_password_clears_account_lockout(client, admin_user, monkeypatch, db):
    threshold = get_settings().login_lockout_threshold
    for _ in range(threshold):
        client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"})

    db.refresh(admin_user)
    assert admin_user.locked_until is not None

    captured = _capture_reset_url(monkeypatch)
    client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    reset_token = captured["reset_url"].split("token=", 1)[-1]

    reset_response = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token, "password": "UnlockedPassw0rd!"}
    )
    assert reset_response.status_code == 200

    db.refresh(admin_user)
    assert admin_user.locked_until is None
    assert admin_user.failed_login_attempts == 0

    # Reset the per-IP limiter (a separate, orthogonal mechanism) so this
    # next request is judged purely on account state, not slowapi's cap,
    # which the loop above would also have tripped.
    from app.core.rate_limit import limiter

    limiter.reset()
    login_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": "UnlockedPassw0rd!"}
    )
    assert login_response.status_code == 200


def test_forgot_password_requesting_twice_invalidates_the_first_token(client, admin_user, monkeypatch):
    """set_password_reset_token overwrites any previous unused token — only
    the most recently requested reset link should ever work."""
    captured1 = _capture_reset_url(monkeypatch)
    client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    first_token = captured1["reset_url"].split("token=", 1)[-1]

    captured2 = _capture_reset_url(monkeypatch)
    client.post("/api/v1/auth/forgot-password", json={"email": admin_user.email})
    second_token = captured2["reset_url"].split("token=", 1)[-1]

    assert first_token != second_token

    stale_response = client.post(
        "/api/v1/auth/reset-password", json={"token": first_token, "password": "ShouldNotWork1!"}
    )
    assert stale_response.status_code == 401

    fresh_response = client.post(
        "/api/v1/auth/reset-password", json={"token": second_token, "password": "ShouldWork123!"}
    )
    assert fresh_response.status_code == 200
