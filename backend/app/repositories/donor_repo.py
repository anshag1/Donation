import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.donation import SUCCESS, Donation
from app.models.donor import Donor
from app.models.event import Event
from app.models.receipt import Receipt
from app.schemas.donation import DonorInput


def get_or_create(db: Session, organization_id: uuid.UUID, donor_input: DonorInput) -> Donor:
    """Dedupe by (organization_id, mobile_number) per docs/03-database-schema.md
    §3.4. Contact details are refreshed on repeat donations so the donor's
    directory entry reflects their latest info; the DONATION keeps its own
    frozen snapshot regardless (see Donation.donor_snapshot_json)."""
    stmt = select(Donor).where(
        Donor.organization_id == organization_id,
        Donor.mobile_number == donor_input.mobile_number,
        Donor.deleted_at.is_(None),
    )
    donor = db.execute(stmt).scalar_one_or_none()

    if donor is None:
        donor = Donor(
            organization_id=organization_id,
            full_name=donor_input.full_name,
            mobile_number=donor_input.mobile_number,
            email=donor_input.email,
            address=donor_input.address,
            pan_number=donor_input.pan_number,
        )
        db.add(donor)
        db.flush()
    else:
        donor.full_name = donor_input.full_name
        donor.email = donor_input.email or donor.email
        donor.address = donor_input.address or donor.address
        donor.pan_number = donor_input.pan_number or donor.pan_number

    return donor


def get_by_id(db: Session, organization_id: uuid.UUID, donor_id: uuid.UUID) -> Donor | None:
    stmt = select(Donor).where(
        Donor.organization_id == organization_id,
        Donor.id == donor_id,
        Donor.deleted_at.is_(None),
    )
    return db.execute(stmt).scalar_one_or_none()


def list_paginated(
    db: Session, organization_id: uuid.UUID, *, page: int, page_size: int, q: str | None = None
) -> tuple[list[tuple[Donor, int, int, object]], int]:
    """Returns (items, total) where each item is
    (Donor, total_donated_in_paise, donation_count, last_donation_at) —
    aggregated over that donor's SUCCESSFUL donations only."""
    successful = (
        select(
            Donation.donor_id,
            func.coalesce(func.sum(Donation.amount_in_paise), 0).label("total"),
            func.count(Donation.id).label("count"),
            func.max(Donation.created_at).label("last_at"),
        )
        .where(Donation.organization_id == organization_id, Donation.status == SUCCESS)
        .group_by(Donation.donor_id)
        .subquery()
    )

    base = (
        select(
            Donor,
            func.coalesce(successful.c.total, 0),
            func.coalesce(successful.c.count, 0),
            successful.c.last_at,
        )
        .outerjoin(successful, successful.c.donor_id == Donor.id)
        .where(Donor.organization_id == organization_id, Donor.deleted_at.is_(None))
    )
    if q:
        like = f"%{q}%"
        base = base.where(or_(Donor.full_name.ilike(like), Donor.mobile_number.ilike(like), Donor.email.ilike(like)))

    total = db.execute(select(func.count()).select_from(base.with_only_columns(Donor.id).subquery())).scalar_one()
    rows = db.execute(
        base.order_by(Donor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [(row[0], row[1], row[2], row[3]) for row in rows], total


def list_donations_for_donor(db: Session, donor_id: uuid.UUID) -> list[tuple[Donation, str | None, str | None]]:
    stmt = (
        select(Donation, Receipt.receipt_number, Event.title)
        .outerjoin(Receipt, Receipt.donation_id == Donation.id)
        .outerjoin(Event, Event.id == Donation.event_id)
        .where(Donation.donor_id == donor_id)
        .order_by(Donation.created_at.desc())
    )
    return [(row[0], row[1], row[2]) for row in db.execute(stmt).all()]
