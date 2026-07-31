import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MOBILE_RE = re.compile(r"^\+?[0-9]{10,13}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

MIN_AMOUNT_IN_PAISE = 100  # ₹1
MAX_AMOUNT_IN_PAISE = 10_000_000_00  # ₹1 crore — sanity ceiling, not a business rule


class DonorInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    mobile_number: str
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    pan_number: str | None = None

    @field_validator("mobile_number")
    @classmethod
    def _validate_mobile(cls, v: str) -> str:
        cleaned = v.replace(" ", "").replace("-", "")
        if not MOBILE_RE.match(cleaned):
            raise ValueError("Enter a valid mobile number (10-13 digits, optional leading +)")
        return cleaned

    @field_validator("pan_number")
    @classmethod
    def _validate_pan(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.upper().strip()
        if not PAN_RE.match(v):
            raise ValueError("Enter a valid PAN number (e.g. ABCDE1234F)")
        return v


class DonationInitiateRequest(BaseModel):
    event_id: uuid.UUID | None = None
    donor: DonorInput
    amount_in_paise: int = Field(ge=MIN_AMOUNT_IN_PAISE, le=MAX_AMOUNT_IN_PAISE)
    purpose: str | None = Field(default=None, max_length=255)


class DonationInitiateResponse(BaseModel):
    donation_id: uuid.UUID
    razorpay_order_id: str
    razorpay_key_id: str
    amount_in_paise: int
    currency: str = "INR"


class DonationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    receipt_number: str | None = None
    receipt_download_url: str | None = None


class DonationClientCallback(BaseModel):
    """Informational only — see docs/02-user-flows.md §2.1. Never flips
    donation status; recorded for reconciliation telemetry only."""

    razorpay_order_id: str
    razorpay_payment_id: str | None = None
    client_status: str


class AdminDonationListItem(BaseModel):
    id: uuid.UUID
    donor_name: str
    donor_mobile: str
    event_title: str | None
    amount_in_paise: int
    status: str
    purpose: str | None
    receipt_number: str | None
    created_at: datetime


class AdminPaymentOut(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str | None
    status: str
    method: str | None
    failure_reason: str | None
    captured_at: datetime | None


class AdminReceiptOut(BaseModel):
    receipt_number: str
    duplicate_count: int
    emailed_at: datetime | None
    download_url: str


class AdminDonationDetail(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    donor_id: uuid.UUID
    donor_snapshot: dict
    event_id: uuid.UUID | None
    event_title: str | None
    amount_in_paise: int
    currency: str
    purpose: str | None
    status: str
    created_at: datetime
    payment: AdminPaymentOut | None
    receipt: AdminReceiptOut | None
