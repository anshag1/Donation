"""Upload validation for admin-supplied images (event banners, org
logo/signature). Never trusts the client's claimed Content-Type or filename —
both are attacker-controlled — so this checks magic bytes on the actual
content and generates the storage filename itself.
"""

from app.core.exceptions import ValidationAppError

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB


def validate_image_upload(content: bytes) -> tuple[str, str]:
    """Returns (content_type, file_extension). Raises ValidationAppError if
    the content isn't a recognized image format or exceeds the size limit."""
    if len(content) > MAX_IMAGE_BYTES:
        raise ValidationAppError(f"Image must be smaller than {MAX_IMAGE_BYTES // (1024 * 1024)}MB")
    if len(content) < 12:
        raise ValidationAppError("File is not a valid image")

    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", "webp"

    raise ValidationAppError("Only PNG, JPEG, or WEBP images are supported")
