# Donation Management & Receipt Generation Platform

A production-ready, multi-tenant-ready SaaS platform for managing charitable donations, automated receipt generation, and event-based fundraising.

**Status**: Foundations, the full donor-facing donation flow, receipt generation, the full admin dashboard, and a complete security/feature hardening pass (2FA, account lockout, per-identity rate limiting, signed receipt-download tokens, real image upload, email-invite for new admins, XLSX/PDF reports, an optional durable task queue, CI) are all implemented, tested (121 backend tests, incl. a dedicated RBAC + cross-org-isolation security sweep and an independent adversarial security review), and verified end-to-end in a real browser (Roadmap Milestones 0–5 and 7). Not yet built: production deployment (Milestone 6 — nothing is connected/live yet) and dependency vulnerability scanning in CI. See [docs/07-roadmap.md](docs/07-roadmap.md) for the full done-vs-planned breakdown.

**Picking this up fresh (new session, new person)?** Read [docs/09-session-handoff.md](docs/09-session-handoff.md) first — it's a complete context-recovery briefing (decisions made, bugs found and fixed, what's real vs. planned).

**Get it running locally in ~10 minutes**: [docs/08-local-development.md](docs/08-local-development.md).

## Documentation Index

| # | Document | Contents |
|---|----------|----------|
| 1 | [docs/01-prd.md](docs/01-prd.md) | Product Requirements Document, Functional & Non-Functional Requirements, User Stories, Information Architecture |
| 2 | [docs/02-user-flows.md](docs/02-user-flows.md) | User Flow Diagrams, Auth Flow, Payment Flow, Webhook Processing Flow, PDF Generation Flow, Email Workflow |
| 3 | [docs/03-database-schema.md](docs/03-database-schema.md) | Database Schema, ER Diagram, Indexing & Multi-tenancy Strategy |
| 4 | [docs/04-api-specification.md](docs/04-api-specification.md) | REST API Specification (all endpoints, request/response contracts) |
| 5 | [docs/05-architecture.md](docs/05-architecture.md) | Backend Architecture, Frontend Architecture, Folder Structure, Git Repository Structure, Coding Standards |
| 6 | [docs/06-deployment-security.md](docs/06-deployment-security.md) | Deployment Architecture, Security Best Practices |
| 7 | [docs/07-roadmap.md](docs/07-roadmap.md) | Future Roadmap, Development Milestones (with current build status) |
| 8 | [docs/08-local-development.md](docs/08-local-development.md) | Running everything locally, incl. testing the donation→receipt pipeline without a Razorpay account |
| 9 | [docs/09-session-handoff.md](docs/09-session-handoff.md) | Full context-recovery briefing — read this first if you're new to the project |

## Quick Summary

- **Frontend**: Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui
- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
- **Database**: PostgreSQL (Supabase in production, via its Session Pooler connection string; Docker Postgres locally)
- **Auth**: Native FastAPI JWT (access + refresh, bcrypt, RBAC) — see [docs/05-architecture.md](docs/05-architecture.md) for why this superseded the original Better Auth/Clerk options
- **Payments**: Razorpay (Orders API + Webhooks)
- **Email**: Resend
- **PDF**: ReportLab
- **Receipt storage**: Cloudflare R2 (chosen over Supabase Storage — zero egress fees; `SupabaseStorage` remains in the codebase as an alternative backend, just unused in this deployment)
- **Hosting**: Cloudflare Pages (frontend) · Render (backend) · Supabase (DB) — none of these are connected/deployed yet, see [docs/09-session-handoff.md](docs/09-session-handoff.md) §2
- **Security**: TOTP 2FA, account lockout, per-identity + per-IP rate limiting, signed receipt-download tokens, magic-byte-validated image uploads — see [docs/06-deployment-security.md](docs/06-deployment-security.md)
- **CI**: GitHub Actions (`.github/workflows/ci.yml`) — ruff/mypy/alembic/pytest for the backend, lint/typecheck/build for the frontend

## Repository Layout

```
donation/
├── backend/    FastAPI application (incl. Dockerfile) — see docs/05-architecture.md §5.4
├── frontend/   Next.js application (incl. Dockerfile)
├── docs/       this documentation set
├── infra/      local Postgres init scripts
└── .github/    CI workflow
```

## Reading Order

If you're onboarding onto this project for the first time, read in this order:
1. `09-session-handoff.md` — the fastest way to get fully up to speed
2. `01-prd.md` — understand *what* we're building and *why*
3. `03-database-schema.md` — understand the data model
4. `02-user-flows.md` — understand how data moves through the system
5. `04-api-specification.md` — the contract between frontend and backend
6. `05-architecture.md` — how the code is organized
7. `06-deployment-security.md` — how it ships and how it's protected
8. `07-roadmap.md` — where it's headed
9. `08-local-development.md` — how to actually run it
