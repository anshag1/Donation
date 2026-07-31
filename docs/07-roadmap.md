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
| **Durable task queue** | Move background PDF/email work from in-process `BackgroundTasks` to Celery/RQ + Redis or a managed queue | Only needed once donation volume risks task loss on redeploy |
| **Donor self-service login** | Donor accounts to view full history without needing the receipt number | Currently receipts are accessed via signed link; full accounts are a bigger auth surface |
| **Signed receipt download tokens** | Require a signed token or mobile-verification on `GET /receipts/{number}/download`, per the original API design | Concrete, scoped hardening item found during the admin-dashboard build — receipt numbers are sequential/low-entropy today |
| **Image upload for event banners & org logo/signature** | Real file upload (multipart) through the storage abstraction, replacing today's plain URL string fields | `storage_service.py`'s adapter already exists for receipt PDFs; extending it to admin-uploaded images is mechanical, just not built yet |
| **Email-invite flow for new admin users** | Send a signup link instead of the super_admin setting a temporary password directly | Needs a dedicated Resend template + a one-time token/expiry model |
| **2FA (TOTP) for admin login** | `admin_users.two_factor_enabled` column already exists | Needs a TOTP library + QR enrollment UI; scoped out of this pass |
| **XLSX and PDF summary reports** | `.xlsx` export and event-wise/monthly/yearly PDF summaries | CSV export (built) covers the same data; these are presentation-layer additions on top of it |

## 7.2 Development Milestones

### Milestone 0 — Foundations ✅ DONE
- Repo scaffolding (monorepo structure per [05-architecture.md](05-architecture.md)); CI pipeline **not yet added** (no `.github/workflows/` — flagged, not silently skipped; straightforward to add once there's a remote to push to).
- Database schema + Alembic migration for all 11 entities, applied and verified against a real local Postgres.
- Auth: **native FastAPI JWT**, not Better Auth — see [05-architecture.md](05-architecture.md) for why. `scripts/seed.py` creates a demo organization + super_admin + event.
- **Exit criteria met**: `POST /auth/login` + `GET /auth/me` work end-to-end against the seeded admin; migrations run clean. (No admin dashboard UI yet, so "empty dashboard renders" doesn't apply — that's Milestone 3.)

### Milestone 1 — Core Donation Flow ✅ DONE
- Public donation form (general + event-specific), built with a custom-themed shadcn/ui + Tailwind v4, react-hook-form + zod validation.
- Razorpay order creation (`payment_service.py`) + Checkout widget integration (`lib/razorpay.ts`).
- Webhook endpoint with HMAC signature verification, `webhook_events` idempotency table, row-level locking on the donation/payment rows.
- Donation/payment status machine end-to-end, verified by an integration test that drives the real API + a correctly-signed webhook against a real Postgres test database.
- **Exit criteria met** (adapted): a *simulated* signed webhook — standing in for the one step that needs a real Razorpay account — creates a `donation` row with `status=success` and a `payment` row, purely through the webhook path; confirmed the client-callback endpoint never flips status (it's logged-only, verified in code and by test). A real Razorpay test-mode run is documented in [08-local-development.md](08-local-development.md) §8.5 but requires the developer's own test account.

### Milestone 2 — Receipts ✅ DONE
- ReportLab PDF template — all required fields present (org name, receipt no., date, donor details, amount + words, purpose, payment/order IDs, signature line, thank-you message). Org logo/signature *images* deferred to the admin-dashboard pass (no upload UI exists yet to provide them).
- Receipt numbering: per-org, per-financial-year, race-condition-safe under concurrency — proven by a test that fires 10 concurrent allocations across separate DB sessions and asserts a gap-free unique sequence.
- Object storage: adapter pattern (`storage_service.py`) with a working `LocalFilesystemStorage` for dev, plus `SupabaseStorage` and `R2Storage` (Cloudflare R2 — this deployment's chosen production backend, see [docs/09-session-handoff.md](09-session-handoff.md)) implementations, both untested against a real account (no credentials available in this environment).
- Resend email integration: real API call when `RESEND_API_KEY` is set, graceful no-op log otherwise.
- **Exit criteria met**: proven via `scripts/simulate_webhook.py` — a donation reaches `success` with a downloadable, correctly-formatted PDF receipt within the same request cycle that processes the webhook.
- **Bugs found and fixed while verifying this milestone** (see [08-local-development.md](08-local-development.md) and inline code comments): JWT `exp`/`iat` were encoded as ISO datetime strings instead of the numeric Unix timestamps PyJWT's own expiry check requires; `razorpay.Utility.verify_webhook_signature` was called unbound off the class instead of on an instance; Postgres rejects `FOR UPDATE` combined with an outer join, which the donation+payment lock query initially produced; ReportLab's base-14 Helvetica font has no glyph for the ₹ sign and silently rendered a missing-glyph box (fixed by using "Rs." in PDFs specifically, keeping ₹ on web/email).

### Milestone 3 — Admin Dashboard Core ✅ DONE
- Dashboard KPIs (today/week/month/year/all-time total + count), backed by a real SQL aggregation over successful donations.
- Donations list with search/filter (event, donor, status, amount range, date range)/pagination, plus a detail view.
- Donor directory (aggregated total donated + donation count + last donation date) + profile/history view.
- Event CRUD (create/list/get/update/soft-delete, blocked from deleting an event with donations against it).
- **Exit criteria met**: verified in a real browser — admin creates an event via the UI, it appears immediately in the list, and the public `/donate/[slug]` page (built in Milestone 1) already renders whatever's in the `events` table, so a newly created active event is live without any extra wiring. Donations tracked against it show up filtered by `event_id`.
- **Deviation**: `/events/[eventSlug]` as a *standalone* public event-details page (separate from the donation form) wasn't built — the donation form itself (`/donate/[eventSlug]`) already shows the event banner/description inline, which covers the same need for v1.

### Milestone 4 — Receipt & Report Management — MOSTLY DONE
- ✅ Resend receipt action, duplicate receipt generation (watermarked, returned as a direct PDF download).
- ✅ CSV export with the same filters as the donations list (capped at 20,000 rows, documented not silent).
- ○ Excel (.xlsx) export and PDF summary reports (event-wise/monthly/yearly) — not built. CSV covers the same underlying data; XLSX/PDF are presentation-layer additions on top of data access that already exists, reasonable to defer until an org actually asks for that specific format.
- **Exit criteria** (adapted): a treasurer-role admin resends a receipt email and downloads a CSV of a date range, both verified via automated RBAC tests and a live browser session — matching totals against the dashboard wasn't separately re-verified since both read from the same `donation_repo` queries.

### Milestone 5 — RBAC, Audit, Hardening ✅ DONE
- Full role/permission matrix enforcement across all 20 admin endpoints — proven by an automated security sweep (`tests/integration/test_admin_endpoints_security.py`): every endpoint rejects missing/garbage auth, every role boundary is checked with a real HTTP request (not just code inspection), and cross-organization isolation is verified for events, donations, dashboard totals, and user management.
- User management UI: create (direct password, not email-invite — deferred), edit roles/active status, with a self-lockout guard (can't deactivate or demote your own `super_admin` account).
- Audit log capture wired into the actual mutation paths (`admin_login`, `admin_login_failed`, `donation_confirmed`, `donation_payment_failed`, `event_created/updated/deleted`, `receipt_resend_email`, `receipt_duplicate_generated`, `admin_user_created/updated`, `organization_updated`) + a viewer UI.
- Rate limiting on login (5/min/IP) and donation initiation (10/min/IP); refresh-token rotation now also revokes the exchanged token (closing a replay window the original design left open — see [06-deployment-security.md](06-deployment-security.md)).
- **Exit criteria met**: 75 backend tests pass, including a dedicated security sweep with per-role denial assertions (not just "it compiles") and cross-org isolation tests that insert real data into a second organization and assert it's neither visible nor mutable from the first org's session.

### Milestone 6 — Production Launch (Week 10–12) — NOT STARTED
- Staging environment with Razorpay test mode fully rehearsed end-to-end.
- Production deploy — **Cloudflare Pages** (frontend), **Render** (backend), **Supabase** (Postgres only), **Cloudflare R2** (receipt storage) — decided, not yet connected. Custom domain, monitoring/alerting (Sentry, uptime) not yet set up.
- Go-live with real organization, first live donation reconciled manually against Razorpay dashboard.
- **Exit criteria**: First real donor payment processed, receipt received, and reconciled correctly in production.

### Post-Launch — Stabilization (Week 12+)
- Monitor real usage, fix edge cases (webhook retries, email deliverability, PDF rendering under real org logos of varying sizes).
- Prioritize roadmap items above based on actual organization feedback, not speculation.

## 7.3 Definition of Done (applies to every milestone)

- Automated tests cover the happy path and at least one failure path.
- No secrets in source control; `.env.example` updated for any new required variable.
- API changes reflected in OpenAPI schema and this documentation set kept in sync.
- Feature reviewed against the [Roles & Permission Matrix](01-prd.md#19-roles--permission-matrix) — no endpoint shipped without an explicit role check.
