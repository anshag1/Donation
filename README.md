# Donation Management & Receipt Generation Platform

A production-ready, multi-tenant-ready SaaS platform for managing charitable donations, automated receipt generation, and event-based fundraising.

**Status**: Foundations, the full donor-facing donation flow, receipt generation, and the admin dashboard (dashboard KPIs, events/donations/donors, users & roles, audit log, org settings, CSV export) are implemented, tested (75 backend tests, incl. a dedicated RBAC + cross-org-isolation security sweep), and verified end-to-end in a real browser (Roadmap Milestones 0–5). Not yet built: XLSX/PDF report formats, 2FA, real image upload for banners/logos, and production deployment. See [docs/07-roadmap.md](docs/07-roadmap.md) for the full done-vs-planned breakdown.

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

## Quick Summary

- **Frontend**: Next.js 16 (App Router) + TypeScript + Tailwind CSS v4 + shadcn/ui
- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2
- **Database**: PostgreSQL (Supabase in production; Docker Postgres locally)
- **Auth**: Native FastAPI JWT (access + refresh, bcrypt, RBAC) — see [docs/05-architecture.md](docs/05-architecture.md) for why this superseded the original Better Auth/Clerk options
- **Payments**: Razorpay (Orders API + Webhooks)
- **Email**: Resend
- **PDF**: ReportLab
- **Hosting**: Vercel (frontend) · Render/Railway (backend) · Supabase (DB)

## Repository Layout

```
donation/
├── backend/    FastAPI application — see docs/05-architecture.md §5.4
├── frontend/   Next.js application
├── docs/       this documentation set
└── infra/      local Postgres init scripts
```

## Reading Order

If you're onboarding onto this project for the first time, read in this order:
1. `01-prd.md` — understand *what* we're building and *why*
2. `03-database-schema.md` — understand the data model
3. `02-user-flows.md` — understand how data moves through the system
4. `04-api-specification.md` — the contract between frontend and backend
5. `05-architecture.md` — how the code is organized
6. `06-deployment-security.md` — how it ships and how it's protected
7. `07-roadmap.md` — where it's headed
8. `08-local-development.md` — how to actually run it
