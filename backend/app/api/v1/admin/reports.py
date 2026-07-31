import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import ADMIN, SUPER_ADMIN, TREASURER
from app.repositories import donation_repo
from app.services.format_utils import format_inr

router = APIRouter(prefix="/admin/reports", tags=["admin:reports"])

REPORT_ROLES = (SUPER_ADMIN, ADMIN, TREASURER)

# A single CSV export is capped at this many rows — well beyond any single
# charitable org's realistic donation volume for v1. If usage ever
# approaches this, paginated/streaming export is the right next step rather
# than silently raising the cap further.
MAX_EXPORT_ROWS = 20_000


@router.get("/export.csv")
def export_donations_csv(
    event_id: uuid.UUID | None = None,
    donor_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*REPORT_ROLES)),
) -> StreamingResponse:
    rows, total = donation_repo.list_paginated_admin(
        db,
        current_admin.organization_id,
        page=1,
        page_size=MAX_EXPORT_ROWS,
        event_id=event_id,
        donor_id=donor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Date",
            "Donor Name",
            "Mobile Number",
            "Event",
            "Amount (INR)",
            "Status",
            "Purpose",
            "Receipt Number",
            "Donation ID",
        ]
    )
    for donation, receipt_number, event_title in rows:
        writer.writerow(
            [
                donation.created_at.isoformat(),
                donation.donor_snapshot_json.get("full_name", ""),
                donation.donor_snapshot_json.get("mobile_number", ""),
                event_title or "",
                format_inr(donation.amount_in_paise),
                donation.status,
                donation.purpose or "",
                receipt_number or "",
                str(donation.id),
            ]
        )
    if total > MAX_EXPORT_ROWS:
        writer.writerow([])
        writer.writerow(
            [f"NOTE: {total} donations matched these filters; only the first {MAX_EXPORT_ROWS} are included."]
        )

    buffer.seek(0)
    filename = f"donations-export-{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
