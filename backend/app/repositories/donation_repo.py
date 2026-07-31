import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.donation import SUCCESS, Donation
from app.models.donor import Donor
from app.models.event import Event
from app.models.payment import Payment
from app.models.receipt import Receipt


def create(
    db: Session,
    *,
    organization_id: uuid.UUID,
    donor_id: uuid.UUID,
    event_id: uuid.UUID | None,
    amount_in_paise: int,
    currency: str,
    purpose: str | None,
    donor_snapshot_json: dict,
) -> Donation:
    donation = Donation(
        organization_id=organization_id,
        donor_id=donor_id,
        event_id=event_id,
        amount_in_paise=amount_in_paise,
        currency=currency,
        purpose=purpose,
        donor_snapshot_json=donor_snapshot_json,
    )
    db.add(donation)
    db.flush()
    return donation


def get_by_id(db: Session, organization_id: uuid.UUID, donation_id: uuid.UUID) -> Donation | None:
    stmt = select(Donation).where(
        Donation.organization_id == organization_id,
        Donation.id == donation_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_id_for_update(db: Session, donation_id: uuid.UUID) -> Donation | None:
    """Locks the row for the webhook handler's read-modify-write — prevents a
    duplicate/near-simultaneous webhook delivery from racing on the same
    donation (belt-and-suspenders alongside webhook_events idempotency).

    Donation and Payment are locked with two separate SELECT ... FOR UPDATE
    statements rather than one joined query: Postgres rejects `FOR UPDATE` on
    a query with an outer join on the nullable side (Donation.payment is
    optional), which a joinedload(Donation.payment) would produce. The second
    select populates the session's identity map, so the lazy `donation.payment`
    access afterward returns that same locked row instead of issuing an
    unlocked query.
    """
    donation_stmt = select(Donation).where(Donation.id == donation_id).with_for_update()
    donation = db.execute(donation_stmt).scalar_one_or_none()
    if donation is None:
        return None

    payment_stmt = select(Payment).where(Payment.donation_id == donation_id).with_for_update()
    db.execute(payment_stmt).scalar_one_or_none()

    return donation


def create_payment(
    db: Session,
    *,
    organization_id: uuid.UUID,
    donation_id: uuid.UUID,
    razorpay_order_id: str,
    amount_in_paise: int,
) -> Payment:
    payment = Payment(
        organization_id=organization_id,
        donation_id=donation_id,
        razorpay_order_id=razorpay_order_id,
        amount_in_paise=amount_in_paise,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment_by_razorpay_order_id(db: Session, razorpay_order_id: str) -> Payment | None:
    stmt = select(Payment).where(Payment.razorpay_order_id == razorpay_order_id)
    return db.execute(stmt).scalar_one_or_none()


def get_full_detail(db: Session, organization_id: uuid.UUID, donation_id: uuid.UUID) -> Donation | None:
    stmt = (
        select(Donation)
        .where(Donation.organization_id == organization_id, Donation.id == donation_id)
        .options(
            joinedload(Donation.payment), joinedload(Donation.receipt), joinedload(Donation.event)
        )
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def list_paginated_admin(
    db: Session,
    organization_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    event_id: uuid.UUID | None = None,
    donor_id: uuid.UUID | None = None,
    status: str | None = None,
    min_amount_in_paise: int | None = None,
    max_amount_in_paise: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
) -> tuple[list[tuple[Donation, str | None, str | None]], int]:
    """Returns (items, total) where each item is (Donation, receipt_number,
    event_title). Donor name/mobile come from Donation.donor_snapshot_json
    (the frozen-at-donation-time values — see docs/03-database-schema.md),
    not a Donor join, so an editable donor profile never rewrites history.
    """
    base = (
        select(Donation, Receipt.receipt_number, Event.title)
        .join(Donor, Donor.id == Donation.donor_id)
        .outerjoin(Receipt, Receipt.donation_id == Donation.id)
        .outerjoin(Event, Event.id == Donation.event_id)
        .where(Donation.organization_id == organization_id)
    )

    if event_id is not None:
        base = base.where(Donation.event_id == event_id)
    if donor_id is not None:
        base = base.where(Donation.donor_id == donor_id)
    if status is not None:
        base = base.where(Donation.status == status)
    if min_amount_in_paise is not None:
        base = base.where(Donation.amount_in_paise >= min_amount_in_paise)
    if max_amount_in_paise is not None:
        base = base.where(Donation.amount_in_paise <= max_amount_in_paise)
    if date_from is not None:
        base = base.where(Donation.created_at >= date_from)
    if date_to is not None:
        base = base.where(Donation.created_at <= date_to)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Donor.full_name.ilike(like), Donor.mobile_number.ilike(like)))

    total = db.execute(select(func.count()).select_from(base.with_only_columns(Donation.id).subquery())).scalar_one()
    rows = db.execute(
        base.order_by(Donation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [(row[0], row[1], row[2]) for row in rows], total


def sum_amount_since(db: Session, organization_id: uuid.UUID, since: datetime) -> int:
    stmt = select(func.coalesce(func.sum(Donation.amount_in_paise), 0)).where(
        Donation.organization_id == organization_id,
        Donation.status == SUCCESS,
        Donation.created_at >= since,
    )
    return db.execute(stmt).scalar_one()


def sum_amount_and_count_all_time(db: Session, organization_id: uuid.UUID) -> tuple[int, int]:
    stmt = select(
        func.coalesce(func.sum(Donation.amount_in_paise), 0), func.count()
    ).where(Donation.organization_id == organization_id, Donation.status == SUCCESS)
    total, count = db.execute(stmt).one()
    return total, count
