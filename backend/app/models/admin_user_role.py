import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin


class AdminUserRole(Base, UUIDPKMixin):
    __tablename__ = "admin_user_roles"
    __table_args__ = (UniqueConstraint("admin_user_id", "role_id", name="ux_admin_user_role"),)

    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    admin_user: Mapped["AdminUser"] = relationship(back_populates="role_links")  # noqa: F821
    role: Mapped["Role"] = relationship()  # noqa: F821
