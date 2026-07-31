import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPKMixin

PENDING = "pending"
SUCCESS = "success"
FAILED = "failed"
REFUNDED = "refunded"


class Donation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "donations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    donor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donors.id"), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=True, index=True
    )
    amount_in_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PENDING, index=True)

    # Freezes donor identity fields as entered for THIS donation — donor records
    # may be edited later, but a historical receipt must reflect what was true
    # at donation time. See docs/03-database-schema.md §3.4 (donations).
    donor_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    payment: Mapped["Payment | None"] = relationship(back_populates="donation", uselist=False)
    receipt: Mapped["Receipt | None"] = relationship(back_populates="donation", uselist=False)
    event: Mapped["Event | None"] = relationship(viewonly=True)
