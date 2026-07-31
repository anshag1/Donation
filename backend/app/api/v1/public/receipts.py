import mimetypes
from pathlib import Path

import jwt
from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_receipt_download_token
from app.deps import DbDep
from app.repositories import receipt_repo
from app.services.storage_service import LOCAL_STORAGE_ROOT, get_storage_backend

router = APIRouter(prefix="/receipts", tags=["public:receipts"])


@router.get("/{receipt_number:path}/download")
def download_receipt(receipt_number: str, token: str | None = None, db: Session = DbDep) -> RedirectResponse:
    """Redirects to a short-lived signed URL for the receipt PDF. Not gated by
    admin auth (donors need it right after paying), so instead requires a
    `token` query param minted by `create_receipt_download_token` — receipt
    numbers alone are sequential/low-entropy (e.g. `ORG/2026-27/000123`) and
    would let anyone enumerate every receipt in the org otherwise. The token
    is scoped to one specific receipt id and expires, so it can't be replayed
    against a different receipt or used indefinitely."""
    if not token:
        raise UnauthorizedError("Missing download token")
    try:
        token_receipt_id = decode_receipt_download_token(token)
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired download link") from exc

    receipt = receipt_repo.get_by_receipt_number(db, receipt_number)
    if receipt is None or receipt.id != token_receipt_id:
        # Same error as an invalid token — never confirm/deny a receipt
        # number's existence to an unauthenticated caller.
        raise UnauthorizedError("Invalid or expired download link")

    settings = get_settings()
    url = get_storage_backend(settings).get_signed_url(key=receipt.pdf_storage_key)
    return RedirectResponse(url)


@router.get("/local-file/{key:path}")
def serve_local_file(key: str) -> FileResponse:
    """Local-dev-only route: serves whatever LocalFilesystemStorage has under
    `key` — receipt PDFs, but also (via public/assets.py's redirect) event
    banners and org logo/signature images now that uploads exist. Never
    reached in production (R2/Supabase are used instead, and their signed
    URLs point directly at those providers, not at this backend).

    Content-Type is derived from the file extension, not hardcoded to
    "application/pdf" — a real bug this pass hit: the browser's
    X-Content-Type-Options: nosniff header (see main.py) makes browsers
    refuse to render an <img> whose server-declared type is application/pdf,
    even though the bytes are a valid PNG."""
    resolved = (LOCAL_STORAGE_ROOT / key).resolve()
    if LOCAL_STORAGE_ROOT.resolve() not in resolved.parents:
        raise NotFoundError("Receipt file not found")
    if not resolved.is_file():
        raise NotFoundError("Receipt file not found")
    media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=media_type, filename=Path(key).name)
