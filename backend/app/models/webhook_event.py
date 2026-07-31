import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class WebhookEvent(Base, UUIDPKMixin):
    """Every inbound webhook is persisted before processing, keyed by the
    provider's event_id, so a redelivered event is a no-op. This table is the
    idempotency backbone for webhook processing — see docs/02-user-flows.md §2.5.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="ux_webhook_events_provider_event_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="razorpay")
    event_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
