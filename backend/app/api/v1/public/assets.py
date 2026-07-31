from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.services.storage_service import get_storage_backend

router = APIRouter(prefix="/assets", tags=["public:assets"])

# The only two prefixes ever served publicly — deliberately NOT "receipts/",
# which holds PII and is gated by a signed token (see public/receipts.py).
# A generic "redirect to whatever key you ask for" route over the same
# storage bucket would otherwise let this endpoint bypass that gate entirely.
PUBLIC_ASSET_PREFIXES = ("event-banners/", "org-assets/")


@router.get("/{key:path}")
def serve_public_asset(key: str) -> RedirectResponse:
    """Event banners and org logo/signature are public-facing marketing
    assets (no PII), so unlike receipts this needs no per-request token —
    just a key-prefix allowlist so this route can never be used to fetch
    anything outside those two folders."""
    if not key.startswith(PUBLIC_ASSET_PREFIXES):
        raise NotFoundError("Asset not found")

    settings = get_settings()
    url = get_storage_backend(settings).get_signed_url(key=key, expires_in_seconds=3600)
    return RedirectResponse(url)
