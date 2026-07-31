import uuid

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Donor(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "donors"
    __table_args__ = (
        Index(
            "ux_donors_org_mobile",
            "organization_id",
            "mobile_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
