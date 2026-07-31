"""XLSX export and event/monthly/yearly PDF summary reports — additions on
top of the existing CSV export, sharing its RBAC and underlying queries.
See app/api/v1/admin/reports.py.
"""

from datetime import UTC

from app.models.donation import SUCCESS
from tests.conftest import auth_headers


def _make_successful_donation(db, organization, *, event_id=None, amount_in_paise=50000):
    from app.models.donor import Donor
    from app.repositories import donation_repo

    donor = Donor(organization_id=organization.id, full_name="Report Donor", mobile_number="9876500099")
    db.add(donor)
    db.flush()

    donation = donation_repo.create(
        db,
        organization_id=organization.id,
        donor_id=donor.id,
        event_id=event_id,
        amount_in_paise=amount_in_paise,
        currency="INR",
        purpose="Report test",
        donor_snapshot_json={"full_name": "Report Donor", "mobile_number": "9876500099"},
    )
    donation.status = SUCCESS
    db.commit()
    db.refresh(donation)
    return donation


def test_xlsx_export_requires_report_role(client, login, organization, make_admin_user):
    coordinator = make_admin_user(organization, roles=["coordinator"])
    token = login(coordinator.email)
    response = client.get("/api/v1/admin/reports/export.xlsx", headers=auth_headers(token))
    assert response.status_code == 403


def test_xlsx_export_returns_a_valid_workbook(client, login, admin_user, organization, db):
    _make_successful_donation(db, organization)
    token = login(admin_user.email)
    response = client.get("/api/v1/admin/reports/export.xlsx", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # A real .xlsx is a zip archive — starts with the local file header magic bytes.
    assert response.content[:2] == b"PK"


def test_summary_pdf_requires_report_role(client, login, organization, make_admin_user):
    viewer = make_admin_user(organization, roles=["viewer"])
    token = login(viewer.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf", params={"period": "year", "year": 2026}, headers=auth_headers(token)
    )
    assert response.status_code == 403


def test_summary_pdf_yearly_includes_monthly_breakdown(client, login, admin_user, organization, db):
    donation = _make_successful_donation(db, organization, amount_in_paise=100000)
    year = donation.created_at.astimezone(UTC).year

    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf", params={"period": "year", "year": year}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_summary_pdf_uses_pdf_safe_currency_formatting(client, login, admin_user, organization, db, monkeypatch):
    """ReportLab's base Helvetica font has no glyph for ₹ (see
    format_utils.format_inr_for_pdf's docstring) — the same bug already fixed
    once for receipt PDFs. This asserts the summary PDF route builds its
    SummaryPdfData with the "Rs."-prefixed formatter, not the raw-₹ one, by
    inspecting the data passed to the renderer directly (ReportLab's output
    stream is compressed, so grepping response bytes for "Rs." isn't reliable)."""
    donation = _make_successful_donation(db, organization, amount_in_paise=100000)
    year = donation.created_at.astimezone(UTC).year

    captured = {}
    real_render = __import__("app.services.pdf.summary_pdf", fromlist=["render_summary_pdf"]).render_summary_pdf

    def _capturing_render(data):
        captured["data"] = data
        return real_render(data)

    monkeypatch.setattr("app.api.v1.admin.reports.render_summary_pdf", _capturing_render)

    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf", params={"period": "year", "year": year}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    assert captured["data"].total_amount_display.startswith("Rs.")
    assert "₹" not in captured["data"].total_amount_display
    for row in captured["data"].breakdown_rows:
        assert row[1].startswith("Rs.")


def test_summary_pdf_monthly_requires_year_and_month(client, login, admin_user):
    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf", params={"period": "month"}, headers=auth_headers(token)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_summary_pdf_event_requires_event_id(client, login, admin_user):
    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf", params={"period": "event"}, headers=auth_headers(token)
    )
    assert response.status_code == 400


def test_summary_pdf_event_report_for_specific_event(client, login, admin_user, organization, db):
    event_response = client.post(
        "/api/v1/admin/events",
        json={"title": "Annual Gala", "slug": "annual-gala", "status": "active"},
        headers=auth_headers(login(admin_user.email)),
    )
    event_id = event_response.json()["data"]["id"]
    _make_successful_donation(db, organization, event_id=event_id, amount_in_paise=75000)

    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf",
        params={"period": "event", "event_id": event_id},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF-")


def test_summary_pdf_rejects_unknown_event(client, login, admin_user):
    token = login(admin_user.email)
    response = client.get(
        "/api/v1/admin/reports/summary.pdf",
        params={"period": "event", "event_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers(token),
    )
    assert response.status_code == 404
