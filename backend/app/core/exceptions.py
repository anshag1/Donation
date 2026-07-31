"""App-level exceptions mapped to HTTP responses in a single place (main.py's
exception handlers) — route/service code raises these instead of HTTPException
directly, so error shaping stays consistent everywhere.
"""

from fastapi import status


class AppError(Exception):
    """Base class. `code` matches docs/04-api-specification.md §4.4."""

    code: str = "INTERNAL_ERROR"
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code
        super().__init__(self.message)


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    http_status = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    http_status = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = status.HTTP_403_FORBIDDEN


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = status.HTTP_409_CONFLICT


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS


class PaymentOrderFailedError(AppError):
    code = "PAYMENT_ORDER_FAILED"
    http_status = status.HTTP_502_BAD_GATEWAY


class WebhookSignatureInvalidError(AppError):
    code = "WEBHOOK_SIGNATURE_INVALID"
    http_status = status.HTTP_400_BAD_REQUEST
