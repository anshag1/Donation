from fastapi import APIRouter

from app.api.v1.admin.audit_logs import router as admin_audit_logs_router
from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.dashboard import router as admin_dashboard_router
from app.api.v1.admin.donations import router as admin_donations_router
from app.api.v1.admin.donors import router as admin_donors_router
from app.api.v1.admin.events import router as admin_events_router
from app.api.v1.admin.organization import router as admin_organization_router
from app.api.v1.admin.reports import router as admin_reports_router
from app.api.v1.admin.users import router as admin_users_router
from app.api.v1.public.assets import router as public_assets_router
from app.api.v1.public.donations import router as public_donations_router
from app.api.v1.public.events import router as public_events_router
from app.api.v1.public.receipts import router as public_receipts_router
from app.api.v1.webhooks.razorpay import router as razorpay_webhook_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(public_events_router)
api_router.include_router(public_donations_router)
api_router.include_router(public_receipts_router)
api_router.include_router(public_assets_router)
api_router.include_router(razorpay_webhook_router)

api_router.include_router(admin_auth_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(admin_events_router)
api_router.include_router(admin_donations_router)
api_router.include_router(admin_donors_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_audit_logs_router)
api_router.include_router(admin_organization_router)
api_router.include_router(admin_reports_router)
