# Saudi Multi-Vendor Marketplace — Documentation

## Documentation index

| Document | Contents |
| --- | --- |
| [product/overview.md](product/overview.md) | Product overview, business model, geographic scope, product scope |
| [product/requirements.md](product/requirements.md) | Customer application, merchant registration and onboarding, merchant dashboard, administration dashboard, frontend design system, internationalization, notifications, testing |
| [architecture/system-architecture.md](architecture/system-architecture.md) | Technology stack, application architecture, repository structure |
| [architecture/database.md](architecture/database.md) | Database design |
| [architecture/payment-architecture.md](architecture/payment-architecture.md) | Payment onboarding, payment system, financial ledger |
| [architecture/delivery-architecture.md](architecture/delivery-architecture.md) | Delivery & fulfillment: zones, fees, pickup, delivery lifecycle, delivery money in splits, ledger, refunds and reconciliation, provider interface |
| [architecture/moyasar-verification.md](architecture/moyasar-verification.md) | Verified Moyasar behaviour, outstanding provider approvals and dependencies |
| [architecture/security.md](architecture/security.md) | Authentication and authorization, security and compliance |
| [api/endpoints.md](api/endpoints.md) | API design |
| [operations/deployment.md](operations/deployment.md) | Development environment, deployment |

---

## 1. Role

Act as a Principal Software Architect, Senior Python/FastAPI Engineer, Senior SvelteKit Engineer, Payment Systems Architect, Database Engineer, and Product Designer.

Your mission is to design, engineer, test, and deliver a complete production-oriented multi-vendor marketplace application for the Saudi Arabian market.

Do not build a prototype, a static dashboard, or a collection of disconnected pages.

Build a functional marketplace where:

- Customers discover stores and purchase products or services.
- Store owners register and manage their businesses.
- Independent merchants receive their earnings directly into their own registered bank accounts.
- The platform automatically collects a configurable commission.
- Payments are processed through a marketplace-compatible payment provider.
- Administrators manage the entire marketplace.

The primary payment provider is **Moyasar for Platforms**, subject to marketplace approval and API availability.

The application must be architected so another marketplace-compatible payment provider can be integrated without rewriting the business logic.

---

## 2. Implementation roadmap

Do not attempt to build the entire system in one uncontrolled code-generation pass.

Work in phases.

### Phase 1 — Foundation

- Inspect the repository.
- Establish architecture.
- Configure FastAPI.
- Configure SvelteKit.
- Configure PostgreSQL.
- Configure Redis.
- Configure Docker.
- Establish migrations.
- Establish design tokens.
- Establish authentication.
- Create project documentation.

Deliverable: Working application foundation.

### Phase 2 — Identity and merchants

- Customer registration.
- Merchant registration.
- Role-based authorization.
- Merchant profiles.
- Store management.
- Verification workflows.
- Payment onboarding abstractions.

Deliverable: Customers and merchants can register and manage their accounts.

### Phase 3 — Marketplace

- Categories.
- Products.
- Services.
- Storefronts.
- Search.
- Shopping cart.
- Inventory.
- Customer addresses.

Deliverable: Customers can discover stores and build carts.

### Phase 4 — Orders and payments

- Checkout.
- Order creation.
- Merchant order allocation.
- Commission calculation.
- Payment provider interface.
- Mock payment integration.
- Moyasar integration based on verified documentation.
- Payment splitting.
- Webhooks.

Deliverable: End-to-end payment flow in sandbox or mock mode.

### Phase 5 — Financial system

- Immutable ledger.
- Merchant earnings.
- Commission records.
- Payment allocation records.
- Settlement records.
- Refunds.
- Chargebacks.
- Reconciliation.

Deliverable: Reliable financial accounting and seller settlement visibility.

### Phase 6 — Dashboards

- Customer account.
- Merchant dashboard.
- Financial dashboard.
- Admin dashboard.
- Merchant management.
- Platform configuration.

Deliverable: All user roles can manage their respective operations.

### Phase 7 — Quality and security

- Automated tests.
- Integration tests.
- End-to-end tests.
- Payment security review.
- Merchant isolation review.
- Performance optimization.
- Accessibility.
- Arabic and English validation.

Deliverable: Release candidate.

### Phase 8 — Deployment

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

---

## 3. Important engineering rules

Follow these rules throughout development.

1. Never fabricate payment-provider API functionality.
2. Never assume Moyasar marketplace approval.
3. Never process real money using mock payment code.
4. Never trust frontend payment status.
5. Never calculate financial allocations exclusively on the frontend.
6. Never store sensitive payment credentials.
7. Never expose provider secret keys to SvelteKit.
8. Never allow merchants to access another merchant's information.
9. Never treat successful payment as completed bank settlement.
10. Never silently change commission rates on existing orders.
11. Never delete financial ledger entries.
12. Never implement fake settlement or withdrawal buttons.
13. Never hardcode dashboard statistics.
14. Never leave critical features as nonfunctional placeholders.
15. Never create excessive abstraction layers.
16. Never sacrifice financial correctness for implementation speed.

If a feature requires provider approval, external credentials, or legal authorization, document the dependency and implement a safe development alternative.

---

## 4. Execution instructions

You are responsible for actually building this application, not merely describing how it should be built.

Start by:

1. Inspecting the existing repository.
2. Identifying existing files and technologies.
3. Identifying reusable components.
4. Checking existing conventions.
5. Preparing a concise implementation plan.
6. Creating or updating the necessary documentation.
7. Implementing the application incrementally.

Before creating new files, inspect the existing project structure.

Do not unnecessarily overwrite working code.

After every implementation phase:

- Run relevant tests.
- Run type checking.
- Run linting.
- Run database migration checks.
- Resolve errors before continuing.
- Update documentation.
- Report completed work and remaining dependencies.

Do not claim a feature is complete unless its actual functionality exists and has been tested.

### Working methodology

Work as an autonomous senior engineering team.

You may use specialized agents for:

- Backend architecture.
- Frontend implementation.
- Payment integration.
- Database engineering.
- Security review.
- Testing.
- Technical documentation.

However, maintain one consistent architecture and one source of truth.

Do not let agents independently invent incompatible APIs or database schemas.

The principal architect is responsible for reviewing integration boundaries.

### Completion criteria

The project is not complete until:

- Customers can register and browse the marketplace.
- Merchants can register and manage stores.
- Administrators can approve merchants.
- Merchants can complete the supported payment onboarding flow.
- Customers can create orders.
- The backend calculates platform commissions.
- Payment allocations are correct.
- The payment provider integration follows verified documentation.
- The financial ledger is consistent.
- Webhooks are secure and idempotent.
- Seller settlement information is visible.
- Refunds are handled correctly.
- Arabic and English work properly.
- All critical workflows have automated tests.
- The application can run locally using Docker Compose.
- Production dependencies and outstanding provider approvals are documented.

### Backend completion status

Status of the backend (`apps/backend`) against the completion criteria above. Every row is covered by automated tests in `apps/backend/tests`, run against real PostgreSQL and Redis.

| Criterion | Backend implementation | Tests |
| --- | --- | --- |
| Customers can register and browse | `/auth/register`, `/stores`, `/categories`, `/products`, `/services`, `/homepage` (admin-configurable) | `test_auth`, `test_catalog_cart_checkout`, `test_operations` |
| Merchants can register and manage stores | `/merchants/register`, `/merchants/onboarding`, `/merchant/store`, `/merchant/products`, `/merchant/services`, `/merchant/inventory` | `test_merchants`, `test_catalog_cart_checkout`, `test_operations` |
| Administrators can approve merchants | `/admin/merchants/{id}/{action}`, verification history, audit log | `test_merchants` |
| Supported payment onboarding flow | `/merchants/payment-account` (start, submit, sync), provider webhooks, document requirements | `test_merchants`, `test_operations`, `test_moyasar_adapter` |
| Customers can create orders | `/cart`, `/checkout` (idempotent, one checkout group per merchant), `/orders` | `test_catalog_cart_checkout` |
| Backend calculates commissions | Global, merchant, category, fixed and percentage rules with effective dates; rates frozen per order | `test_payments`, `test_unit_money` |
| Payment allocations are correct | Allocation invariants, explicit fee bearer | `test_payments`, `test_unit_money` |
| Provider integration follows verified docs | [moyasar-verification.md](architecture/moyasar-verification.md) | `test_moyasar_adapter` |
| Financial ledger is consistent | Double-entry, DB-enforced balance and immutability | `test_payments`, `test_refunds_settlements` |
| Webhooks are secure and idempotent | Signature/secret verification, event de-duplication, monotonic state, retryable failures | `test_payments` |
| Seller settlement information is visible | `/merchant/earnings`, `/merchant/settlements`, `/admin/settlements` | `test_refunds_settlements` |
| Delivery & fulfillment | Merchant delivery zones and pickup, delivery fees and statuses, explicit delivery commission policy, componentized splits/ledger/refunds/reconciliation ([delivery-architecture.md](architecture/delivery-architecture.md)) | `test_delivery` |
| Refunds are handled correctly | Full, partial, merchant/admin/customer-initiated; split-aware reversal | `test_refunds_settlements`, `test_operations` |
| Administrators manage every table | Django-admin-style CRUD for all tables at `/admin/data` (`/admin/data/*` API): search, filters, sorting, FK pickers, delete previews, bulk delete, audit history; append-only and financial tables protected | `test_admin_data` |
| Arabic and English | Localised notifications and emails, persisted language preference, stable error codes | `test_admin_i18n` |
| Critical workflows have automated tests | 163 backend tests | `uv run pytest` |
| Runs locally with Docker Compose | `docker-compose.yml`, `apps/backend/Dockerfile`, `.env.example`, `python -m app.cli seed-dev` | Image built and booted |
| Dependencies and approvals documented | [moyasar-verification.md §2](architecture/moyasar-verification.md#2-not-verified-or-requiring-moyasar-approval), [deployment.md](operations/deployment.md) | — |

Outside the backend:

- **Provider approvals.** Marketplace approval, split enablement, the fee schedule and the platform recipient id come from Moyasar. Per engineering rule 3 and the "safe development alternative" rule, the mock provider covers development and tests until then.
- **The SvelteKit frontend (`apps/frontend`).** It is a separate deliverable that consumes this API (`/api/docs`).

---

**Final instruction: Build a real, maintainable, secure Saudi multi-vendor marketplace with automatic split payments and direct merchant settlements. Prioritize financial correctness, marketplace isolation, and a functional customer/merchant/admin experience over unnecessary features or architectural complexity.**
