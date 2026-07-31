import threading

from app.repositories import receipt_repo
from tests.conftest import TestSessionLocal


def test_allocate_next_receipt_number_is_sequential(db, organization):
    n1 = receipt_repo.allocate_next_receipt_number(
        db, organization_id=organization.id, receipt_prefix="TEST", financial_year="2026-27"
    )
    n2 = receipt_repo.allocate_next_receipt_number(
        db, organization_id=organization.id, receipt_prefix="TEST", financial_year="2026-27"
    )
    db.commit()

    assert n1 == "TEST/2026-27/000001"
    assert n2 == "TEST/2026-27/000002"


def test_allocate_next_receipt_number_is_independent_per_financial_year(db, organization):
    this_year = receipt_repo.allocate_next_receipt_number(
        db, organization_id=organization.id, receipt_prefix="TEST", financial_year="2026-27"
    )
    next_year = receipt_repo.allocate_next_receipt_number(
        db, organization_id=organization.id, receipt_prefix="TEST", financial_year="2027-28"
    )
    db.commit()

    assert this_year == "TEST/2026-27/000001"
    assert next_year == "TEST/2027-28/000001"


def test_allocate_next_receipt_number_is_safe_under_concurrency(organization):
    """Fires N concurrent allocations, each on its own DB session/transaction
    (mirroring N simultaneous donations), and asserts every number handed out
    is unique with no gaps — proving the SELECT ... FOR UPDATE lock in
    receipt_repo.allocate_next_receipt_number actually serializes correctly
    rather than racing.
    """
    organization_id = organization.id
    results: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def _allocate_in_own_session() -> None:
        session = TestSessionLocal()
        try:
            number = receipt_repo.allocate_next_receipt_number(
                session,
                organization_id=organization_id,
                receipt_prefix="TEST",
                financial_year="2026-27",
            )
            session.commit()
            with lock:
                results.append(number)
        except Exception as exc:  # pragma: no cover - failure path surfaced via assertion below
            with lock:
                errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=_allocate_in_own_session) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent allocation raised: {errors}"
    assert len(results) == 10
    assert len(set(results)) == 10, f"duplicate receipt numbers allocated: {results}"

    sequence_numbers = sorted(int(r.split("/")[-1]) for r in results)
    assert sequence_numbers == list(range(1, 11))
