# 9. Session Handoff — Full Context Recovery

**Purpose of this file**: a self-contained briefing so a fresh Claude session (or anyone else) can pick this project up with zero prior context. If you're reading this cold, read this file first, then skim `01-prd.md` and `05-architecture.md` for depth. This file is a snapshot as of **2026-07-31**; check git log / re-run tests before trusting anything time-sensitive below.

## 1. What this is

A production-quality Donation Management Platform for a charitable organization: donors pay via Razorpay, get an automated PDF receipt; admins manage events/donations/donors/users through a full dashboard, with 2FA, account lockout, real image upload, email-invite onboarding, and XLSX/PDF reporting. Built multi-tenant-*ready* (every core table has `organization_id`) but deployed single-tenant for v1.

- **Repo**: `c:\Users\agarw\OneDrive\Desktop\donation`, pushed to **https://github.com/anshag1/Donation.git**, branch `main`.
- **Stack**: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 (backend) · Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui (frontend) · PostgreSQL · native JWT auth (not Better Auth/Clerk — see §3).

## 2. Deployment plan (decided, not yet executed)

| Layer | Choice | Status |
|---|---|---|
| Frontend | Cloudflare Pages | Not yet connected/deployed; `frontend/Dockerfile` also exists (standalone Next.js output) as a local/fallback option, built + smoke-tested |
| Backend | Render | Not yet connected/deployed; `backend/Dockerfile` exists and builds/runs correctly (verified locally) |
| Database | Supabase Postgres | Account not yet created; use the **Session Pooler** connection string (port 5432, IPv4-compatible — NOT "Direct connection", which is IPv6-only unless paying for an add-on, and Render is IPv4) |
| Receipt PDF storage | **Cloudflare R2** (chosen over Supabase Storage — zero egress fees, avoids a cross-cloud hop since frontend is already on Cloudflare) | Code written (`R2Storage` in `storage_service.py`), **still never tested against a real R2 bucket** — verify before relying on it |
| Email | Resend | No account yet |
| Payments | Razorpay | No account yet — this is the one thing that actually blocks real donations |
| CI | GitHub Actions | ✅ `.github/workflows/ci.yml` exists and runs on every push/PR — but only *verifies* code (lint/typecheck/test), doesn't yet *deploy* anything |

None of Razorpay/Resend/Supabase/R2 credentials have been provided. Everything currently runs in **local-first mode**: Docker Postgres, local-filesystem receipt storage, email calls logged instead of sent, Razorpay order creation fails with a clear config error instead of crashing. This is intentional graceful degradation, not a bug.

## 3. Key architecture decisions (and why — don't redo this analysis)

- **Native FastAPI JWT, not Better Auth/Clerk** (the original brief's suggestion). Reason: backend `admin_users`+RBAC is the single source of truth; a second auth system would just be something else to keep in sync.
- **Admin route protection is client-side** (`AdminGuard`/`AuthProvider` in frontend), **not** Next.js `proxy.ts`. Reason: the refresh-token cookie is set by the backend's origin with `path=/api/v1/auth` — Next's server-side code only sees cookies sent to *its own* origin on the *current* path, so it structurally can't see this cookie for `/admin/*` requests. Fixing this properly needs a same-origin rewrite proxy + a second non-path-restricted cookie, or a BFF layer — not built. The backend's `require_role` RBAC checks are the real security boundary regardless of what the frontend renders.
- **Sync SQLAlchemy, not async** — simpler, DB routes are `def` not `async def` so FastAPI runs them in its threadpool.
- **Storage/email/task-dispatch are all adapter patterns**, selected once from config, not scattered `if configured` checks. Storage precedence: R2 > Supabase Storage > local filesystem. Task dispatch: RQ+Redis if `REDIS_URL` is set, else in-process `BackgroundTasks` (`app/worker/queue.py`, added this pass).
- **Seed/dev scripts live in `backend/scripts/`, NOT `backend/alembic/`** — a module named `alembic/seed.py` collides with the *installed* `alembic` package's own name and silently resolves wrong. Real bug hit and fixed in an earlier session.
- **Money is always integer paise** end-to-end in the backend; only formatted to ₹ (or "Rs." in PDFs — ReportLab's base font can't render ₹) at the display layer. `format_inr()`/`format_inr_for_pdf()` now both accept `Decimal` too (SQL `SUM()` aggregates come back as `Decimal`, not `int` — a real bug this pass hit, see §4).
- **2FA, account lockout, and per-identity rate limiting are separate mechanisms, not one feature**: 2FA is opt-in per-account; lockout triggers after 5 failed logins (password OR TOTP code) regardless of whether 2FA is on; per-identity limiting is keyed on donor mobile number and is independent of the existing per-IP `slowapi` limits. All three ship this pass.
- **The email-invite flow replaces direct password-setting**: `POST /admin/users` no longer accepts a `password` — it generates an unusable random one plus a hashed, single-use, 7-day invite token, and the new admin sets their own password via a public accept-invite page/endpoint.
- **mypy is wired into CI but is advisory, not a hard gate** (`mypy app || true`) — the codebase has ~50 pre-existing strict-mode violations (mostly SQLAlchemy relationship forward-refs and missing third-party type stubs) from before mypy was ever actually run. `ruff` **is** a hard gate and the codebase is fully clean against it. Don't be surprised the CI backend job "passes" even with mypy errors printed — that's the intended, documented behavior until that debt is paid down (see `docs/06-deployment-security.md` §6.3).

## 4. Real bugs found and fixed (verified knowledge — don't re-debug these)

### From earlier sessions
1. JWT `iat`/`exp` must be **numeric Unix timestamps**, not ISO datetime strings — PyJWT's own expiry check silently breaks otherwise. Fixed in `app/core/security.py`.
2. `razorpay.Utility.verify_webhook_signature(...)` **must be called on an instance** (`razorpay.Utility()`), not the class directly. Fixed in `app/services/webhook_service.py`.
3. Postgres **rejects `FOR UPDATE` combined with an outer join**. Fixed with two separate `SELECT ... FOR UPDATE` statements in `donation_repo.get_by_id_for_update`.
4. ReportLab's base Helvetica font **has no glyph for ₹** (renders a black box). Fixed via `format_inr_for_pdf()` ("Rs." prefix); web/email keep ₹ via `format_inr()`.
5. The refresh-token cookie's `Secure` flag broke `ENVIRONMENT=test` too. Fixed to `environment not in ("development", "test")`.
6. `slowapi`'s rate limiter uses process-wide in-memory state — fixed with an autouse `limiter.reset()` fixture in `conftest.py`.
7. Supabase Storage's REST API requires **both** an `apikey` header **and** `Authorization: Bearer`. Fixed in `storage_service.py`.
8. Frontend `globals.css` had a circular `--font-sans: var(--font-sans)`. Fixed to point at `--font-geist-sans`.
9. `AmountPicker.tsx`: a preset chip stayed visually "selected" after focusing the custom-amount input. Fixed via `isCustomFocused` state.

### From this pass (Milestone 7 — hardening & feature completion)
10. `format_inr()`/`format_inr_for_pdf()` crashed with `ValueError: invalid format string` the moment the new report-aggregation SQL queries (`donation_repo.aggregate_totals_for_event/month`, `aggregate_monthly_breakdown_for_year`) fed them a `Decimal` instead of `int` — psycopg returns `Decimal` for SQL `SUM()` results. Fixed by normalizing via `int()` inside both formatters (`app/services/format_utils.py`). Caught by actually generating a report, not just by a passing unit test.
11. The new summary-report PDF endpoint (`GET /admin/reports/summary.pdf`) initially called `format_inr()` (real ₹ glyph) instead of `format_inr_for_pdf()` ("Rs." prefix) — reproducing the exact bug #4 above, in new code, because the new report code didn't know to reuse the existing fix. Caught **visually**: downloaded the actual PDF via a live Playwright browser session and saw the ₹ render as a black box. Fixed; regression-tested by monkeypatching the renderer to inspect the `SummaryPdfData` actually passed, since ReportLab's output stream is compressed and grepping response bytes for "Rs." isn't reliable.
12. `serve_local_file` (the local-dev-only route that serves whatever `LocalFilesystemStorage` has under a key) **hardcoded `media_type="application/pdf"`** — fine when it only ever served receipts, but once event-banner/org-logo uploads started reusing it (via the new public `/assets/{key}` redirect), uploaded PNGs got served with the wrong Content-Type. Under this app's own `X-Content-Type-Options: nosniff` security header, that made browsers **refuse to render the image at all**. Caught by actually uploading an image via Playwright, then checking the resulting `<img>` element's `naturalWidth` was `0` (failed to load) even though the upload API call itself succeeded. Fixed by deriving the media type from the file extension (`mimetypes.guess_type`) instead of hardcoding it; regression-tested (`test_upload_event_banner_stores_file_and_is_publicly_fetchable` now also asserts the served Content-Type).
13. **Security-review finding** (not a functional bug, a real vulnerability caught by an independent adversarial review pass, not by testing): `send_admin_invite_email`'s local-dev fallback (used whenever `RESEND_API_KEY` is unset) logged the raw invite URL at INFO level — which embeds a single-use bearer token sufficient on its own to take over the newly-created account (including a fresh `super_admin`) via `POST /auth/accept-invite`. Application logs are readable by a wider audience than the API response (which only reaches the requesting super_admin). Fixed by dropping the token from the log line entirely; regression-tested (`test_invite_token_is_never_logged`, uses pytest's `caplog`).
14. A stale `uvicorn` process from a previous, abruptly-interrupted session was still bound to port 8000 during this pass's live-browser verification, serving 404s for every newly-added route even though the current code was correct and all tests passed. Not a code bug, but cost real debugging time — see `docs/08-local-development.md` §8.7 for the fix (check for more than one PID on the port, kill the older one).

## 5. What's fully built, tested, and verified (Roadmap Milestones 0–5, 7)

- **Backend**: full schema, donation flow (Razorpay order → signature-verified idempotent webhook → receipt), full admin API (dashboard/events+banner-upload/donations/donors/users+invite/audit-logs/organization+logo-upload/reports-CSV+XLSX+PDF), native JWT auth with 2FA + account lockout + refresh rotation+revocation, per-identity + per-IP rate limiting, audit logging wired into real mutation paths, RBAC on every admin route, an optional durable RQ+Redis task queue.
- **Frontend**: public donation flow (general + event-specific + standalone event page, Razorpay Checkout, status polling) + full admin dashboard (two-step 2FA login, KPIs, all CRUD pages incl. image upload, invite-based user creation, reports with XLSX/PDF downloads, 2FA enrollment page), custom-themed shadcn/ui (indigo/amber, light+dark), client-side auth.
- **Tests**: 121 backend tests (`cd backend && source .venv/Scripts/activate && python -m pytest -q`) — unit, integration, and a dedicated `test_admin_endpoints_security.py` sweep proving every admin endpoint (including all the new ones) rejects bad auth/wrong roles and cross-org isolation holds.
- **Lint**: `ruff check app tests scripts` is fully clean and is a hard CI gate. `mypy app` runs in CI but is advisory only (pre-existing debt, see §3).
- **Frontend checks**: `npm run lint`, `npm run typecheck` (now a real package.json script), `npm run build` all clean.
- **CI**: `.github/workflows/ci.yml` — backend job (Postgres service container, ruff, mypy-advisory, `alembic upgrade head`, full pytest) + frontend job (lint, typecheck, build) — verified to pass by manually reproducing the exact same sequence locally against a freshly-created database.
- **Manually verified end-to-end in a real headless browser this pass** (Playwright, via scratch scripts — not committed to the repo): 2FA enrollment → forced two-step login → disable; event-banner upload → publicly re-fetched with the correct image Content-Type → rendered successfully on the real public donation page; org logo upload; XLSX export + summary PDF download (content inspected directly — the PDF bug in §4 was caught this way); new-admin invite creation → accept-invite → login; the new standalone `/events/[eventSlug]` page.

## 6. What's NOT built (don't assume these exist)

- No standalone `GET /admin/reports/donor/{id}.pdf` — CSV/XLSX cover per-donor history via the existing `donor_id` filter.
- No CAPTCHA/Turnstile on the public donation form (deliberately deferred to minimize donor friction).
- No dependency vulnerability scanning in CI (`pip-audit`/`npm audit`/Dependabot) — flagged, not silently skipped.
- **`R2Storage` has never been exercised against a real R2 bucket** — code follows Cloudflare's official boto3 example exactly, but verify with `simulate_webhook.py` the moment real R2 credentials are added (same pattern used to verify Supabase originally).
- No production deployment anywhere (Milestone 6) — nothing is connected/live. CI verifies the code; it doesn't deploy it yet.
- No `DELETE /admin/users/{id}` as a distinct endpoint — use `PATCH .../{id}` with `is_active: false`.
- No self-serve multi-org onboarding, volunteer portal, donation campaigns, or other post-v1 roadmap items — see `docs/07-roadmap.md` §7.1.

## 7. Local dev environment specifics

- Docker Postgres on **port 5435** (not 5432 — avoids clashing with other local projects on this machine), databases `donation_dev` + `donation_test`. `docker compose up -d` from repo root.
- Optional Redis for the durable task queue on **port 6380** (not the default 6379, same reasoning), behind the `durable-queue` compose profile: `docker compose --profile durable-queue up -d`. Not needed unless you're specifically testing that path — see `docs/08-local-development.md` §8.4b.
- Backend venv: `backend/.venv` (Windows Git Bash: `source .venv/Scripts/activate`, not `bin/activate`). `pip install -r requirements-dev.txt` (not just `requirements.txt`) to also get `ruff`/`mypy`/`types-openpyxl`.
- Seeded demo data (`python -m scripts.seed`): org slug `demo-org`, admin `admin@example.org` / `ChangeMe123!` (⚠️ do not reuse in production — this password is now public in this doc), event slug `annual-function-2026`.
- Docker Desktop on this machine sometimes isn't running; start via `powershell -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'"` then poll `docker info` until it responds.
- **Watch for stale backend processes** if a session was interrupted and restarted — see §4 item 14 and `docs/08-local-development.md` §8.7. Check `Get-NetTCPConnection -LocalPort 8000` for more than one PID before assuming new code isn't taking effect.
- Full instructions: `docs/08-local-development.md`.

## 8. Git state

As of this handoff, the Milestone 7 hardening pass is complete, tested, security-reviewed, and documented, but **not yet committed** — working tree has substantial modifications + new files (see `git status`). Two prior commits are already pushed to `origin/main`:
- `d8c03f9` — "Initial commit: donation management platform" (187 files)
- `5232c7f` — "Add Cloudflare R2 storage backend; document deployment plan and session handoff"

`.env` files are correctly gitignored throughout; only `.env.example` (placeholder values) is tracked.

## 9. Docs map

`README.md` → `docs/01-prd.md` (requirements/user stories) → `02-user-flows.md` (sequence diagrams) → `03-database-schema.md` (ER diagram) → `04-api-specification.md` (every endpoint, ✅/○ status) → `05-architecture.md` (folder structure, ✅/○ status, coding standards) → `06-deployment-security.md` (security posture, ✅/○ status) → `07-roadmap.md` (milestones + future items) → `08-local-development.md` (how to run it) → this file. All kept in sync with actual implementation status throughout — trust the ✅/○ markers over prose elsewhere if they ever conflict.
