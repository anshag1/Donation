"""Object storage abstraction. One interface, three backends, selected once
from config — not scattered `if configured` checks throughout the codebase.
LocalFilesystemStorage lets the whole receipt pipeline run without any cloud
account; R2Storage is this deployment's production backend (Cloudflare R2,
chosen for its zero-egress-fee pricing); SupabaseStorage remains as an
alternative for anyone who'd rather keep storage next to a Supabase-hosted
DB. See docs/05-architecture.md §5.2 and docs/06-deployment-security.md §6.1.
"""

from pathlib import Path
from typing import Protocol

import boto3
import httpx
from botocore.client import Config as BotoConfig

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

    def _auth_headers(self) -> dict[str, str]:
        """Supabase's Kong gateway requires BOTH headers: `apikey` identifies
        the project/key to the gateway itself, `Authorization` is the JWT
        checked for the actual permission (service_role bypasses RLS). Both
        carry the same service_role key here — this is the exact pair the
        official supabase-py client sends (its `_get_auth_headers()`), found
        by reading the client source since the REST docs don't spell out
        server-side header requirements. Sending `Authorization` alone (an
        earlier version of this file) gets rejected before it even reaches
        Storage.
        """
        return {"apikey": self._service_key, "Authorization": f"Bearer {self._service_key}"}

    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{key}"
        response = httpx.post(
            url,
            content=content,
            headers={
                **self._auth_headers(),
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
            headers=self._auth_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
        signed_path = response.json()["signedURL"]
        return f"{self._base_url}/storage/v1{signed_path}"

    def download(self, *, key: str) -> bytes:
        url = f"{self._base_url}/storage/v1/object/{self._bucket}/{key}"
        response = httpx.get(url, headers=self._auth_headers(), timeout=30.0)
        response.raise_for_status()
        return response.content


class R2Storage:
    """Cloudflare R2 — S3-compatible, so boto3's standard S3 client works
    against it unmodified with just a different endpoint_url/region. This is
    this deployment's chosen production backend (see docs/07-roadmap.md):
    zero egress fees, and avoids a cross-cloud hop since the frontend already
    sits on Cloudflare Pages.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.r2_storage_configured:
            raise RuntimeError(
                "R2Storage requires CLOUDFLARE_R2_ACCOUNT_ID, "
                "CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY, "
                "and CLOUDFLARE_R2_BUCKET"
            )
        self._bucket = settings.cloudflare_r2_bucket
        self._client = boto3.client(
            service_name="s3",
            endpoint_url=f"https://{settings.cloudflare_r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.cloudflare_r2_access_key_id,
            aws_secret_access_key=settings.cloudflare_r2_secret_access_key,
            region_name="auto",
            config=BotoConfig(signature_version="s3v4"),
        )

    def upload(self, *, key: str, content: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)
        return key

    def get_signed_url(self, *, key: str, expires_in_seconds: int = 900) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )

    def download(self, *, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()


def get_storage_backend(settings: Settings) -> StorageBackend:
    """R2 is this deployment's chosen production backend — checked first.
    Supabase Storage remains available as an alternative (e.g. for a
    different deployment that'd rather keep storage next to a
    Supabase-hosted DB); Local is the dev-without-any-cloud-account fallback.
    """
    if settings.r2_storage_configured:
        return R2Storage(settings)
    if settings.supabase_storage_configured:
        return SupabaseStorage(settings)
    return LocalFilesystemStorage()
