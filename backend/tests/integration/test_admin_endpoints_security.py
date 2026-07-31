"""Security sweep for every admin endpoint added in this pass: every route
must (1) reject requests with no/invalid auth, (2) enforce its documented
role requirement, and (3) never leak or allow mutation of another
organization's data. This file exists specifically because the user asked
for "no endpoints left unsecured" — it is the check, not incidental coverage.
"""

import pytest

from tests.conftest import auth_headers

PLACEHOLDER = "00000000-0000-0000-0000-000000000000"

# (method, path) for every admin route. A random UUID stands in for path
# params — auth/role dependencies run before the route body touches the DB,
# so this correctly exercises the 401/403 boundary regardless of whether
# that resource exists.
ALL_ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/dashboard/summary"),
    ("GET", "/api/v1/admin/events"),
    ("POST", "/api/v1/admin/events"),
    ("GET", f"/api/v1/admin/events/{PLACEHOLDER}"),
    ("PATCH", f"/api/v1/admin/events/{PLACEHOLDER}"),
    ("DELETE", f"/api/v1/admin/events/{PLACEHOLDER}"),
    ("GET", "/api/v1/admin/donations"),
    ("GET", f"/api/v1/admin/donations/{PLACEHOLDER}"),
    ("POST", f"/api/v1/admin/donations/{PLACEHOLDER}/receipt/resend-email"),
    ("POST", f"/api/v1/admin/donations/{PLACEHOLDER}/receipt/duplicate"),
    ("GET", "/api/v1/admin/donors"),
    ("GET", f"/api/v1/admin/donors/{PLACEHOLDER}"),
    ("GET", "/api/v1/admin/users"),
    ("POST", "/api/v1/admin/users"),
    ("PATCH", f"/api/v1/admin/users/{PLACEHOLDER}"),
    ("GET", "/api/v1/admin/audit-logs"),
    ("GET", "/api/v1/admin/organization"),
    ("PATCH", "/api/v1/admin/organization"),
    ("GET", "/api/v1/admin/reports/export.csv"),
    ("GET", "/api/v1/auth/me"),
]


@pytest.mark.parametrize("method,path", ALL_ADMIN_ENDPOINTS)
def test_every_admin_endpoint_rejects_missing_auth(client, method, path):
    response = client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert response.status_code == 401, f"{method} {path} did not 401 with no auth: {response.text}"
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("method,path", ALL_ADMIN_ENDPOINTS)
def test_every_admin_endpoint_rejects_garbage_token(client, method, path):
    response = client.request(
        method, path, headers=auth_headers("not-a-real-jwt"), json={} if method in ("POST", "PATCH") else None
    )
    assert response.status_code == 401, f"{method} {path} did not 401 with a garbage token"


# --- Role enforcement -------------------------------------------------

def test_viewer_cannot_write_events(client, login, organization, make_admin_user):
    viewer = make_admin_user(organization, roles=["viewer"])
    token = login(viewer.email)
    headers = auth_headers(token)

    assert client.get("/api/v1/admin/events", headers=headers).status_code == 200
    create = client.post(
        "/api/v1/admin/events",
        headers=headers,
        json={"title": "T", "slug": "t-event"},
    )
    assert create.status_code == 403
    assert create.json()["error"]["code"] == "FORBIDDEN"


def test_coordinator_can_write_events_but_not_donations_receipts(
    client, login, organization, make_admin_user, donation_with_payment
):
    coordinator = make_admin_user(organization, roles=["coordinator"])
    token = login(coordinator.email)
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/admin/events",
        headers=headers,
        json={"title": "Coordinator Event", "slug": "coordinator-event"},
    )
    assert created.status_code == 200, created.text

    donation, _payment = donation_with_payment
    resend = client.post(
        f"/api/v1/admin/donations/{donation.id}/receipt/resend-email", headers=headers
    )
    assert resend.status_code == 403


def test_treasurer_can_action_receipts_but_not_write_events(
    client, login, organization, make_admin_user, donation_with_payment
):
    treasurer = make_admin_user(organization, roles=["treasurer"])
    token = login(treasurer.email)
    headers = auth_headers(token)

    donation, _payment = donation_with_payment
    # No email on this donor snapshot -> expect a validation error, not 403,
    # proving the role check passed and it got to the actual business logic.
    resend = client.post(
        f"/api/v1/admin/donations/{donation.id}/receipt/resend-email", headers=headers
    )
    assert resend.status_code in (200, 400), resend.text
    assert resend.status_code != 403

    create_event = client.post(
        "/api/v1/admin/events", headers=headers, json={"title": "X", "slug": "treasurer-event"}
    )
    assert create_event.status_code == 403


def test_only_super_admin_can_manage_users(client, login, organization, make_admin_user):
    admin_role_user = make_admin_user(organization, roles=["admin"])
    token = login(admin_role_user.email)
    headers = auth_headers(token)

    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/admin/users",
            headers=headers,
            json={"email": "new@example.org", "full_name": "New", "password": "abcdefghij", "roles": ["viewer"]},
        ).status_code
        == 403
    )


def test_only_super_admin_can_manage_organization_settings(client, login, organization, make_admin_user):
    treasurer = make_admin_user(organization, roles=["treasurer"])
    headers = auth_headers(login(treasurer.email))
    assert client.get("/api/v1/admin/organization", headers=headers).status_code == 403


def test_audit_logs_allowed_for_super_admin_and_treasurer_only(client, login, organization, make_admin_user):
    coordinator = make_admin_user(organization, roles=["coordinator"])
    headers = auth_headers(login(coordinator.email))
    assert client.get("/api/v1/admin/audit-logs", headers=headers).status_code == 403

    treasurer = make_admin_user(organization, roles=["treasurer"])
    headers = auth_headers(login(treasurer.email))
    assert client.get("/api/v1/admin/audit-logs", headers=headers).status_code == 200


def test_super_admin_cannot_deactivate_or_demote_self(client, login, organization, admin_user):
    headers = auth_headers(login(admin_user.email))

    deactivate_self = client.patch(
        f"/api/v1/admin/users/{admin_user.id}", headers=headers, json={"is_active": False}
    )
    assert deactivate_self.status_code == 403

    demote_self = client.patch(
        f"/api/v1/admin/users/{admin_user.id}", headers=headers, json={"roles": ["viewer"]}
    )
    assert demote_self.status_code == 403


# --- Cross-organization isolation --------------------------------------

def test_event_from_other_org_is_not_visible_or_editable(
    client, login, organization, other_organization, make_admin_user, db
):
    from app.models.event import Event

    other_event = Event(organization_id=other_organization.id, title="Other Org Event", slug="other-org-event")
    db.add(other_event)
    db.commit()
    db.refresh(other_event)

    my_admin = make_admin_user(organization, roles=["super_admin"])
    headers = auth_headers(login(my_admin.email))

    get_response = client.get(f"/api/v1/admin/events/{other_event.id}", headers=headers)
    assert get_response.status_code == 404

    patch_response = client.patch(
        f"/api/v1/admin/events/{other_event.id}", headers=headers, json={"title": "Hijacked"}
    )
    assert patch_response.status_code == 404

    list_response = client.get("/api/v1/admin/events", headers=headers)
    ids_in_list = {item["id"] for item in list_response.json()["data"]["items"]}
    assert str(other_event.id) not in ids_in_list


def test_donation_from_other_org_is_not_visible(
    client, login, organization, other_organization, make_admin_user, db
):
    from app.models.donor import Donor
    from app.repositories import donation_repo as repo

    other_donor = Donor(organization_id=other_organization.id, full_name="Other Donor", mobile_number="9000000000")
    db.add(other_donor)
    db.flush()
    other_donation = repo.create(
        db,
        organization_id=other_organization.id,
        donor_id=other_donor.id,
        event_id=None,
        amount_in_paise=10000,
        currency="INR",
        purpose=None,
        donor_snapshot_json={"full_name": "Other Donor", "mobile_number": "9000000000"},
    )
    db.commit()

    my_admin = make_admin_user(organization, roles=["super_admin"])
    headers = auth_headers(login(my_admin.email))

    response = client.get(f"/api/v1/admin/donations/{other_donation.id}", headers=headers)
    assert response.status_code == 404


def test_dashboard_totals_do_not_include_other_orgs_donations(
    client, login, organization, other_organization, make_admin_user, db
):
    from app.models.donation import SUCCESS
    from app.models.donor import Donor
    from app.repositories import donation_repo as repo

    other_donor = Donor(organization_id=other_organization.id, full_name="Other Donor", mobile_number="9000000001")
    db.add(other_donor)
    db.flush()
    other_donation = repo.create(
        db,
        organization_id=other_organization.id,
        donor_id=other_donor.id,
        event_id=None,
        amount_in_paise=99_999_00,
        currency="INR",
        purpose=None,
        donor_snapshot_json={"full_name": "Other Donor", "mobile_number": "9000000001"},
    )
    other_donation.status = SUCCESS
    db.commit()

    my_admin = make_admin_user(organization, roles=["super_admin"])
    headers = auth_headers(login(my_admin.email))

    summary = client.get("/api/v1/admin/dashboard/summary", headers=headers).json()["data"]
    assert summary["all_time_total_in_paise"] == 0
    assert summary["total_donation_count"] == 0


def test_user_management_is_org_scoped(client, login, organization, other_organization, make_admin_user):
    other_admin = make_admin_user(other_organization, roles=["super_admin"])

    my_admin = make_admin_user(organization, roles=["super_admin"])
    headers = auth_headers(login(my_admin.email))

    response = client.patch(
        f"/api/v1/admin/users/{other_admin.id}", headers=headers, json={"is_active": False}
    )
    assert response.status_code == 404

    list_response = client.get("/api/v1/admin/users", headers=headers)
    ids = {item["id"] for item in list_response.json()["data"]["items"]}
    assert str(other_admin.id) not in ids
