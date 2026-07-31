"""Real file upload for event banners + org logo/signature. Covers: RBAC on
the multipart endpoints (not part of test_admin_endpoints_security.py's
generic sweep since that sweep sends JSON bodies, which don't fit multipart
semantics), magic-byte validation, size limits, and that the public asset
route can only ever serve the two allowlisted prefixes — never receipts.
"""

from tests.conftest import auth_headers

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
NOT_AN_IMAGE = b"this is definitely not an image file"


def _make_event(client, token, *, title="Test Event", slug="test-event"):
    response = client.post(
        "/api/v1/admin/events",
        json={"title": title, "slug": slug, "status": "active"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_upload_event_banner_stores_file_and_is_publicly_fetchable(client, login, admin_user):
    token = login(admin_user.email)
    event_id = _make_event(client, token)

    upload_response = client.post(
        f"/api/v1/admin/events/{event_id}/banner",
        files={"file": ("banner.png", FAKE_PNG, "image/png")},
        headers=auth_headers(token),
    )
    assert upload_response.status_code == 200, upload_response.text
    banner_url = upload_response.json()["data"]["banner_url"]
    assert "/api/v1/assets/event-banners/" in banner_url

    # banner_url is absolute (http://testserver/api/v1/assets/...) — strip the
    # scheme+host so TestClient can hit it as a relative path.
    relative_path = banner_url.replace("http://testserver", "")
    fetch_response = client.get(relative_path, follow_redirects=False)
    assert fetch_response.status_code in (302, 307)

    # Following the redirect must serve the image with a real image
    # Content-Type — local dev's serve_local_file() used to hardcode
    # "application/pdf" (it originally only ever served receipts), which
    # made browsers refuse to render it as an <img> under the app's
    # X-Content-Type-Options: nosniff header. A real bug this pass hit.
    local_file_response = client.get(fetch_response.headers["location"])
    assert local_file_response.status_code == 200
    assert local_file_response.headers["content-type"] == "image/png"


def test_upload_event_banner_requires_auth(client, admin_user):
    response = client.post(
        "/api/v1/admin/events/00000000-0000-0000-0000-000000000000/banner",
        files={"file": ("banner.png", FAKE_PNG, "image/png")},
    )
    assert response.status_code == 401


def test_upload_event_banner_forbidden_for_viewer(client, login, admin_user, organization, make_admin_user):
    super_admin_token = login(admin_user.email)
    event_id = _make_event(client, super_admin_token)

    viewer = make_admin_user(organization, roles=["viewer"])
    viewer_token = login(viewer.email)
    response = client.post(
        f"/api/v1/admin/events/{event_id}/banner",
        files={"file": ("banner.png", FAKE_PNG, "image/png")},
        headers=auth_headers(viewer_token),
    )
    assert response.status_code == 403


def test_upload_rejects_non_image_content(client, login, admin_user):
    token = login(admin_user.email)
    event_id = _make_event(client, token)

    response = client.post(
        f"/api/v1/admin/events/{event_id}/banner",
        files={"file": ("banner.png", NOT_AN_IMAGE, "image/png")},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_oversized_file(client, login, admin_user):
    token = login(admin_user.email)
    event_id = _make_event(client, token)

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 1)
    response = client.post(
        f"/api/v1/admin/events/{event_id}/banner",
        files={"file": ("banner.png", oversized, "image/png")},
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_organization_logo_upload_requires_super_admin(client, login, organization, make_admin_user):
    admin = make_admin_user(organization, roles=["admin"])
    token = login(admin.email)
    response = client.post(
        "/api/v1/admin/organization/logo",
        files={"file": ("logo.png", FAKE_PNG, "image/png")},
        headers=auth_headers(token),
    )
    assert response.status_code == 403


def test_organization_logo_upload_succeeds_for_super_admin(client, login, admin_user):
    token = login(admin_user.email)
    response = client.post(
        "/api/v1/admin/organization/logo",
        files={"file": ("logo.png", FAKE_PNG, "image/png")},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert "/api/v1/assets/org-assets/" in response.json()["data"]["logo_url"]


def test_public_asset_route_rejects_non_allowlisted_prefix(client):
    response = client.get("/api/v1/assets/receipts/some-org/some-receipt.pdf", follow_redirects=False)
    assert response.status_code == 404
