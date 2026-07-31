import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin


class Receipt(Base, UUIDPKMixin):
    __tablename__ = "receipts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    donation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donations.id"), nullable=False, unique=True, index=True
    )
    receipt_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    financial_year: Mapped[str] = mapped_column(String(10), nullable=False)
    pdf_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    donation: Mapped["Donation"] = relationship(back_populates="receipt")  # noqa: F821


class ReceiptCounter(Base):
    """Backs gap-free sequential receipt numbering per org + financial year.

    Incremented via SELECT ... FOR UPDATE inside the same transaction that
    inserts the Receipt row (see app/services/receipt_service.py) — this row
    IS the lock, so concurrent donations never get the same receipt number.
    """

    __tablename__ = "receipt_counters"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "financial_year", name="ux_receipt_counters_org_fy"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    financial_year: Mapped[str] = mapped_column(String(10), nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
