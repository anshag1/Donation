from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin

# Seeded via alembic/seed.py — keep in sync with docs/01-prd.md §1.9.
SUPER_ADMIN = "super_admin"
ADMIN = "admin"
TREASURER = "treasurer"
COORDINATOR = "coordinator"
VIEWER = "viewer"

ALL_ROLES = [SUPER_ADMIN, ADMIN, TREASURER, COORDINATOR, VIEWER]


class Role(Base, UUIDPKMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
