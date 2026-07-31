import uuid
from datetime import datetime

from pydantic import BaseModel


class DonorListItem(BaseModel):
    id: uuid.UUID
    full_name: str
    mobile_number: str
    email: str | None
    total_donated_in_paise: int
    donation_count: int
    last_donation_at: datetime | None


class DonorDonationHistoryItem(BaseModel):
    id: uuid.UUID
    amount_in_paise: int
    status: str
    purpose: str | None
    event_title: str | None
    receipt_number: str | None
    created_at: datetime


class DonorDetail(BaseModel):
    id: uuid.UUID
    full_name: str
    mobile_number: str
    email: str | None
    address: str | None
    pan_number: str | None
    created_at: datetime
    donations: list[DonorDonationHistoryItem]
