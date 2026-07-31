FROM python:3.11-slim AS base

WORKDIR /app

# System deps for psycopg (libpq) — psycopg[binary] vendors its own libpq,
# but keeping this here documents the dependency explicitly and covers any
# future switch to psycopg[c] for performance.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/var \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/healthz').raise_for_status()"

# Migrations are run as a separate deploy step (`alembic upgrade head`), not
# on container boot — see docs/06-deployment-security.md §6.2, which avoids a
# race between multiple instances migrating concurrently on a rolling deploy.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
