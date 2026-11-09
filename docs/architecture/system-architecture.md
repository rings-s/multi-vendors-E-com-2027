# System Architecture

## 1. Technology stack

Use the following technology stack.

### Backend

- Python 3.13+
- FastAPI
- Pydantic v2
- SQLModel for table models, sessions and queries (built on SQLAlchemy 2.x; SQLAlchemy is used directly only for what SQLModel does not wrap, see [Database Design](database.md#orm-conventions-sqlmodel))
- Alembic
- PostgreSQL
- Redis
- Celery or ARQ only where background processing genuinely requires it.
- HTTPX for external API communication.
- Asyncer to run unavoidable blocking work (Argon2 hashing, file writes, SMTP) in worker threads from async code.
- JWT authentication.
- Argon2 password hashing.

Use asynchronous database and HTTP operations where appropriate.

### Frontend

- SvelteKit latest stable.
- Svelte 5.
- TypeScript.
- Tailwind CSS.
- shadcn-svelte or compatible accessible component primitives.
- Zod for frontend validation where useful.
- Server-side rendering where appropriate.
- Progressive Web App capabilities.

Use Svelte 5 runes and modern SvelteKit conventions.

Do not use React, Next.js, or Vue.

### Infrastructure

- PostgreSQL as the primary database.
- Redis for caching, temporary reservations, and background task coordination.
- Docker and Docker Compose.
- Cloudflare-compatible deployment architecture.
- Environment-based configuration.
- Structured logging.
- Automated database migrations.

### Engineering principles

- Pragmatic Domain-Driven Design.
- Modular monolith architecture.
- SOLID principles.
- Explicit service boundaries.
- Dependency injection.
- Strong typing.
- Database constraints.
- Transactional integrity.
- Idempotent operations.
- Secure-by-default design.

Avoid microservices.

Avoid unnecessary abstractions and excessive architectural complexity.

---

## 2. Application architecture

Build three primary application interfaces.

### A. Customer application

Public marketplace and customer account.

Responsibilities:

- Discover stores.
- Browse categories.
- Search products and services.
- View merchant storefronts.
- View product/service details.
- Add products to cart.
- Checkout.
- Pay securely.
- Track orders.
- Manage profile and addresses.
- View order history.
- Submit reviews.

### B. Merchant application

Dedicated merchant dashboard.

Responsibilities:

- Merchant registration.
- Business verification.
- Store management.
- Catalog management.
- Inventory management.
- Order fulfillment.
- Financial management.
- Payment onboarding.
- Settlement tracking.
- Customer management.
- Store analytics.

### C. Platform administration

Dedicated administrative dashboard.

Responsibilities:

- Marketplace management.
- Merchant approvals.
- Merchant suspension.
- Customer management.
- Product moderation.
- Order monitoring.
- Commission configuration.
- Payment monitoring.
- Financial reconciliation.
- Refund management.
- Dispute management.
- System configuration.
- Audit logs.

All three interfaces must use the same backend and shared business rules.

---

## 3. Repository structure

Use a monorepo.

```text
marketplace/
│
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── modules/
│   │   │   │   ├── auth/
│   │   │   │   ├── users/
│   │   │   │   ├── customers/
│   │   │   │   ├── merchants/
│   │   │   │   ├── stores/
│   │   │   │   ├── catalog/
│   │   │   │   ├── cart/
│   │   │   │   ├── orders/
│   │   │   │   ├── payments/
│   │   │   │   ├── commissions/
│   │   │   │   ├── ledger/
│   │   │   │   ├── settlements/
│   │   │   │   ├── notifications/
│   │   │   │   └── admin/
│   │   │   ├── infrastructure/
│   │   │   ├── integrations/
│   │   │   │   └── payments/
│   │   │   ├── database/
│   │   │   └── main.py
│   │   ├── migrations/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   └── frontend/
│       ├── src/
│       │   ├── lib/
│       │   │   ├── components/
│       │   │   ├── features/
│       │   │   ├── services/
│       │   │   ├── stores/
│       │   │   ├── types/
│       │   │   └── i18n/
│       │   ├── routes/
│       │   │   ├── (marketplace)/
│       │   │   ├── (customer)/
│       │   │   ├── merchant/
│       │   │   └── admin/
│       │   └── app.css
│       ├── package.json
│       └── Dockerfile
│
├── docs/
│   ├── README.md
│   ├── product/
│   │   ├── overview.md
│   │   └── requirements.md
│   ├── architecture/
│   │   ├── system-architecture.md
│   │   ├── database.md
│   │   ├── payment-architecture.md
│   │   └── security.md
│   ├── api/
│   │   └── endpoints.md
│   └── operations/
│       └── deployment.md
│
├── docker-compose.yml
├── .env.example
└── README.md
```

You may refine the structure if necessary, but preserve clear domain boundaries.
