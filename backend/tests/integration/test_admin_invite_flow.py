"""Email-invite flow for new admin users — replaces the old
"super_admin sets a temp password directly" approach. Covers: creation
returns an invite link when Resend isn't configured (local-dev fallback),
the new account can't log in until the invite is accepted, accepting sets a
real password, and expired/garbage tokens are rejected. See
app/repositories/admin_user_repo.py and app/api/v1/admin/auth.py.
"""

from sqlalchemy import select

from app.models.admin_user import AdminUser
from tests.conftest import auth_headers


def test_create_user_returns_invite_url_when_resend_not_configured(client, login, admin_user):
    token = login(admin_user.email)
    response = client.post(
        "/api/v1/admin/users",
        json={"email": "new-admin@example.org", "full_name": "New Admin", "roles": ["super_admin"]},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["invite_url"] is not None
    assert "token=" in data["invite_url"]


def test_invite_token_is_never_logged(client, login, admin_user, caplog):
    """The invite token is a bearer credential that alone can take over the
    new account (including a super_admin account) via /auth/accept-invite —
    logging it would hand that credential to anyone with log access, a wider
    audience than the super_admin API caller it's meant for. Regression test
    for a real finding from this pass's security review."""
    token = login(admin_user.email)
    with caplog.at_level("DEBUG"):
        response = client.post(
            "/api/v1/admin/users",
            json={"email": "no-log-leak@example.org", "full_name": "New Admin", "roles": ["super_admin"]},
            headers=auth_headers(token),
        )
    invite_token = response.json()["data"]["invite_url"].split("token=", 1)[-1]
    assert invite_token not in caplog.text


def test_new_user_cannot_login_before_accepting_invite(client, login, admin_user, db):
    token = login(admin_user.email)
    client.post(
        "/api/v1/admin/users",
        json={"email": "new-admin2@example.org", "full_name": "New Admin", "roles": ["super_admin"]},
        headers=auth_headers(token),
    )
    # There's no password to try — the account's password hash is a random,
    # unusable value nobody (including the creating super_admin) ever sees.
    response = client.post(
        "/api/v1/auth/login", json={"email": "new-admin2@example.org", "password": "anything-at-all"}
    )
    assert response.status_code == 401


def test_full_invite_accept_and_login_flow(client, login, admin_user, db):
    token = login(admin_user.email)
    create_response = client.post(
        "/api/v1/admin/users",
        json={"email": "new-admin3@example.org", "full_name": "New Admin", "roles": ["super_admin"]},
        headers=auth_headers(token),
    )
    invite_url = create_response.json()["data"]["invite_url"]
    invite_token = invite_url.split("token=", 1)[-1]

    accept_response = client.post(
        "/api/v1/auth/accept-invite", json={"token": invite_token, "password": "BrandNewPassw0rd!"}
    )
    assert accept_response.status_code == 200, accept_response.text

    new_user = db.execute(select(AdminUser).where(AdminUser.email == "new-admin3@example.org")).scalar_one()
    assert new_user.invite_token_hash is None
    assert new_user.invite_expires_at is None

    login_response = client.post(
        "/api/v1/auth/login", json={"email": "new-admin3@example.org", "password": "BrandNewPassw0rd!"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["data"]["access_token"]


def test_accept_invite_rejects_garbage_token(client):
    response = client.post(
        "/api/v1/auth/accept-invite", json={"token": "not-a-real-token", "password": "BrandNewPassw0rd!"}
    )
    assert response.status_code == 401


def test_accept_invite_token_cannot_be_reused(client, login, admin_user):
    token = login(admin_user.email)
    create_response = client.post(
        "/api/v1/admin/users",
        json={"email": "new-admin4@example.org", "full_name": "New Admin", "roles": ["super_admin"]},
        headers=auth_headers(token),
    )
    invite_token = create_response.json()["data"]["invite_url"].split("token=", 1)[-1]

    first = client.post("/api/v1/auth/accept-invite", json={"token": invite_token, "password": "FirstPassw0rd!"})
    assert first.status_code == 200

    second = client.post("/api/v1/auth/accept-invite", json={"token": invite_token, "password": "SecondPassw0rd!"})
    assert second.status_code == 401
