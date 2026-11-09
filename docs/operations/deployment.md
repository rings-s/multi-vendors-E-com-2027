# Operations and Deployment

## 1. Development environment

Create a complete local development environment.

Use Docker Compose for:

- PostgreSQL.
- Redis.
- FastAPI.
- SvelteKit.

Provide:

- `.env.example`.
- Dockerfiles.
- Docker Compose configuration.
- Database migrations.
- Development seed data.
- Test configuration.
- README.

Never commit secrets.

Include a mock payment provider so the entire application can be developed and tested without production payment credentials.

Clearly distinguish mock payments from real payments in the UI and database.

### 1.1 Implementation status

| Item | Location |
| --- | --- |
| Environment template | [`.env.example`](../../.env.example). The real `.env` is git-ignored. |
| Backend Dockerfile | [`apps/backend/Dockerfile`](../../apps/backend/Dockerfile): `runtime` target (production, non-root, health check) and `dev` target (reload). |
| Compose stack | [`docker-compose.yml`](../../docker-compose.yml): `postgres`, `redis`, one-shot `migrate`, `backend` and `frontend` (SvelteKit dev server). Day-to-day commands are in the root [`Makefile`](../../Makefile) (`make help`). |
| Migrations | Alembic (`apps/backend/migrations`). `0002` installs the immutability and balance triggers and seeds roles, permissions and the global commission. |
| Seed data | `python -m app.cli seed-dev`: idempotent, mock provider only, refused in production. |
| First administrator | `python -m app.cli create-admin --email … --name … --super` (password from `ADMIN_PASSWORD` or a prompt). |
| Tests | `uv run pytest` builds a fresh `<db>_test` database with Alembic and uses Redis DB 15. |
| Mock payments | `PAYMENT_PROVIDER=mock`. Payments, ledger transactions and settlements carry `is_test=true`; `/health` reports `mock_payments`; `/admin/payment-provider` reports `is_test`. |

---

## 2. Deployment (Phase 8)

- Production Docker configuration.
- Environment configuration.
- Database backups.
- Logging.
- Monitoring.
- Error reporting.
- Production migrations.
- Domain and TLS configuration.
- Deployment documentation.

Deliverable: Production deployment package.

### 2.1 Production image

Build the `runtime` target:

```bash
docker build --target runtime -t marketplace-backend:<version> apps/backend
```

The image runs as the unprivileged `app` user with `fastapi run --proxy-headers --workers 2`. The entrypoint is configured in `pyproject.toml`. It exposes port 8000 and has a `HEALTHCHECK` on `/health`. Uploaded images are written to `/app/var/uploads`, so mount a persistent volume there (or replace the storage adapter with object storage).

### 2.2 Environment configuration

Start from `.env.example`. With `ENVIRONMENT=production` the application refuses to start unless:

- `PAYMENT_PROVIDER` is not `mock`;
- `JWT_SECRET` is set to a real secret (`python -c "import secrets; print(secrets.token_urlsafe(48))"`);
- `COOKIE_SECURE=true`;
- with `PAYMENT_PROVIDER=moyasar`: `MOYASAR_SECRET_KEY` and `MOYASAR_WEBHOOK_SECRET` are set.

Additional Moyasar settings (`MOYASAR_PLATFORM_API_KEY`, `MOYASAR_PLATFORM_RECIPIENT_ID`, `MOYASAR_MERCHANT_FEES`, `MOYASAR_SPLITS_ENABLED`, `MOYASAR_LIVE`) depend on the provider agreement. See [moyasar-verification.md](../architecture/moyasar-verification.md). Set `CORS_ORIGINS` to the exact frontend origin(s) and `COOKIE_DOMAIN` when the API and frontend share a parent domain.

Secrets must come from the platform's secret manager (Docker/Kubernetes secrets, Cloudflare or cloud KMS), never from the image or the repository. Provider secret keys are only read by the backend and are never returned by any API.

### 2.3 Production migrations

Run migrations as a separate, single step before rolling out new application containers:

```bash
docker run --rm --env-file prod.env marketplace-backend:<version> alembic upgrade head
```

Never run `alembic downgrade` on production financial tables. Ledger, audit and verification tables are protected by database triggers against UPDATE, DELETE and TRUNCATE. Corrections are made with reversing entries. In CI, `alembic check` verifies that models and migrations are in sync.

### 2.4 Domain, TLS and edge

Terminate TLS at the edge (Cloudflare or a reverse proxy) and forward to the backend over a private network. The backend reads `CF-Connecting-IP` / `X-Forwarded-For` for rate limiting and audit logs, so only trust these headers from your proxy (do not expose the backend directly). Serve the API under `/api` on the same site as the frontend so cookies stay first-party. `SameSite=Lax` cookies plus the double-submit CSRF token protect cookie-authenticated requests.

Webhook endpoint to register with Moyasar: `https://<api-domain>/api/v1/webhooks/moyasar`.

### 2.5 Database backups

- Enable continuous WAL archiving / point-in-time recovery (managed PostgreSQL, or `pgBackRest` / `wal-g`).
- Take a nightly logical backup in addition: `pg_dump --format=custom --no-owner "$DATABASE_URL_SYNC" > marketplace-$(date +%F).dump`, encrypted and stored off-site.
- Test restores at least monthly (`pg_restore --clean --if-exists -d <scratch_db>`), then run the reconciliation endpoint against the restored copy.
- Redis holds only rate-limit counters, locks and caches. It needs no backup.

### 2.6 Logging, monitoring and error reporting

- Logs are structured JSON on stdout (`LOG_JSON=true`), with `request_id` and `path` bound per request and echoed back in `X-Request-ID`. Ship stdout to the log platform.
- Liveness: `GET /health`. Readiness: `GET /ready` returns 503 when PostgreSQL or Redis is unavailable.
- Alert on:
  - `webhook_processing_failed` log events, and on `failed_webhooks` in `GET /api/v1/admin/overview`;
  - `refresh_token_reuse_detected` (possible token theft);
  - `unhandled_error` (every 500 is logged with its stack trace);
  - reconciliation runs (`POST /api/v1/admin/reconciliation`) that report mismatches. Schedule at least one run per day.
- Error reporting: forward `unhandled_error` and `maintenance_failed` events to the error-tracking service (for example a log-based Sentry or Grafana alert). No third-party SDK is bundled, so no credentials are assumed.

### 2.7 Background work

Each application process runs a maintenance loop (`RUN_MAINTENANCE_LOOP=true`). It expires checkout inventory reservations and voids their pending payments, and it dispatches queued transactional emails. Rows are claimed with `SELECT … FOR UPDATE SKIP LOCKED`, so several processes can run it safely. No separate worker (Celery/ARQ) is required.

### 2.8 Release checklist

1. `ruff`, `mypy`, `alembic check` and `pytest` are green.
2. The provider items in [moyasar-verification.md §3](../architecture/moyasar-verification.md#3-re-verification-checklist-before-going-live) are complete.
3. A legal and regulatory review is done (PDPL, SAMA payment regulations, ZATCA VAT invoicing, e-commerce and consumer-protection rules). The platform's controls do not by themselves make it compliant. The approved Moyasar arrangement determines the actual fund flow. See [security.md](../architecture/security.md#saudi-regulatory-considerations).
4. Backups and restores are tested, and monitoring alerts are configured.
5. Create the first SUPER_ADMIN with `python -m app.cli create-admin --super`.
