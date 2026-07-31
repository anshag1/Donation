import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.receipt import Receipt, ReceiptCounter


def allocate_next_receipt_number(
    db: Session, *, organization_id: uuid.UUID, receipt_prefix: str, financial_year: str
) -> str:
    """Gap-free sequential numbering per org + financial year, safe under
    concurrency. INSERT ... ON CONFLICT DO NOTHING guarantees the counter row
    exists without a check-then-insert race, then SELECT ... FOR UPDATE locks
    it for the rest of the caller's transaction — two concurrent donations
    can never be assigned the same number. See docs/03-database-schema.md §3.4.
    """
    pg_insert_stmt = (
        pg_insert(ReceiptCounter)
        .values(organization_id=organization_id, financial_year=financial_year, last_value=0)
        .on_conflict_do_nothing(constraint="ux_receipt_counters_org_fy")
    )
    db.execute(pg_insert_stmt)

    stmt = (
        select(ReceiptCounter)
        .where(
            ReceiptCounter.organization_id == organization_id,
            ReceiptCounter.financial_year == financial_year,
        )
        .with_for_update()
    )
    counter = db.execute(stmt).scalar_one()

    counter.last_value += 1
    db.flush()

    return f"{receipt_prefix}/{financial_year}/{counter.last_value:06d}"


def create(
    db: Session,
    *,
    organization_id: uuid.UUID,
    donation_id: uuid.UUID,
    receipt_number: str,
    financial_year: str,
    pdf_storage_key: str,
) -> Receipt:
    receipt = Receipt(
        organization_id=organization_id,
        donation_id=donation_id,
        receipt_number=receipt_number,
        financial_year=financial_year,
        pdf_storage_key=pdf_storage_key,
    )
    db.add(receipt)
    db.flush()
    return receipt


def get_by_donation_id(db: Session, donation_id: uuid.UUID) -> Receipt | None:
    stmt = select(Receipt).where(Receipt.donation_id == donation_id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_receipt_number(db: Session, receipt_number: str) -> Receipt | None:
    stmt = select(Receipt).where(Receipt.receipt_number == receipt_number)
    return db.execute(stmt).scalar_one_or_none()


def mark_emailed(db: Session, receipt: Receipt) -> None:
    from sqlalchemy import func

    receipt.emailed_at = func.now()
    db.flush()
