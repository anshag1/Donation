import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.rate_limit import limiter

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="Donation Management Platform API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Every AppError subclass maps to a stable {code, message} envelope per
    docs/04-api-specification.md §4.4 — no stack traces or internal detail
    ever reach the client."""
    return JSONResponse(
        status_code=exc.http_status,
        content={"data": None, "error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Reshapes FastAPI/Pydantic's default {detail: [...]} into the same
    {data, error} envelope every other error uses."""
    first_error = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first_error.get("loc", []) if p != "body")
    message = f"{field}: {first_error.get('msg')}" if field else first_error.get("msg", "Invalid request")
    return JSONResponse(
        status_code=400,
        content={"data": None, "error": {"code": "VALIDATION_ERROR", "message": message}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("app.error").exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
        },
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


app.include_router(api_router)
