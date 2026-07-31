from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.rbac import require_role
from app.deps import CurrentAdmin, DbDep
from app.models.role import ADMIN, COORDINATOR, SUPER_ADMIN, TREASURER, VIEWER
from app.repositories import donation_repo
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardSummary
from app.schemas.donation import AdminDonationListItem

router = APIRouter(prefix="/admin/dashboard", tags=["admin:dashboard"])

ALL_AUTHENTICATED_ROLES = (SUPER_ADMIN, ADMIN, TREASURER, COORDINATOR, VIEWER)


def _start_of_day(now: datetime) -> datetime:
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
def get_summary(
    db: Session = DbDep,
    current_admin: CurrentAdmin = Depends(require_role(*ALL_AUTHENTICATED_ROLES)),
) -> ApiResponse[DashboardSummary]:
    now = datetime.now(timezone.utc)
    today_start = _start_of_day(now)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    org_id = current_admin.organization_id
    all_time_total, all_time_count = donation_repo.sum_amount_and_count_all_time(db, org_id)

    recent_rows, _ = donation_repo.list_paginated_admin(db, org_id, page=1, page_size=10)
    recent_donations = [
        AdminDonationListItem(
            id=donation.id,
            donor_name=donation.donor_snapshot_json.get("full_name", ""),
            donor_mobile=donation.donor_snapshot_json.get("mobile_number", ""),
            event_title=event_title,
            amount_in_paise=donation.amount_in_paise,
            status=donation.status,
            purpose=donation.purpose,
            receipt_number=receipt_number,
            created_at=donation.created_at,
        )
        for donation, receipt_number, event_title in recent_rows
    ]

    return ApiResponse(
        data=DashboardSummary(
            today_total_in_paise=donation_repo.sum_amount_since(db, org_id, today_start),
            week_total_in_paise=donation_repo.sum_amount_since(db, org_id, week_start),
            month_total_in_paise=donation_repo.sum_amount_since(db, org_id, month_start),
            year_total_in_paise=donation_repo.sum_amount_since(db, org_id, year_start),
            all_time_total_in_paise=all_time_total,
            total_donation_count=all_time_count,
            recent_donations=recent_donations,
        )
    )
