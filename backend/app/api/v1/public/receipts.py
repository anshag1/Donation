from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.deps import DbDep
from app.repositories import receipt_repo
from app.services.storage_service import LOCAL_STORAGE_ROOT, get_storage_backend

router = APIRouter(prefix="/receipts", tags=["public:receipts"])


@router.get("/{receipt_number:path}/download")
def download_receipt(receipt_number: str, db: Session = DbDep) -> RedirectResponse:
    """Redirects to a short-lived signed URL for the receipt PDF. Not gated by
    admin auth (donors need it right after paying), but receipt numbers are
    sequential/low-entropy — production hardening (a signed token query param
    or donor mobile-number confirmation) is tracked in docs/04-api-specification.md
    §4.1 and left for the admin-dashboard follow-up pass, which is where
    donor-facing receipt re-delivery (resend/duplicate) actually gets built."""
    receipt = receipt_repo.get_by_receipt_number(db, receipt_number)
    if receipt is None:
        raise NotFoundError("Receipt not found")

    settings = get_settings()
    url = get_storage_backend(settings).get_signed_url(key=receipt.pdf_storage_key)
    return RedirectResponse(url)


@router.get("/local-file/{key:path}")
def serve_local_file(key: str) -> FileResponse:
    """Local-dev-only route: serves receipts written by LocalFilesystemStorage.
    Never reached in production (SupabaseStorage is used instead, and its
    signed URLs point at Supabase directly, not at this backend)."""
    resolved = (LOCAL_STORAGE_ROOT / key).resolve()
    if LOCAL_STORAGE_ROOT.resolve() not in resolved.parents:
        raise NotFoundError("Receipt file not found")
    if not resolved.is_file():
        raise NotFoundError("Receipt file not found")
    return FileResponse(resolved, media_type="application/pdf", filename=Path(key).name)
