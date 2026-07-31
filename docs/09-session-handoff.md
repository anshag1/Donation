# 9. Session Handoff — Full Context Recovery

**Purpose of this file**: a self-contained briefing so a fresh Claude session (or anyone else) can pick this project up with zero prior context. If you're reading this cold, read this file first, then skim `01-prd.md` and `05-architecture.md` for depth. This file is a snapshot as of **2026-07-31**; check git log / re-run tests before trusting anything time-sensitive below.

## 1. What this is

A production-quality Donation Management Platform for a charitable organization: donors pay via Razorpay, get an automated PDF receipt; admins manage events/donations/donors/users through a full dashboard. Built multi-tenant-*ready* (every core table has `organization_id`) but deployed single-tenant for v1.

- **Repo**: `c:\Users\agarw\OneDrive\Desktop\donation`, pushed to **https://github.com/anshag1/Donation.git**, branch `main`.
- **Stack**: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 (backend) · Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui (frontend) · PostgreSQL · native JWT auth (not Better Auth/Clerk — see §3).

## 2. Deployment plan (decided, not yet executed)

| Layer | Choice | Status |
|---|---|---|
| Frontend | Cloudflare Pages | Not yet connected/deployed |
| Backend | Render | Not yet connected/deployed; `backend/Dockerfile` exists and builds/runs correctly (verified locally) |
| Database | Supabase Postgres | Account not yet created; use the **Session Pooler** connection string (port 5432, IPv4-compatible — NOT "Direct connection", which is IPv6-only unless paying for an add-on, and Render is IPv4) |
| Receipt PDF storage | **Cloudflare R2** (chosen over Supabase Storage — zero egress fees, avoids a cross-cloud hop since frontend is already on Cloudflare) | Code just written (`R2Storage` in `storage_service.py`), **never tested against a real R2 bucket** — verify before relying on it |
| Email | Resend | No account yet |
| Payments | Razorpay | No account yet — this is the one thing that actually blocks real donations |

None of Razorpay/Resend/Supabase/R2 credentials have been provided. Everything currently runs in **local-first mode**: Docker Postgres, local-filesystem receipt storage, email calls logged instead of sent, Razorpay order creation fails with a clear config error instead of crashing. This is intentional graceful degradation, not a bug.

## 3. Key architecture decisions (and why — don't redo this analysis)

- **Native FastAPI JWT, not Better Auth/Clerk** (the original brief's suggestion). Reason: backend `admin_users`+RBAC is the single source of truth; a second auth system would just be something else to keep in sync.
- **Admin route protection is client-side** (`AdminGuard`/`AuthProvider` in frontend), **not** Next.js `proxy.ts`. Reason: the refresh-token cookie is set by the backend's origin with `path=/api/v1/auth` — Next's server-side code only sees cookies sent to *its own* origin on the *current* path, so it structurally can't see this cookie for `/admin/*` requests. Fixing this properly needs a same-origin rewrite proxy + a second non-path-restricted cookie, or a BFF layer — not built. The backend's `require_role` RBAC checks are the real security boundary regardless of what the frontend renders.
- **Sync SQLAlchemy, not async** — simpler, DB routes are `def` not `async def` so FastAPI runs them in its threadpool.
- **Storage/email are adapter patterns**, selected once in `get_storage_backend()`/`email_service.py`, not scattered `if configured` checks. Precedence: R2 > Supabase Storage > local filesystem.
- **Seed/dev scripts live in `backend/scripts/`, NOT `backend/alembic/`** — a module named `alembic/seed.py` collides with the *installed* `alembic` package's own name and silently resolves wrong. Real bug hit and fixed this session.
- **CSV export only**, no XLSX/PDF summary reports — deliberate scope cut, not an oversight.
- **Event banners / org logo are plain URL string fields**, not real file upload — same reasoning.
- **Money is always integer paise** end-to-end in the backend; only formatted to ₹ (or "Rs." in PDFs — see §4) at the display layer.

## 4. Real bugs found and fixed this session (verified knowledge — don't re-debug these)

1. JWT `iat`/`exp` must be **numeric Unix timestamps**, not ISO datetime strings — PyJWT's own expiry check silently breaks otherwise. Fixed in `app/core/security.py`.
2. `razorpay.Utility.verify_webhook_signature(...)` **must be called on an instance** (`razorpay.Utility()`), not the class directly — calling it unbound silently misassigns arguments. Fixed in `app/services/webhook_service.py`.
3. Postgres **rejects `FOR UPDATE` combined with an outer join**. The donation+payment row-locking query (`donation_repo.get_by_id_for_update`) originally used `joinedload(Donation.payment).with_for_update()` — broken. Fixed with two separate `SELECT ... FOR UPDATE` statements.
4. ReportLab's base Helvetica font **has no glyph for ₹** (renders a black box). Fixed by adding `format_inr_for_pdf()` (uses "Rs." prefix) used only in PDF rendering; web/email keep the real ₹ symbol via `format_inr()`.
5. The refresh-token cookie's `Secure` flag was `environment != "development"` — this broke it in `ENVIRONMENT=test` too (httpx TestClient uses plain `http://`, and browsers/clients silently drop `Secure` cookies over non-HTTPS). Fixed to `environment not in ("development", "test")`.
6. `slowapi`'s rate limiter uses **process-wide in-memory state** — without a reset, pytest tests accumulate rate-limit hits across unrelated test functions and spuriously 429. Fixed with an autouse `limiter.reset()` fixture in `conftest.py`.
7. Supabase Storage's REST API requires **both** an `apikey` header **and** `Authorization: Bearer` — sending `Authorization` alone (original `SupabaseStorage` code) gets rejected by Supabase's gateway before it even reaches Storage. Found by reading the official `supabase-py` client source (`_get_auth_headers()`), not the docs (which don't spell this out for server-side use). Fixed in `storage_service.py`.
8. Frontend `globals.css` had `--font-sans: var(--font-sans)` — **circular**, resolved to nothing, silently fell back to browser-default serif font on every page. Fixed to point at `--font-geist-sans` (the actual loaded font variable).
9. `AmountPicker.tsx`: a preset amount chip stayed visually "selected" even after the donor focused the custom-amount input (only cleared once they typed a digit) — confusing UX the user caught by screenshot. Fixed to deselect on focus via an `isCustomFocused` state.

## 5. What's fully built, tested, and verified (Roadmap Milestones 0–5)

- **Backend**: full schema (12 tables incl. `revoked_refresh_tokens`), donation flow (Razorpay order → signature-verified idempotent webhook → receipt), full admin API (dashboard/events/donations/donors/users/audit-logs/organization/reports-CSV), native JWT auth with refresh rotation+revocation, audit logging wired into real mutation paths, RBAC on every admin route.
- **Frontend**: public donation flow (general + event-specific, Razorpay Checkout, status polling) + full admin dashboard (login, KPIs, all CRUD pages), custom-themed shadcn/ui (indigo/amber, light+dark), client-side auth.
- **Tests**: 75 backend tests (`cd backend && source .venv/Scripts/activate && python -m pytest -q`) — unit, integration, and a dedicated `test_admin_endpoints_security.py` sweep proving every admin endpoint rejects bad auth/wrong roles and cross-org isolation holds.
- **Frontend checks**: `npm run lint`, `npx tsc --noEmit`, `npm run build` all clean.
- **Manually verified end-to-end in a real headless browser** (Playwright, via scratch scripts — not committed to the repo): full admin flow login→dashboard→events→donations→donors→users→audit-logs→settings→reports→logout, and the full public donation→webhook→receipt pipeline via `backend/scripts/simulate_webhook.py`.

## 6. What's NOT built (don't assume these exist)

- Receipt download (`GET /receipts/{number}/download`) has no signed-token/mobile-verification — reachable by receipt number alone (documented gap).
- No XLSX/PDF report formats (CSV only), no 2FA (column exists, no TOTP flow), no real image upload (banner/logo are URL strings), no email-invite flow for new admins (temp password set directly), no per-identity rate limiting or login lockout (flat per-IP only), no durable task queue (in-process `BackgroundTasks`).
- **No CI** (`.github/workflows/` doesn't exist). **No frontend Dockerfile.**
- **`R2Storage` has never been exercised against a real R2 bucket** — code follows Cloudflare's official boto3 example exactly, but verify with `simulate_webhook.py` the moment real R2 credentials are added (same pattern used to verify Supabase originally).
- Standalone public `/events/[eventSlug]` page not built (donation form shows the same info inline).

## 7. Local dev environment specifics

- Docker Postgres on **port 5435** (not 5432 — avoids clashing with other local projects on this machine), databases `donation_dev` + `donation_test`. `docker compose up -d` from repo root.
- Backend venv: `backend/.venv` (Windows Git Bash: `source .venv/Scripts/activate`, not `bin/activate`).
- Seeded demo data (`python -m scripts.seed`): org slug `demo-org`, admin `admin@example.org` / `ChangeMe123!` (⚠️ do not reuse in production — this password is now public in this doc), event slug `annual-function-2026`.
- Docker Desktop on this machine sometimes isn't running; start via `powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'"` then poll `docker info` until it responds.
- Full instructions: `docs/08-local-development.md`.

## 8. Git state

One commit pushed (`d8c03f9`, "Initial commit: donation management platform", 187 files) to `origin/main`. Since then, uncommitted local changes: the R2 storage backend (`config.py`, `storage_service.py`, `requirements.txt`, `.env.example`) — **not yet committed or pushed** as of this handoff. `.env` files are correctly gitignored throughout; only `.env.example` (placeholder values) is tracked.

## 9. Docs map

`README.md` → `docs/01-prd.md` (requirements/user stories) → `02-user-flows.md` (sequence diagrams) → `03-database-schema.md` (ER diagram) → `04-api-specification.md` (every endpoint, ✅/○ status) → `05-architecture.md` (folder structure, ✅/○ status, coding standards) → `06-deployment-security.md` (security posture, ✅/○ status) → `07-roadmap.md` (milestones + future items) → `08-local-development.md` (how to run it) → this file. All kept in sync with actual implementation status throughout — trust the ✅/○ markers over prose elsewhere if they ever conflict.
