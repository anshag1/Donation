"""Object storage abstraction. One interface, two backends, selected once from
config — not scattered `if configured` checks throughout the codebase. Local
filesystem storage lets the whole receipt pipeline run without a Supabase
account; SupabaseStorage is the production backend. See
docs/05-architecture.md §5.2 and docs/06-deployment-security.md §6.1.
"""

from pathlib import Path
from typing import Protocol

import httpx

from app.config import Settings

LOCAL_STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "var"


class StorageBackend(Protocol):
    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        """Stores `content` under `key`. Returns a value suitable for later
        `get_signed_url` lookup (an opaque storage key, not necessarily a URL)."""
        ...

    def get_signed_url(self, *, key: str, expires_in_seconds: int = 900) -> str:
        """Returns a URL the caller can use to fetch the object directly."""
        ...

    def download(self, *, key: str) -> bytes:
        """Returns the raw bytes stored at `key` — used server-side (e.g. to
        attach a receipt PDF to an outgoing email) where a redirect/URL isn't
        useful. Kept on the same interface so callers never branch on which
        backend is active."""
        ...


class LocalFilesystemStorage:
    def __init__(self, root: Path = LOCAL_STORAGE_ROOT) -> None:
        self._root = root

    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def get_signed_url(self, *, key: str, expires_in_seconds: int = 900) -> str:
        # Served by the backend itself in local dev — see
        # app/api/v1/public/receipts.py, which streams straight from disk.
        return f"/api/v1/receipts/local-file/{key}"

    def download(self, *, key: str) -> bytes:
        return (self._root / key).read_bytes()


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_storage_configured:
            raise RuntimeError("SupabaseStorage requires SUPABASE_URL, "
                                "SUPABASE_SERVICE_ROLE_KEY, and SUPABASE_STORAGE_BUCKET")
        self._base_url = settings.supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_role_key
        self._bucket = settings.supabase_storage_bucket

    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{key}"
        response = httpx.post(
            url,
            content=content,
            headers={
                "Authorization": f"Bearer {self._service_key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return key

    def get_signed_url(self, *, key: str, expires_in_seconds: int = 900) -> str:
        url = f"{self._base_url}/storage/v1/object/sign/{self._bucket}/{key}"
        response = httpx.post(
            url,
            json={"expiresIn": expires_in_seconds},
            headers={"Authorization": f"Bearer {self._service_key}"},
            timeout=15.0,
        )
        response.raise_for_status()
        signed_path = response.json()["signedURL"]
        return f"{self._base_url}/storage/v1{signed_path}"

    def download(self, *, key: str) -> bytes:
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{key}"
        response = httpx.get(
            url, headers={"Authorization": f"Bearer {self._service_key}"}, timeout=30.0
        )
        response.raise_for_status()
        return response.content


def get_storage_backend(settings: Settings) -> StorageBackend:
    if settings.supabase_storage_configured:
        return SupabaseStorage(settings)
    return LocalFilesystemStorage()
