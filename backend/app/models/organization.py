from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Organization(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="ORG")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Per-org Razorpay/Resend credentials are supported by schema for the future
    # multi-tenant rollout; v1 (single org) reads these from backend env vars
    # instead, so these columns are nullable and unused for now.
    razorpay_key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    razorpay_key_secret_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resend_api_key_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
