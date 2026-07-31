import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

CREATED = "created"
AUTHORIZED = "authorized"
CAPTURED = "captured"
FAILED = "failed"
REFUNDED = "refunded"


class Payment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    donation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donations.id"), nullable=False, unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="razorpay")
    razorpay_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CREATED, index=True)
    amount_in_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    donation: Mapped["Donation"] = relationship(back_populates="payment")
