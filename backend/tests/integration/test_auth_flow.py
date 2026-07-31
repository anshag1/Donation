"""Covers the auth hardening added in this pass: audit logging on
login/failed-login, refresh-token rotation + revocation, and logout. See
docs/06-deployment-security.md and app/services/auth_service.py.
"""

from sqlalchemy import select

from app.config import get_settings
from app.core.rate_limit import limiter
from app.models.audit_log import AuditLog
from tests.conftest import ADMIN_TEST_PASSWORD


def test_login_success_writes_audit_log(client, admin_user, db):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD},
    )
    assert response.status_code == 200

    logs = db.execute(select(AuditLog).where(AuditLog.action == "admin_login")).scalars().all()
    assert len(logs) == 1
    assert logs[0].actor_admin_user_id == admin_user.id
    assert logs[0].organization_id == admin_user.organization_id


def test_login_failure_writes_audit_log_without_leaking_which_check_failed(client, admin_user, db):
    response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"

    logs = db.execute(select(AuditLog).where(AuditLog.action == "admin_login_failed")).scalars().all()
    assert len(logs) == 1
    assert logs[0].entity_id == admin_user.id


def test_login_with_unknown_email_returns_same_message_and_logs_nothing(client, db):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.org", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"
    assert db.execute(select(AuditLog)).scalars().all() == []


def test_account_locks_after_repeated_failed_logins_then_rejects_correct_password(client, admin_user, db):
    threshold = get_settings().login_lockout_threshold

    for _ in range(threshold):
        response = client.post(
            "/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"}
        )
        assert response.status_code == 401

    lock_logs = db.execute(select(AuditLog).where(AuditLog.action == "admin_account_locked")).scalars().all()
    assert len(lock_logs) == 1

    db.refresh(admin_user)
    assert admin_user.locked_until is not None
    # The counter resets when a lock triggers, so it doesn't grow unbounded.
    assert admin_user.failed_login_attempts == 0

    # Reset the per-IP limiter only (a separate, orthogonal mechanism) so this
    # next request is judged purely on account-lockout state, not slowapi's
    # "5/minute" cap, which the loop above would otherwise also have tripped.
    limiter.reset()
    still_locked_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    assert still_locked_response.status_code == 401
    assert still_locked_response.json()["error"]["message"] == "Invalid email or password"


def test_successful_login_resets_failed_attempt_counter(client, admin_user, db):
    client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"})
    client.post("/api/v1/auth/login", json={"email": admin_user.email, "password": "wrong-password"})

    ok_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    assert ok_response.status_code == 200

    db.refresh(admin_user)
    assert admin_user.failed_login_attempts == 0
    assert admin_user.locked_until is None


def test_refresh_rotates_token_and_revokes_the_old_one(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD},
    )
    old_refresh_cookie = client.cookies.get("refresh_token")
    assert old_refresh_cookie

    refresh_response = client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    new_access_token = refresh_response.json()["data"]["access_token"]
    assert new_access_token != login_response.json()["data"]["access_token"]

    new_refresh_cookie = client.cookies.get("refresh_token")
    assert new_refresh_cookie != old_refresh_cookie

    # Replaying the OLD refresh token (e.g. a stolen copy used after the
    # legitimate client already rotated) must now be rejected.
    client.cookies.set("refresh_token", old_refresh_cookie)
    replay_response = client.post("/api/v1/auth/refresh")
    assert replay_response.status_code == 401
    assert replay_response.json()["error"]["code"] == "UNAUTHORIZED"


def test_logout_revokes_the_refresh_token(client, admin_user):
    client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD},
    )

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200

    refresh_after_logout = client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_me_requires_bearer_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_admin_with_valid_token(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD},
    )
    access_token = login_response.json()["data"]["access_token"]

    me_response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_response.status_code == 200
    data = me_response.json()["data"]
    assert data["email"] == admin_user.email
    assert "super_admin" in data["roles"]
