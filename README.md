# Saudi Multi-Vendor Marketplace

A multi-vendor marketplace for Saudi Arabia (SAR, Arabic/English) with server-side commission calculation, split payments, an immutable double-entry ledger and verified merchant settlements.

- Product and architecture documentation: [`docs/`](docs/README.md) (delivery: [`docs/architecture/delivery-architecture.md`](docs/architecture/delivery-architecture.md))
- Backend (FastAPI + SQLModel): [`apps/backend`](apps/backend)
- Frontend (SvelteKit 3 + shadcn-svelte, Arabic RTL / English LTR): [`apps/frontend`](apps/frontend)

## Quick start (Docker Compose + make)

```bash
make up          # creates .env from .env.example if missing, builds and starts everything
make seed        # demo data (mock payments only)
make superuser   # create a SUPER_ADMIN (prompts for email, name and password)
```

- Frontend: http://localhost:5173 (SvelteKit dev server with HMR; proxies `/api/v1/*` and `/media/*` to the backend)
- API docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/health · Readiness: http://localhost:8000/ready

The stack is `postgres`, `redis`, a one-shot `migrate` (Alembic), `backend` (FastAPI, reloads on change) and `frontend`. Source code is bind-mounted, so edits apply without rebuilding. Run `make build` after changing dependencies.

| Command | What it does |
| --- | --- |
| `make up` / `make down` | Start the stack in the background / stop it (data is kept) |
| `make logs` / `make logs s=backend` | Follow the logs |
| `make migrate` | Apply migrations |
| `make seed` | Load the demo data |
| `make superuser` | Create a SUPER_ADMIN. Non-interactive: `make superuser EMAIL=ops@company.sa NAME="Ops"` (the password is read from `ADMIN_PASSWORD` or prompted for) |
| `make flush` | **Delete all data**: drops the `public` schema, re-applies every migration (roles, permissions and commission rules come back), and clears Redis. Asks you to type `flush`; `FORCE=1` skips the prompt |
| `make fresh` | `flush`, then `seed` |
| `make reset` | Remove the containers and **every volume** (database, Redis, uploads, node_modules) |
| `make psql` / `make redis-cli` | Open a database / Redis shell |

`flush` drops the schema instead of truncating the tables because the ledger and audit tables have triggers that block `TRUNCATE`, `UPDATE` and `DELETE`. Uploaded files in the `uploads` volume are kept; use `make reset` to remove them too.

Host ports are `5173`, `8000`, `55432` (Postgres) and `56379` (Redis). Override them with `FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT` and `REDIS_PORT` in `.env`. If you change `FRONTEND_PORT`, also change `FRONTEND_URL`.

Demo accounts created by `seed-dev` (password `demo-password-123`): `admin@example.com` (SUPER_ADMIN), `merchant@example.com` (approved store `najd-oud` with delivery zones and a pickup point), `customer@example.com`. The public API never creates administrators. Use `make superuser` for real ones.

## Local backend development (without Docker for the app)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13. PostgreSQL and Redis can come from Compose (`docker compose up -d postgres redis`).

```bash
cd apps/backend
uv sync
uv run alembic upgrade head
uv run fastapi dev            # entrypoint configured in pyproject.toml ([tool.fastapi])
```

Quality gates (run them all before merging):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run alembic check          # models and migrations are in sync
uv run pytest                 # creates and migrates a fresh <db>_test database
```

The test suite needs PostgreSQL and Redis (the financial guarantees rely on database constraints and triggers). Override the targets with `TEST_DATABASE_URL` and `TEST_REDIS_URL`.

## Frontend

Requires Node 24 and pnpm. The SvelteKit server proxies `/api/v1/*` and `/media/*` to the backend, so the browser only talks to the frontend origin.

```bash
cd apps/frontend
pnpm install
API_URL=http://localhost:8000 pnpm dev          # http://localhost:5173 (must match the backend FRONTEND_URL)
pnpm check && pnpm lint                          # svelte-check, prettier, eslint
API_URL=http://localhost:8000 pnpm test:e2e      # Playwright: checkout + Arabic (RTL) / English (LTR)
```

- UI components are [shadcn-svelte](https://shadcn-svelte.com) (`src/lib/components/ui`, added with the CLI, converted to logical RTL-safe classes); app components live in `src/lib/components/app`.
- Design tokens are in `src/routes/layout.css`; all copy is in `src/lib/i18n/messages/{en,ar}.ts` (the `Messages` type keeps both catalogues in sync).
- The end-to-end tests need the `seed-dev` demo data and the mock payment provider. They reuse a server already running on `E2E_PORT` (default 5173); otherwise they build and start one.
- After changing the API, regenerate the client types with `API_SCHEMA_URL=http://localhost:8000/api/openapi.json pnpm api:types`.

## Payments: mock vs. Moyasar

`PAYMENT_PROVIDER=mock` (the default) runs the whole flow (merchant onboarding, split payments, signed webhooks, refunds, settlements, chargebacks) with **no real money**. Mock payments are flagged `is_test` in the database and API, and the mock provider refuses to start when `ENVIRONMENT=production`.

`PAYMENT_PROVIDER=moyasar` requires an approved Moyasar for Platforms account. See [Moyasar verification](docs/architecture/moyasar-verification.md) for what is verified and what still needs provider approval.
