"""Local/dev seed data: one organization, one super_admin, one demo event —
enough for the donation page and admin login to have something real to work
against without needing the (deferred) admin CRUD UI. Safe to re-run
(idempotent — checks before inserting).

Usage (from backend/, with the venv active): python -m scripts.seed

Deliberately NOT placed under alembic/ — a module there would collide with
the installed `alembic` package's own name (`python -m alembic.seed` resolves
"alembic" to the real library first, not this directory) and silently fail
or import the wrong thing.
"""

import datetime

from sqlalchemy import select

from app.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.admin_user import AdminUser
from app.models.admin_user_role import AdminUserRole
from app.models.event import ACTIVE, Event
from app.models.organization import Organization
from app.models.role import ALL_ROLES, Role

DEMO_ORG_SLUG = "demo-org"
DEMO_ADMIN_EMAIL = "admin@example.org"
DEMO_ADMIN_PASSWORD = "ChangeMe123!"  # local dev only — never used in production
DEMO_EVENT_SLUG = "annual-function-2026"


def run() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        for role_name in ALL_ROLES:
            existing = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
            if existing is None:
                db.add(Role(name=role_name))
        db.flush()

        organization = db.execute(
            select(Organization).where(Organization.slug == DEMO_ORG_SLUG)
        ).scalar_one_or_none()
        if organization is None:
            organization = Organization(
                name="Demo Charitable Trust",
                slug=DEMO_ORG_SLUG,
                contact_email="contact@example.org",
                receipt_prefix=settings.default_org_receipt_prefix,
            )
            db.add(organization)
            db.flush()
            print(f"Created organization: {organization.name} ({organization.id})")
        else:
            print(f"Organization already exists: {organization.name} ({organization.id})")

        admin_user = db.execute(
            select(AdminUser).where(AdminUser.email == DEMO_ADMIN_EMAIL)
        ).scalar_one_or_none()
        if admin_user is None:
            admin_user = AdminUser(
                organization_id=organization.id,
                email=DEMO_ADMIN_EMAIL,
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                full_name="Demo Super Admin",
            )
            db.add(admin_user)
            db.flush()

            super_admin_role = db.execute(
                select(Role).where(Role.name == "super_admin")
            ).scalar_one()
            db.add(AdminUserRole(admin_user_id=admin_user.id, role_id=super_admin_role.id))
            db.flush()
            print(f"Created admin user: {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
        else:
            print(f"Admin user already exists: {DEMO_ADMIN_EMAIL}")

        event = db.execute(
            select(Event).where(
                Event.organization_id == organization.id, Event.slug == DEMO_EVENT_SLUG
            )
        ).scalar_one_or_none()
        if event is None:
            event = Event(
                organization_id=organization.id,
                title="Annual Function 2026",
                slug=DEMO_EVENT_SLUG,
                description=(
                    "Our annual community gathering celebrating another year of service — "
                    "proceeds fund scholarships, medical camps, and disaster relief work."
                ),
                status=ACTIVE,
                start_date=datetime.date(2026, 12, 1),
                end_date=datetime.date(2026, 12, 31),
            )
            db.add(event)
            db.flush()
            print(f"Created event: {event.title} (/donate/{event.slug})")
        else:
            print(f"Event already exists: {event.title} (/donate/{event.slug})")

        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
