"""Test configuration. Points at the `donation_test` database (created by
infra/init-test-db.sql alongside donation_dev) and sets fixed test secrets —
env vars must be set BEFORE any `app.*` module is imported, since
app.config.get_settings() is process-wide cached (lru_cache).
"""

import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://donation:donation@localhost:5435/donation_test"
os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-production"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_webhook_secret"
os.environ["ENVIRONMENT"] = "test"
# Deliberately leave RAZORPAY_KEY_ID/SECRET and RESEND_API_KEY unset in most
# tests (matches local-first reality); tests that need order creation
# monkeypatch app.services.payment_service.create_razorpay_order directly
# instead of hitting the real Razorpay API.

import uuid  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.identity_rate_limit import donation_identity_limiter  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.admin_user import AdminUser  # noqa: E402
from app.models.admin_user_role import AdminUserRole  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.donor import Donor  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.repositories import donation_repo  # noqa: E402

settings = get_settings()
engine = create_engine(settings.database_url, future=True)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncates all tables between tests so each test starts from a blank
    slate without paying the cost of recreating the schema every time."""
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi's in-memory storage is a process-wide singleton keyed by
    remote address — httpx TestClient always reports the same fake address
    ("testclient"), so without a reset, rate-limit counters accumulate
    ACROSS tests and cause unrelated later tests to spuriously 429."""
    limiter.reset()
    donation_identity_limiter.reset()
    yield


@pytest.fixture
def client(db):
    def _get_db_override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def organization(db) -> Organization:
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}", receipt_prefix="TEST")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


ADMIN_TEST_PASSWORD = "Sup3rSecret!"


def _get_or_create_role(db, name: str) -> Role:
    role = db.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()
    return role


@pytest.fixture
def make_admin_user(db):
    """Factory: make_admin_user(organization, roles=["super_admin"]) -> AdminUser,
    password always ADMIN_TEST_PASSWORD. Use this (not the `admin_user` fixture)
    whenever a test needs a NON-super_admin role to check RBAC denial paths.
    """

    def _make(organization, roles: list[str] | None = None) -> AdminUser:
        roles = roles or ["super_admin"]
        user = AdminUser(
            organization_id=organization.id,
            email=f"admin-{uuid.uuid4().hex[:8]}@example.org",
            password_hash=hash_password(ADMIN_TEST_PASSWORD),
            full_name="Test Admin",
        )
        db.add(user)
        db.flush()
        for role_name in roles:
            db.add(AdminUserRole(admin_user_id=user.id, role_id=_get_or_create_role(db, role_name).id))
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def admin_user(make_admin_user, organization) -> AdminUser:
    """A super_admin user for `organization`, password `ADMIN_TEST_PASSWORD`."""
    return make_admin_user(organization, roles=["super_admin"])


@pytest.fixture
def other_organization(db) -> Organization:
    """A second, unrelated organization — for asserting cross-org isolation."""
    org = Organization(name="Other Org", slug=f"other-org-{uuid.uuid4().hex[:8]}", receipt_prefix="OTHER")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def login(client):
    """login(email, password) -> access_token, via the real HTTP endpoint
    (not a JWT crafted in-process) — so these tests exercise exactly what a
    real client does."""

    def _login(email: str, password: str = ADMIN_TEST_PASSWORD) -> str:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return response.json()["data"]["access_token"]

    return _login


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def donation_with_payment(db, organization):
    """A pending donation + its Razorpay order, ready for a webhook to land on."""
    donor = Donor(
        organization_id=organization.id,
        full_name="Jane Donor",
        mobile_number="9876500000",
    )
    db.add(donor)
    db.flush()

    donation = donation_repo.create(
        db,
        organization_id=organization.id,
        donor_id=donor.id,
        event_id=None,
        amount_in_paise=50000,
        currency="INR",
        purpose="Test purpose",
        donor_snapshot_json={
            "full_name": "Jane Donor",
            "mobile_number": "9876500000",
            "email": "jane@example.com",
        },
    )
    payment = donation_repo.create_payment(
        db,
        organization_id=organization.id,
        donation_id=donation.id,
        razorpay_order_id=f"order_{uuid.uuid4().hex[:14]}",
        amount_in_paise=50000,
    )
    db.commit()
    db.refresh(donation)
    db.refresh(payment)
    return donation, payment
