# 1. Product Requirements Document (PRD)

## 1.1 Product Vision

Build a centralized, professional Donation Management Platform that lets a charitable organization accept online donations for events/causes, automatically verify payments, and issue compliant, downloadable PDF receipts — while giving administrators a single dashboard to track collections, donors, and events.

Although the first deployment serves **one organization**, the system is architected multi-tenant-ready from day one: every core table carries an `organization_id`, and auth/authorization is scoped per-organization so additional organizations can be onboarded later without a schema or auth redesign.

## 1.2 Problem Statement

Today, donations arrive through disconnected channels (UPI apps, bank transfer, cash, QR codes). This causes:
- No single source of truth for who donated, how much, and for what.
- Manual, error-prone, and slow receipt generation.
- No donor history, so repeat donors aren't recognized.
- No reporting for the treasurer/board (monthly/yearly/event-wise).
- No audit trail if a donation or receipt is disputed.

## 1.3 Goals / Non-Goals

**Goals**
- One donation page per event, or a general donation page.
- Real-time payment verification via Razorpay webhooks (never trust client-side "success").
- Instant, automated PDF receipt generation + email delivery.
- Admin dashboard for donations, donors, events, and reports.
- Foundation for multi-org SaaS (schema, auth, and routing designed for it) without over-building it now.

**Non-Goals (v1)**
- Multi-organization self-serve signup (org is provisioned manually by us in v1).
- Volunteer portal, recurring/subscription donations, multi-currency, multiple payment gateways (all roadmap items — see [07-roadmap.md](07-roadmap.md)).
- Native mobile apps.

## 1.4 Target Users / Personas

| Persona | Description | Key Needs |
|---|---|---|
| **Donor** | General public donating to an event/cause | Fast, trustworthy checkout; instant receipt |
| **Admin (Treasurer)** | Manages finances for the org | Accurate records, exports, reconciliation |
| **Admin (Event Coordinator)** | Creates/manages events | Simple event CRUD, donation link per event |
| **Super Admin (Org Owner)** | Owns the org's account | User/role management, org settings, branding |
| **(Future) Platform Owner** | Operates the SaaS across orgs | Org provisioning, billing, platform analytics |

## 1.5 Functional Requirements

### FR-1: Public Donation Page
- FR-1.1: Publicly accessible page per event (`/donate/[eventSlug]`) and a general org donation page (`/donate`).
- FR-1.2: Collects donor Full Name, Mobile Number (required); Email, Address, PAN (optional).
- FR-1.3: Donor selects/enters donation amount; supports preset amount chips + custom amount.
- FR-1.4: Donor selects donation purpose/event (pre-filled if arriving via event-specific link).
- FR-1.5: Initiates Razorpay Checkout (Orders API) for UPI, cards, net banking, wallets.
- FR-1.6: On completion, redirects to a receipt/confirmation page showing status.
- FR-1.7: Mobile-responsive, accessible (WCAG 2.1 AA), completes in ≤ 4 form fields before payment.

### FR-2: Payment Processing
- FR-2.1: Backend creates a Razorpay Order before checkout opens (amount, currency, receipt reference, notes).
- FR-2.2: Backend verifies payment via Razorpay webhook signature (`X-Razorpay-Signature`, HMAC-SHA256) — never marks a donation successful from client callback alone.
- FR-2.3: Idempotent webhook handling (Razorpay may redeliver events).
- FR-2.4: Payment states tracked: `created → authorized → captured → failed/refunded`.

### FR-3: Donation Recording
- FR-3.1: On verified payment capture, create/upsert Donor record (dedupe by mobile number + org).
- FR-3.2: Create Donation record linked to Donor, Event, Payment, Organization.
- FR-3.3: Generate a unique, sequential, org-scoped Receipt Number (e.g. `ORG/2026-27/000123`).

### FR-4: Receipt Generation
- FR-4.1: Auto-generate PDF receipt on successful payment (ReportLab), containing all fields listed in the brief (org name/logo, receipt no., date, donor name, mobile, amount, purpose, payment ID, transaction ID, signature, thank-you note).
- FR-4.2: Store receipt PDF in object storage (Supabase Storage / S3-compatible) with the DB storing only the URL/key.
- FR-4.3: Receipt downloadable immediately from confirmation page and donor's history page.
- FR-4.4: Receipt emailed automatically if donor supplied an email.

### FR-5: Admin Dashboard
- FR-5.1: KPI cards — today/week/month/year totals, total collection, recent donations feed.
- FR-5.2: Donations table — search, filter (event, donor, amount range, date range, payment status), pagination, sort.
- FR-5.3: Donation detail view with full audit trail.
- FR-5.4: Receipt actions — view, download, resend by email, generate duplicate (watermarked "DUPLICATE").
- FR-5.5: Event CRUD — title, description, banner image, status (draft/active/closed), start/end date, auto-generated donation link/slug.
- FR-5.6: Donor directory with full donation history per donor.
- FR-5.7: Role-based views (Super Admin sees user/role management; Treasurer sees finance; Coordinator sees events only).

### FR-6: Reporting & Export
- FR-6.1: Export donations to Excel (.xlsx) and CSV with active filters applied.
- FR-6.2: PDF summary reports — event-wise, monthly, yearly.
- FR-6.3: Donor history export (single donor, all-time).

### FR-7: Authentication & Authorization
- FR-7.1: Admin login (email/password + optional 2FA) scoped to an organization.
- FR-7.2: Role-based access control: `super_admin`, `admin`, `treasurer`, `coordinator`, `viewer`.
- FR-7.3: Public donor-facing pages require no authentication.
- FR-7.4: (Future) Donor login for self-service receipt/history access.

### FR-8: Audit Logging
- FR-8.1: Every mutating admin action (create/update/delete on donation, event, receipt resend, role change) is logged with actor, timestamp, before/after diff.

## 1.6 Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Public donation page LCP < 2.5s on 4G; API p95 < 300ms for reads, < 800ms for payment-order creation |
| **Availability** | 99.5% uptime target for v1 (single-org); backend stateless & horizontally scalable |
| **Scalability** | Support 10k+ donations/event burst (e.g. annual function day) without manual intervention |
| **Security** | OWASP Top 10 mitigations, TLS everywhere, secrets in env vars/secret manager, webhook signature verification, rate limiting on public endpoints |
| **Data Integrity** | Payment verification is server-authoritative; donation record only created after webhook confirms capture |
| **Auditability** | All financial mutations logged immutably (append-only audit_logs table) |
| **Compliance** | PAN handling per Indian IT Act (80G receipt requirements); PII encrypted at rest where supported by Supabase; data retention policy configurable |
| **Maintainability** | Typed end-to-end (TypeScript + Pydantic), migrations via Alembic, documented API (OpenAPI/Swagger auto-generated by FastAPI) |
| **Observability** | Structured logging, error tracking (Sentry), webhook delivery logs retained 90 days |
| **Multi-tenancy readiness** | Every core table has `organization_id`; no cross-org query without an explicit org filter; row-level isolation enforced in the data-access layer |
| **Cost** | Deployable on free/low tiers (Cloudflare Pages free tier, Render starter, Supabase free/pro, Cloudflare R2's free egress) for a single-org launch — see [09-session-handoff.md](09-session-handoff.md) for the actual chosen stack |
| **Accessibility** | WCAG 2.1 AA on donor-facing pages |
| **i18n readiness** | Currency/locale formatting isolated in a utility layer (INR only in v1, extensible later) |

## 1.7 User Stories

### Donor
- As a donor, I want to donate in under a minute so that I don't abandon the process.
- As a donor, I want to choose which event/cause my money supports so that I know my contribution's purpose.
- As a donor, I want to receive a PDF receipt immediately so that I have proof for tax/personal records.
- As a donor, I want my receipt emailed to me so that I don't lose it.
- As a donor, I want to trust that my payment details are handled securely (Razorpay-hosted checkout, no card data touches the org's servers).

### Admin — Treasurer
- As a treasurer, I want a dashboard showing today's/month's/year's collections so I can report to the board without manual tallying.
- As a treasurer, I want to filter donations by date range and export to Excel so I can do monthly reconciliation.
- As a treasurer, I want to resend a receipt by email when a donor says they didn't receive it.
- As a treasurer, I want a duplicate-receipt feature so I can help a donor who lost their original.

### Admin — Event Coordinator
- As a coordinator, I want to create an event with a banner and description so it looks professional on the public page.
- As a coordinator, I want a shareable donation link per event so I can post it on WhatsApp/social media.
- As a coordinator, I want to close an event's donation window after its end date automatically.

### Admin — Super Admin
- As a super admin, I want to invite other admins and assign roles so access is least-privilege.
- As a super admin, I want an audit log of who changed what so I can investigate discrepancies.

### System
- As the system, I must never record a donation as successful unless Razorpay's webhook confirms capture with a verified signature.
- As the system, I must generate a receipt number that is unique and sequential per organization per financial year, for statutory compliance (Section 80G).

## 1.8 Information Architecture

```
Public Site (donor-facing, unauthenticated)
├── / (org landing — optional, org branding, list of active events)
├── /donate                      (general donation form)
├── /donate/[eventSlug]          (event-specific donation form, pre-filled purpose)
├── /receipt/[receiptNumber]     (receipt confirmation + download, token-gated)
└── /events/[eventSlug]          (public event details page)

Admin Dashboard (authenticated, RBAC-gated) — /admin/*
├── /admin/login
├── /admin (dashboard home — KPIs, recent donations)
├── /admin/donations             (list, search, filter)
│   └── /admin/donations/[id]    (detail, resend/duplicate receipt)
├── /admin/donors
│   └── /admin/donors/[id]       (donor profile + history)
├── /admin/events
│   ├── /admin/events/new
│   └── /admin/events/[id]/edit
├── /admin/reports               (Excel/CSV/PDF exports, summaries)
├── /admin/users                 (role/permission management — super_admin only)
├── /admin/audit-logs            (super_admin/treasurer only)
└── /admin/settings              (org profile, branding, receipt template, signature image)
```

## 1.9 Roles & Permission Matrix

| Capability | super_admin | admin | treasurer | coordinator | viewer |
|---|---|---|---|---|---|
| View dashboard/donations | ✅ | ✅ | ✅ | ✅ (own events) | ✅ |
| Export reports | ✅ | ✅ | ✅ | ❌ | ❌ |
| Resend/duplicate receipt | ✅ | ✅ | ✅ | ❌ | ❌ |
| Create/edit events | ✅ | ✅ | ❌ | ✅ | ❌ |
| Manage users/roles | ✅ | ❌ | ❌ | ❌ | ❌ |
| View audit logs | ✅ | ❌ | ✅ | ❌ | ❌ |
| Edit org settings/branding | ✅ | ❌ | ❌ | ❌ | ❌ |
