# 7. Future Roadmap & Development Milestones

## 7.1 Future Roadmap (Post-v1)

| Capability | Description | Why it's deferred |
|---|---|---|
| **Self-serve multi-org onboarding** | Org signup flow, per-org Razorpay key configuration UI, subdomain/custom-domain provisioning | v1 has one org, manually provisioned; building self-serve now is speculative |
| **Organization branding/theming** | Per-org color scheme, custom email templates, custom receipt layout | Schema already supports it (`organizations.logo_url`, etc.); UI deferred until 2nd org exists |
| **Custom receipt templates** | Let orgs design their own receipt layout (drag-and-drop or template picker) | Needs real usage data on what orgs actually want first |
| **Multiple payment gateways** | Stripe/PayU/Cashfree alongside Razorpay, gateway selection per org | `payments.provider` column already anticipates this |
| **Volunteer portal** | Separate login for volunteers to log offline/cash donations on behalf of the org | Distinct persona/permission model, sizable scope |
| **Donation campaigns** | Goal-based campaigns with progress bars, recurring/subscription donations | Requires a recurring billing model (Razorpay Subscriptions) |
| **Analytics dashboard** | Donor retention, cohort analysis, channel attribution | Needs sufficient data volume to be meaningful |
| **Public donation pages per org** | `{org-slug}.platform.tld` or custom domain donation pages | Depends on multi-org onboarding |
| **API integrations** | Public API keys for orgs to pull their own data into other tools (e.g. accounting software) | Needs API key management + scoped tokens |
| **QR code verification** | Printable receipt QR that links to a verification page | Small add-on once receipt storage/URLs are stable |
| **Digital signature** | Cryptographically signed PDF receipts (not just an image of a signature) | Compliance-driven; add when an org requests it |
| **Duplicate receipt self-service** | Let donors regenerate their own receipt via mobile/OTP verification, without contacting admin | Requires donor-facing auth (currently admin-only action) |
| **Donor self-service login** | Donor accounts to view full history without needing the receipt number | Currently receipts are accessed via signed link; full accounts are a bigger auth surface |

All the items previously listed here (durable task queue, signed receipt-download tokens, image upload, email-invite, 2FA, XLSX/PDF reports) were built in the hardening pass — see Milestone 7 below.

## 7.2 Development Milestones

### Milestone 0 — Foundations ✅ DONE
- Repo scaffolding (monorepo structure per [05-architecture.md](05-architecture.md)); CI pipeline added in Milestone 7 (`.github/workflows/ci.yml`).
- Database schema + Alembic migration for all entities, applied and verified against a real local Postgres.
- Auth: **native FastAPI JWT**, not Better Auth — see [05-architecture.md](05-architecture.md) for why. `scripts/seed.py` creates a demo organization + super_admin + event.
- **Exit criteria met**: `POST /auth/login` + `GET /auth/me` work end-to-end against the seeded admin; migrations run clean. (No admin dashboard UI yet, so "empty dashboard renders" doesn't apply — that's Milestone 3.)

### Milestone 1 — Core Donation Flow ✅ DONE
- Public donation form (general + event-specific), built with a custom-themed shadcn/ui + Tailwind v4, react-hook-form + zod validation.
- Razorpay order creation (`payment_service.py`) + Checkout widget integration (`lib/razorpay.ts`).
- Webhook endpoint with HMAC signature verification, `webhook_events` idempotency table, row-level locking on the donation/payment rows.
- Donation/payment status machine end-to-end, verified by an integration test that drives the real API + a correctly-signed webhook against a real Postgres test database.
- **Exit criteria met** (adapted): a *simulated* signed webhook — standing in for the one step that needs a real Razorpay account — creates a `donation` row with `status=success` and a `payment` row, purely through the webhook path; confirmed the client-callback endpoint never flips status (it's logged-only, verified in code and by test). A real Razorpay test-mode run is documented in [08-local-development.md](08-local-development.md) §8.5 but requires the developer's own test account.

### Milestone 2 — Receipts ✅ DONE
- ReportLab PDF template — all required fields present (org name, receipt no., date, donor details, amount + words, purpose, payment/order IDs, signature line, thank-you message). Org logo/signature images are now real uploads (Milestone 7), not just URL fields.
- Receipt numbering: per-org, per-financial-year, race-condition-safe under concurrency — proven by a test that fires 10 concurrent allocations across separate DB sessions and asserts a gap-free unique sequence.
- Object storage: adapter pattern (`storage_service.py`) with a working `LocalFilesystemStorage` for dev, plus `SupabaseStorage` and `R2Storage` (Cloudflare R2 — this deployment's chosen production backend, see [docs/09-session-handoff.md](09-session-handoff.md)) implementations, both untested against a real account (no credentials available in this environment).
- Resend email integration: real API call when `RESEND_API_KEY` is set, graceful no-op log otherwise.
- **Exit criteria met**: proven via `scripts/simulate_webhook.py` — a donation reaches `success` with a downloadable, correctly-formatted PDF receipt within the same request cycle that processes the webhook.
- **Bugs found and fixed while verifying this milestone**: JWT `exp`/`iat` were encoded as ISO datetime strings instead of the numeric Unix timestamps PyJWT's own expiry check requires; `razorpay.Utility.verify_webhook_signature` was called unbound off the class instead of on an instance; Postgres rejects `FOR UPDATE` combined with an outer join, which the donation+payment lock query initially produced; ReportLab's base-14 Helvetica font has no glyph for the ₹ sign and silently rendered a missing-glyph box (fixed by using "Rs." in PDFs specifically, keeping ₹ on web/email — and re-broken/re-fixed for the new summary-report PDF in Milestone 7, see below).

### Milestone 3 — Admin Dashboard Core ✅ DONE
- Dashboard KPIs (today/week/month/year/all-time total + count), backed by a real SQL aggregation over successful donations.
- Donations list with search/filter (event, donor, status, amount range, date range)/pagination, plus a detail view.
- Donor directory (aggregated total donated + donation count + last donation date) + profile/history view.
- Event CRUD (create/list/get/update/soft-delete, blocked from deleting an event with donations against it).
- **Exit criteria met**: verified in a real browser — admin creates an event via the UI, it appears immediately in the list, and the public `/donate/[slug]` page (built in Milestone 1) already renders whatever's in the `events` table, so a newly created active event is live without any extra wiring. Donations tracked against it show up filtered by `event_id`.
- Standalone `/events/[eventSlug]` public page built in Milestone 7 (see below) — the deviation noted in earlier drafts of this doc is resolved.

### Milestone 4 — Receipt & Report Management ✅ DONE
- Resend receipt action, duplicate receipt generation (watermarked, returned as a direct PDF download).
- CSV export with the same filters as the donations list (capped at 20,000 rows, documented not silent).
- XLSX export (`GET /admin/reports/export.xlsx`, openpyxl) and PDF summary reports (`GET /admin/reports/summary.pdf` — event-wise/monthly/yearly, ReportLab) — built in Milestone 7.
- **Exit criteria met**: a treasurer-role admin resends a receipt email, downloads a CSV/XLSX of a date range, and downloads a yearly/monthly/event summary PDF, all verified via automated RBAC tests and a live browser session.

### Milestone 5 — RBAC, Audit, Hardening ✅ DONE
- Full role/permission matrix enforcement across all admin endpoints — proven by an automated security sweep (`tests/integration/test_admin_endpoints_security.py`): every endpoint rejects missing/garbage auth, every role boundary is checked with a real HTTP request (not just code inspection), and cross-organization isolation is verified for events, donations, dashboard totals, and user management.
- User management UI: create via email-invite (Milestone 7 — no longer a direct temp password), edit roles/active status, with a self-lockout guard (can't deactivate or demote your own `super_admin` account).
- Audit log capture wired into the actual mutation paths (`admin_login`, `admin_login_failed`, `admin_account_locked`, `admin_2fa_enabled`, `admin_2fa_disabled`, `admin_invite_accepted`, `donation_confirmed`, `donation_payment_failed`, `event_created/updated/deleted`, `event_banner_uploaded`, `receipt_resend_email`, `receipt_duplicate_generated`, `admin_user_created/updated`, `organization_updated`, `organization_logo_uploaded`, `organization_signature_uploaded`) + a viewer UI.
- Rate limiting on login (5/min/IP) and donation initiation (10/min/IP), **plus** per-identity rate limiting (10/hour per mobile number, independent of IP) and account lockout after 5 failed logins (15 min, Milestone 7); refresh-token rotation also revokes the exchanged token (closing a replay window the original design left open).
- **Exit criteria met**: 121 backend tests pass, including a dedicated security sweep with per-role denial assertions (not just "it compiles") and cross-org isolation tests that insert real data into a second organization and assert it's neither visible nor mutable from the first org's session.

### Milestone 6 — Production Launch — NOT STARTED
- Staging environment with Razorpay test mode fully rehearsed end-to-end.
- Production deploy — **Cloudflare Pages** (frontend), **Render** (backend), **Supabase** (Postgres only), **Cloudflare R2** (receipt storage) — decided, not yet connected. Custom domain, monitoring/alerting (Sentry, uptime) not yet set up.
- Go-live with real organization, first live donation reconciled manually against Razorpay dashboard.
- **Exit criteria**: First real donor payment processed, receipt received, and reconciled correctly in production.

### Milestone 7 — Hardening & Feature Completion ✅ DONE

Closed every gap tracked in this doc's previous drafts (and in `docs/09-session-handoff.md` §6 "What's NOT built"), with a security-first ordering and a dedicated adversarial review pass at the end.

- **Signed, expiring receipt-download tokens**: `GET /receipts/{number}/download` now requires a `?token=` minted by `create_receipt_download_token` (JWT, `purpose=receipt_download`, scoped to one specific receipt id, 30-day expiry) — closes the "sequential receipt numbers are enumerable" gap flagged since Milestone 5. Same generic 401 whether the token is missing, invalid, expired, or valid-for-a-different-receipt.
- **Per-identity rate limiting + account lockout**: `app/core/identity_rate_limit.py` (in-memory sliding window, mirrors slowapi's own "single-instance in-memory is fine at this scale" call) limits donation-initiate attempts per mobile number, independent of the existing per-IP limit. `admin_users.failed_login_attempts`/`locked_until` lock an account for 15 minutes after 5 consecutive failed logins (password or TOTP code) — the lockout message is identical to "invalid credentials" so it can't be used to fingerprint account state.
- **2FA (TOTP)**: `pyotp` + QR enrollment (`POST /auth/2fa/setup`, `/2fa/enable`, `/2fa/disable`), a two-step login (`POST /auth/login` returns `mfa_required`+`mfa_token` when enabled; `POST /auth/login/verify-2fa` completes it) — see `app/services/totp_service.py`, `app/services/auth_service.py`.
- **Real image upload**: `POST /admin/events/{id}/banner`, `/admin/organization/logo`, `/admin/organization/signature` — multipart, magic-byte-validated (PNG/JPEG/WEBP, 5MB cap, server-generated filenames — see `app/core/file_validation.py`), stored via the existing storage adapter, served back through a new public `GET /assets/{key}` route restricted to an allowlist of safe prefixes (never `receipts/`).
- **Email-invite flow**: `POST /admin/users` no longer takes a `password` — it generates a random unusable password plus a hashed, single-use, 7-day invite token; the new admin sets their own password via `/admin/accept-invite` (frontend) → `POST /auth/accept-invite` (backend, public by design). Falls back to returning the raw invite link in the API response when Resend isn't configured (never logged — see the security-review finding below).
- **XLSX + PDF summary reports**: `GET /admin/reports/export.xlsx` (openpyxl, same filters/cap as the CSV export) and `GET /admin/reports/summary.pdf` (event-wise/monthly/yearly totals, ReportLab).
- **Durable task queue**: `app/worker/queue.py` chooses RQ+Redis (`app/worker/rq_queue.py`, `scripts/worker.py`) over in-process `BackgroundTasks` when `REDIS_URL` is set — same adapter pattern as storage/email. `docker-compose.yml` has an opt-in `redis` service behind the `durable-queue` profile.
- **CI pipeline**: `.github/workflows/ci.yml` — backend job (ruff hard gate, mypy advisory/non-blocking, `alembic upgrade head` against a fresh Postgres service container, full pytest run) and frontend job (lint, typecheck, build).
- **Frontend Dockerfile**: multi-stage, Next.js `output: "standalone"` — not the actual deployment path (Cloudflare Pages) but a verified local-container/fallback option. Built and smoke-tested against a running container.
- **Standalone public `/events/[eventSlug]` page**: resolves the Milestone 3 deviation.
- **Self-service password reset**: `POST /auth/forgot-password` → `POST /auth/reset-password` — closes the gap where an admin locked out or with a forgotten password had no way back in except a super_admin or developer editing the database directly (which is literally how a real lockout during this project's own Supabase setup was resolved, prompting this feature). Same email-based, single-use-token pattern as the invite flow, with the same "never log or return the raw token" discipline; also clears any active account lockout on a successful reset.
- **Independent security review** (see `docs/06-deployment-security.md` §6.3): two parallel adversarial passes (backend, frontend) over the full diff found one real, actionable issue — `send_admin_invite_email`'s no-op fallback logged the raw invite token (a bearer credential equivalent to a password-reset link, sufficient alone to take over a freshly-created account including a super_admin) at INFO level. Fixed by dropping the token from the log line entirely; a regression test (`test_invite_token_is_never_logged`) asserts it never appears in captured logs again.
- **Real bug found along the way**: `format_inr()`/`format_inr_for_pdf()` received a `Decimal` (not `int`) from the new SQL `SUM()` aggregate queries and crashed with `ValueError: invalid format string` — fixed by normalizing via `int()` inside both formatters. Caught live (not just by a passing test) via a Playwright-driven summary-PDF download that rendered the ₹ symbol as a missing-glyph black box (the same font issue Milestone 2 already fixed once for receipts, reintroduced because the new summary-report code called `format_inr()` instead of `format_inr_for_pdf()`) and via a local-dev image-serving bug (`serve_local_file` hardcoded `media_type="application/pdf"` from its receipts-only origins, so uploaded PNGs/JPEGs were served with the wrong Content-Type and silently refused by the browser under `X-Content-Type-Options: nosniff`) — both fixed and covered by regression tests.
- **Exit criteria met**: 130 backend tests pass (up from 75 at the end of Milestone 5); ruff clean; frontend lint/typecheck/build clean; every new flow (2FA enrollment + login challenge, image upload round-trip including public re-fetch, invite creation → accept → login, XLSX/PDF report downloads, the standalone event page, forgot/reset-password) verified live in a real browser via Playwright, not just unit tests.

### Post-Launch — Stabilization
- Monitor real usage, fix edge cases (webhook retries, email deliverability, PDF rendering under real org logos of varying sizes).
- Prioritize roadmap items above based on actual organization feedback, not speculation.

## 7.3 Definition of Done (applies to every milestone)

- Automated tests cover the happy path and at least one failure path.
- No secrets in source control; `.env.example` updated for any new required variable.
- API changes reflected in OpenAPI schema and this documentation set kept in sync.
- Feature reviewed against the [Roles & Permission Matrix](01-prd.md#19-roles--permission-matrix) — no endpoint shipped without an explicit role check.
