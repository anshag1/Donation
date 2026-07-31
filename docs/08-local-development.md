# 8. Local Development

This document describes how to run the platform entirely on your own machine — no Razorpay account, no Resend account, no Supabase project required. Everything degrades gracefully to a local-first mode (see `backend/.env.example`) and becomes "live" the moment real credentials are added.

## 8.1 Prerequisites

- Docker Desktop (for Postgres)
- Python 3.11+
- Node.js 20+
- (Optional) `git`

## 8.2 One-time setup

```bash
# 1. Start Postgres (creates both donation_dev and donation_test databases)
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt    # or requirements-dev.txt to also get ruff/mypy (see §8.6)
cp .env.example .env
# Edit .env: set JWT_SECRET (python -c "import secrets; print(secrets.token_urlsafe(64))")
# and, if the docker-compose port mapping differs, adjust DATABASE_URL's port.
alembic upgrade head
python -m scripts.seed             # creates a demo org, admin user, and event

# 3. Frontend
cd ../frontend
npm install
cp .env.example .env.local
```

> **Note on ports**: this repo's `docker-compose.yml` maps Postgres to host port **5435**, not the default 5432 — chosen to avoid clashing with other local Postgres containers. Adjust `DATABASE_URL` in `backend/.env` if you change this.

## 8.3 Running

```bash
# Terminal 1 — backend
cd backend && source .venv/Scripts/activate
uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs

# Terminal 2 — frontend
cd frontend
npm run dev
# App at http://localhost:3000
```

Visit `http://localhost:3000/donate/annual-function-2026` (the seeded demo event) or `http://localhost:3000/donate` (general donation).

**Demo admin login** (for the future admin dashboard; auth API already works today):
- Email: `admin@example.org`
- Password: `ChangeMe123!`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.org","password":"ChangeMe123!"}'
```

## 8.4 Testing the full donation → receipt pipeline without a Razorpay account

Filling out the donation form and clicking "Donate" **will** call the real backend and create a Razorpay order — but since `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET` are blank by default, that call fails with a clear `PAYMENT_ORDER_FAILED` error (shown as a toast in the UI). That's expected in local-first mode; it proves the integration boundary works correctly, but doesn't get you a completed payment to inspect.

To exercise the **entire post-payment pipeline** — webhook signature verification, idempotency, receipt numbering, PDF rendering, storage, and the email attempt — without a Razorpay account, use the bundled simulation script. It creates a pending donation the same way the real API does, then sends the backend a correctly-signed `payment.captured` webhook, exactly as Razorpay would:

```bash
cd backend
source .venv/Scripts/activate
python -m scripts.simulate_webhook
# Created pending donation <uuid> (order order_sim...)
# Webhook POST -> 200 {'data': {'received': True}, 'error': None}
# Donation status: success
# Receipt number: DEMO/2026-27/000001
# Download at:    http://localhost:8000/api/v1/receipts/local-file/receipts/<org-id>/DEMO_2026-27_000001.pdf
```

Options: `--amount` (paise), `--full-name`, `--mobile`, `--email`, `--base-url`. Open the printed download URL in a browser to inspect the actual rendered PDF receipt.

This script requires `RAZORPAY_WEBHOOK_SECRET` to be set in `backend/.env` (any value works locally — it just needs to match between the script and the running server; `.env.example` ships with a placeholder).

## 8.4b Testing the durable task queue (optional — Redis)

Not needed by default: receipt generation runs in-process via FastAPI `BackgroundTasks` unless `REDIS_URL` is set. To exercise the durable RQ+Redis path instead:

```bash
docker compose --profile durable-queue up -d     # starts Redis on host port 6380
# In backend/.env: REDIS_URL=redis://localhost:6380/0
# Terminal 3 — worker process
cd backend && source .venv/Scripts/activate
python -m scripts.worker
```

Then run `python -m scripts.simulate_webhook` as normal (§8.4) — the receipt job is now enqueued to Redis and processed by the worker process instead of in-process.

## 8.5 Testing against real Razorpay (test mode)

Once you have a [Razorpay test-mode account](https://dashboard.razorpay.com/):

1. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `backend/.env` from the Razorpay dashboard (Settings → API Keys, test mode).
2. Set up a webhook in the Razorpay dashboard pointing at your backend's `/api/v1/webhooks/razorpay` — for local testing this requires a tunnel (e.g. `ngrok http 8000`) since Razorpay needs a public URL to deliver to. Set `RAZORPAY_WEBHOOK_SECRET` to the secret you configure there.
3. Use Razorpay's [test cards/UPI](https://razorpay.com/docs/payments/payments/test-card-upi-details/) to complete a real (test-mode) checkout from the donation form.

## 8.6 Running the backend test suite

```bash
cd backend
source .venv/Scripts/activate
python -m pytest -v
```

Tests run against the separate `donation_test` database (created automatically by `infra/init-test-db.sql` when `docker compose up` first initializes the Postgres volume). They pass with no Razorpay/Resend credentials at all — `payment_service.create_razorpay_order` is monkeypatched in the integration test, and the webhook/PDF/receipt-numbering paths are exercised directly against real Postgres.

**Lint/typecheck** (needs `pip install -r requirements-dev.txt`, matches CI):
```bash
ruff check app tests scripts   # hard gate — must be clean
mypy app                       # advisory only — see docs/06-deployment-security.md for why
```

## 8.7 Common issues

| Symptom | Fix |
|---|---|
| `alembic upgrade head` can't connect | Confirm `docker compose ps` shows `donation_postgres` healthy, and that `DATABASE_URL`'s port matches the compose file's host port mapping. |
| `email-validator is not installed` on backend startup | `pip install -r requirements.txt` again — this is a `pydantic[email]` extra required by `EmailStr` fields. |
| Frontend shows a "Razorpay is not configured" toast on submit | Expected in local-first mode — see §8.4 to test the rest of the pipeline without real keys. |
| Backend won't start: "port already in use" | Something else (or a previous `uvicorn` you forgot to stop) is bound to 8000. Find and stop it, or run on a different `--port` (and update `frontend/.env.local`'s `NEXT_PUBLIC_API_BASE_URL` to match). |
| API responses look stale / a route you just added 404s even though the code is definitely there | An **old** `uvicorn` process from an earlier session may still be running and holding port 8000 alongside (or instead of) your current one — Windows can end up with two processes both showing as listening on the same port. Check `Get-NetTCPConnection -LocalPort 8000` (PowerShell) for more than one PID, and kill the older one (check `Get-Process -Id <pid> | Select StartTime`) before assuming the code itself is broken. Hit for real during the Milestone 7 hardening pass after a session was interrupted and restarted. |
