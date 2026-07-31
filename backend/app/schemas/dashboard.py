from pydantic import BaseModel

from app.schemas.donation import AdminDonationListItem


class DashboardSummary(BaseModel):
    today_total_in_paise: int
    week_total_in_paise: int
    month_total_in_paise: int
    year_total_in_paise: int
    all_time_total_in_paise: int
    total_donation_count: int
    recent_donations: list[AdminDonationListItem]
