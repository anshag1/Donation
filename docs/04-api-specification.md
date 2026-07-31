# 4. API Specification

**Build status**: everything in this document is implemented and covered by automated tests (75 backend tests: unit + integration + a dedicated admin-endpoint security sweep — see [07-roadmap.md](07-roadmap.md)), with the specific exceptions called out inline: 2FA isn't built, XLSX/PDF report formats aren't built (CSV is), and the receipt-download endpoint doesn't yet require a signed token (§4.1).

Base URL: `https://api.<org-domain>/api/v1`
FastAPI auto-generates OpenAPI/Swagger at `/docs` and `/openapi.json` — this document is the human-readable contract; the generated spec is the source of truth for exact schemas.

Conventions:
- All responses: `{ "data": ..., "error": null }` on success, `{ "data": null, "error": { "code": "...", "message": "..." } }` on failure.
- Money fields always in **paise** (integer) in the API; frontend formats to ₹.
- All list endpoints support `?page=&page_size=&sort=&order=`.
- Auth: `Authorization: Bearer <jwt>` for admin routes (or httpOnly session cookie, browser default). Public routes require none.
- Every admin route implicitly scopes to the caller's `organization_id` — never accepted as a request parameter.

## 4.1 Public Endpoints (Unauthenticated)

### `GET /events/public`
List active, published events for the org's donation landing page.
Response: `[{ id, title, slug, banner_url, short_description, start_date, end_date }]`

### `GET /events/public/{slug}`
Get a single event's public details for the donation page.

### `POST /donations/initiate`
Create a pending donation + Razorpay order.
```json
// Request
{
  "event_id": "uuid | null",
  "donor": {
    "full_name": "string",
    "mobile_number": "string",
    "email": "string | null",
    "address": "string | null",
    "pan_number": "string | null"
  },
  "amount_in_paise": 500000,
  "purpose": "string | null"
}
```
```json
// Response
{
  "data": {
    "donation_id": "uuid",
    "razorpay_order_id": "order_xxx",
    "razorpay_key_id": "rzp_live_xxx",
    "amount_in_paise": 500000,
    "currency": "INR"
  }
}
```
Rate limited (e.g. 10 req/min/IP) + basic bot-mitigation (honeypot field / Turnstile if abuse observed).

### `GET /donations/{id}/status`
Poll donation status post-checkout (used while waiting for webhook confirmation).
```json
{ "data": { "status": "pending|success|failed", "receipt_number": "string|null", "receipt_download_url": "string|null" } }
```

### `POST /donations/{id}/client-callback`
Informational only — records the client-side Razorpay checkout callback for UX/telemetry. **Never** flips donation status; only logs that the client believes payment succeeded, for reconciliation if the webhook is delayed/lost.

### `GET /receipts/{receipt_number}/download`
Redirects to a short-lived signed URL for the PDF (or, in local-first dev without Supabase Storage configured, to `GET /receipts/local-file/{key}`, which streams straight from disk).
**Current implementation gap**: this route does not yet require the signed token / mobile-verification param described in the original design below — it's reachable by receipt number alone, which is sequential and low-entropy. Tracked explicitly (see the code comment in `app/api/v1/public/receipts.py`) as a hardening item for the admin-dashboard pass, alongside the resend/duplicate-receipt admin actions it naturally belongs with — not a silently-dropped requirement.
*Original design intent, not yet built*: requires `receipt_number` **plus** a signed token query param (`?token=`) issued at donation confirmation time, or donor mobile-number verification for out-of-band access.

## 4.2 Webhook Endpoint

### `POST /webhooks/razorpay`
Receives Razorpay events. Verifies `X-Razorpay-Signature` against raw request body using the webhook secret before parsing. Idempotent via `webhook_events.event_id`. Returns `200` fast; the receipt PDF + email are generated in a background task (`app/worker/tasks.py`, dispatched via FastAPI `BackgroundTasks`) using their own DB session, not the request's.

Handled `event`s (as implemented): `payment.captured`, `payment.failed`. `payment.authorized`, `refund.created`, `refund.processed` are in the original design but not yet handled — donations settle on capture in the current flow, and refunds aren't modeled yet (no admin action produces one).

## 4.3 Admin Endpoints (Authenticated, RBAC-enforced)

### Auth
Native FastAPI JWT (see [05-architecture.md](05-architecture.md) for why this superseded Better Auth/Clerk).
- ✅ `POST /auth/login` — email + password → `{access_token}` in body; refresh token set as an httpOnly cookie (`path=/api/v1/auth`). Rate limited 5/min/IP. Writes an `admin_login` (or `admin_login_failed`) audit log entry.
- ✅ `POST /auth/refresh` — reads the refresh cookie, checks it against `revoked_refresh_tokens`, returns a new access token, and rotates the refresh cookie — **revoking the token just exchanged** so it can't be replayed even if it leaked.
- ✅ `POST /auth/logout` — revokes the current refresh token's `jti` and clears the cookie. (Access tokens themselves stay stateless/short-lived — logout doesn't invalidate an already-issued access token early, only prevents getting new ones.)
- ✅ `GET /auth/me` — current admin's id/org/email/roles, from the Bearer access token.
- ○ `POST /auth/2fa/verify` — not yet built (`admin_users.two_factor_enabled` column exists; TOTP flow is a roadmap item).

### Dashboard ✅
- `GET /admin/dashboard/summary` *(any authenticated role)* → today/week/month/year/all-time totals (successful donations only), total count, and the 10 most recent donations.

### Donations ✅
- `GET /admin/donations` *(any authenticated role)* — filters: `event_id`, `donor_id`, `status`, `min_amount_in_paise`, `max_amount_in_paise`, `date_from`, `date_to`, `q` (donor name/mobile search, matched against the live `donors` row — display values come from each donation's frozen snapshot)
- `GET /admin/donations/{id}` *(any authenticated role)* — full detail incl. payment + receipt
- `POST /admin/donations/{id}/receipt/resend-email` *(role: super_admin, admin, treasurer)*
- `POST /admin/donations/{id}/receipt/duplicate` *(role: super_admin, admin, treasurer)* → returns the watermarked PDF directly as `application/pdf` (not the `{data,error}` envelope — this is a file download, not a data response)

### Donors ✅
- `GET /admin/donors` *(any authenticated role)* — search by name/mobile/email; each row aggregates total donated + count + last donation date over that donor's successful donations
- `GET /admin/donors/{id}` *(any authenticated role)* — profile + full donation history

### Events ✅
- `GET /admin/events`, `GET /admin/events/{id}` *(any authenticated role)*
- `POST /admin/events`, `PATCH /admin/events/{id}` *(role: super_admin, admin, coordinator)*
- `DELETE /admin/events/{id}` *(role: super_admin, admin, coordinator)* — soft delete; 400s if the event has any donations (close it instead)
- ○ `POST /admin/events/{id}/banner` (multipart upload) — not built; `banner_url` is a plain string field the admin pastes in instead. Real image upload needs the storage abstraction wired up for images specifically, deferred as a deliberate scope cut, not an oversight.

### Reports
- ✅ `GET /admin/reports/export.csv` *(role: super_admin, admin, treasurer)* — same filters as the donations list, capped at 20,000 rows (documented, not silent)
- ○ `GET /admin/reports/export.xlsx`, `GET /admin/reports/summary.pdf`, `GET /admin/reports/donor/{id}.pdf` — not built; CSV covers the same underlying data for now

### Users & Roles ✅ *(role: super_admin only)*
- `GET /admin/users`
- `POST /admin/users` — creates the account directly with an admin-set temporary password (no email-invite flow yet — that needs Resend wiring for a dedicated template, deferred)
- `PATCH /admin/users/{id}` — update full name / roles / active status. Blocked from deactivating your own account or removing your own `super_admin` role (self-lockout guard)
- ○ `DELETE /admin/users/{id}` — not built as a separate endpoint; use `PATCH` with `is_active: false` instead

### Audit Logs ✅ *(role: super_admin, treasurer)*
- `GET /admin/audit-logs` — filters: `entity_type`, `actor_id`, `date_from`, `date_to`; each row includes the actor's resolved email

### Organization Settings ✅ *(role: super_admin only)*
- `GET /admin/organization`
- `PATCH /admin/organization` — name, contact info, PAN, address, receipt prefix, logo/signature URLs (strings, not file upload — see the Events banner note above)

## 4.4 Error Codes

| Code | Meaning |
|---|---|
| `VALIDATION_ERROR` | Pydantic validation failure (400) |
| `UNAUTHORIZED` | Missing/invalid auth (401) |
| `FORBIDDEN` | Authenticated but lacks role/permission (403) |
| `NOT_FOUND` | Entity doesn't exist or not in caller's org (404) |
| `RATE_LIMITED` | Too many requests (429) |
| `PAYMENT_ORDER_FAILED` | Razorpay order creation failed (502) |
| `WEBHOOK_SIGNATURE_INVALID` | Signature verification failed (400) |
| `CONFLICT` | e.g. duplicate slug (409) |
| `INTERNAL_ERROR` | Unhandled server error (500) |

## 4.5 Rate Limiting

| Endpoint group | Limit | Status |
|---|---|---|
| `POST /donations/initiate` | 10 / min / IP | ✅ implemented |
| `POST /auth/login` | 5 / min / IP | ✅ implemented |
| `POST /webhooks/razorpay` | Not rate-limited (signature verification is the control) | as designed |
| 30/hour/mobile_number on initiate; exponential backoff on login; source-IP allowlisting on the webhook; 100/min/user on other admin endpoints | — | ○ not yet implemented — the two limits above are flat per-IP via `slowapi`'s in-memory storage, sufficient for a single backend instance; revisit when horizontally scaling (see §6.3) |

Implemented via `slowapi`, in-memory storage (`app/core/rate_limit.py`). **Note**: in-memory storage means limits reset on restart and aren't shared across multiple backend instances — fine for v1's single-instance deployment; swap `slowapi`'s `storage_uri` to Redis before running more than one instance behind a load balancer.
