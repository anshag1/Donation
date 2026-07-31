"""End-to-end TOTP 2FA: enroll -> enable -> login now requires a second step
-> verify-2fa issues real tokens -> disable turns it back off. See
app/services/totp_service.py and docs/07-roadmap.md.
"""

import pyotp

from tests.conftest import ADMIN_TEST_PASSWORD, auth_headers


def _enable_2fa(client, access_token: str) -> str:
    """Runs setup + enable for the given already-authenticated admin, returns
    the TOTP secret so the test can generate valid codes afterward."""
    setup_response = client.post("/api/v1/auth/2fa/setup", headers=auth_headers(access_token))
    assert setup_response.status_code == 200, setup_response.text
    setup_data = setup_response.json()["data"]
    assert setup_data["qr_code_data_uri"].startswith("data:image/png;base64,")
    secret = setup_data["secret"]

    code = pyotp.TOTP(secret).now()
    enable_response = client.post(
        "/api/v1/auth/2fa/enable", json={"code": code}, headers=auth_headers(access_token)
    )
    assert enable_response.status_code == 200, enable_response.text
    return secret


def test_full_2fa_enrollment_and_login_flow(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["access_token"]

    secret = _enable_2fa(client, access_token)

    me_response = client.get("/api/v1/auth/me", headers=auth_headers(access_token))
    assert me_response.json()["data"]["two_factor_enabled"] is True

    # Logging in again now must NOT return tokens directly — no NEW refresh
    # cookie is set on this response (the cookie already on the client is
    # left over from the first, pre-2FA login above, not from this request).
    client.cookies.delete("refresh_token")
    second_login = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    assert second_login.status_code == 200
    second_login_data = second_login.json()["data"]
    assert second_login_data["mfa_required"] is True
    assert second_login_data["access_token"] is None
    mfa_token = second_login_data["mfa_token"]
    assert mfa_token
    assert client.cookies.get("refresh_token") is None

    # ...only completing the second step with a valid TOTP code does.
    verify_response = client.post(
        "/api/v1/auth/login/verify-2fa", json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()}
    )
    assert verify_response.status_code == 200, verify_response.text
    verify_data = verify_response.json()["data"]
    assert verify_data["mfa_required"] is False
    assert verify_data["access_token"]
    assert client.cookies.get("refresh_token")

    # Disabling requires a valid code too.
    disable_response = client.post(
        "/api/v1/auth/2fa/disable",
        json={"code": pyotp.TOTP(secret).now()},
        headers=auth_headers(verify_data["access_token"]),
    )
    assert disable_response.status_code == 200, disable_response.text

    third_login = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    assert third_login.json()["data"]["mfa_required"] is False
    assert third_login.json()["data"]["access_token"]


def test_verify_2fa_rejects_wrong_code(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["access_token"]
    _enable_2fa(client, access_token)

    second_login = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    mfa_token = second_login.json()["data"]["mfa_token"]

    bad_response = client.post(
        "/api/v1/auth/login/verify-2fa", json={"mfa_token": mfa_token, "code": "000000"}
    )
    assert bad_response.status_code == 401
    assert bad_response.json()["error"]["message"] == "Invalid or expired verification code"


def test_verify_2fa_rejects_tampered_mfa_token(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["access_token"]
    _enable_2fa(client, access_token)

    response = client.post(
        "/api/v1/auth/login/verify-2fa", json={"mfa_token": "not-a-real-token", "code": "123456"}
    )
    assert response.status_code == 401


def test_enable_2fa_rejects_wrong_code(client, admin_user):
    login_response = client.post(
        "/api/v1/auth/login", json={"email": admin_user.email, "password": ADMIN_TEST_PASSWORD}
    )
    access_token = login_response.json()["data"]["access_token"]

    client.post("/api/v1/auth/2fa/setup", headers=auth_headers(access_token))
    response = client.post(
        "/api/v1/auth/2fa/enable", json={"code": "000000"}, headers=auth_headers(access_token)
    )
    assert response.status_code == 400

    me_response = client.get("/api/v1/auth/me", headers=auth_headers(access_token))
    assert me_response.json()["data"]["two_factor_enabled"] is False
