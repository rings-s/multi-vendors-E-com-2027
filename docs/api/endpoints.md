# API Design

Use versioned REST APIs.

Base path:

`/api/v1`

Suggested endpoint structure:

```text
/api/v1/auth
/api/v1/users

/api/v1/customers
/api/v1/customers/addresses

/api/v1/merchants
/api/v1/merchants/onboarding
/api/v1/merchants/payment-account

/api/v1/stores
/api/v1/categories

/api/v1/products
/api/v1/services

/api/v1/cart
/api/v1/checkout
/api/v1/checkout/quote

/api/v1/orders
/api/v1/orders/{order_id}

/api/v1/payments
/api/v1/payments/{payment_id}

/api/v1/webhooks/moyasar

/api/v1/merchant/dashboard
/api/v1/merchant/analytics?days=30            # dashboard charts, scoped to the merchant (days 7-365)
/api/v1/merchant/transactions
/api/v1/merchant/earnings
/api/v1/merchant/settlements
/api/v1/merchant/delivery/settings
/api/v1/merchant/delivery/zones
/api/v1/merchant/deliveries
/api/v1/merchant/orders/{merchant_order_id}/delivery/status

/api/v1/stores/{slug}/delivery

/api/v1/admin/overview
/api/v1/admin/analytics?days=30               # marketplace dashboard charts (days 7-365)
/api/v1/admin/merchants
/api/v1/admin/orders
/api/v1/admin/payments
/api/v1/admin/commissions
/api/v1/admin/settlements
/api/v1/admin/reconciliation
/api/v1/admin/settings

/api/v1/admin/data/models                      # every table (Django-admin-style data admin)
/api/v1/admin/data/models/{model}              # schema: fields, list columns, search, filters
/api/v1/admin/data/{model}                     # GET list (search, filters, ordering) / POST create
/api/v1/admin/data/{model}/{pk}                # GET / PATCH / DELETE one record
/api/v1/admin/data/{model}/lookup              # foreign-key picker search
/api/v1/admin/data/{model}/delete-preview      # cascades, unlinks and protected references
/api/v1/admin/data/{model}/bulk-delete         # atomic multi-delete
```

### Generic data admin (`/api/v1/admin/data/*`, UI at `/admin/data`)

Full CRUD for every table in `SQLModel.metadata`, modelled on the Django admin. Tables are
discovered automatically; per-table options (display label, list columns, search fields,
filters, ordering, hidden and read-only columns, choices, allowed actions) live in
`apps/backend/app/modules/admin/data/registry.py` (`CONFIG`).

- **Permissions:** `admin.data.view` (ADMIN, SUPER_ADMIN) to browse; `admin.data.manage`
  (SUPER_ADMIN only, grantable through `role_permissions`) to create, change and delete.
- **Filters** use Django-style lookups in the query string: `?status=PAID`,
  `?total__gte=1000`, `?paid_at__isnull=false`, `?id__in=a,b`, `?title__icontains=oud`.
  `q` searches the table's search fields (and any UUID column for a UUID term);
  `ordering=-created_at,number` sorts.
- **Composite keys** (`user_roles`, `role_permissions`, `store_categories`) are addressed as
  `{pk1},{pk2}` in the order of the key columns.
- **Database rules still apply.** Append-only tables (`ledger_entries`, `ledger_transactions`,
  `audit_logs`, `merchant_verifications`, `delivery_events`) are view-only; `ON DELETE RESTRICT`
  relations block deletes with `409 protected_relation`; unique, not-null, foreign-key and check
  violations come back as field-level `422` errors.
- **Secrets are never exposed:** `users.password_hash` and token hashes are hidden. Users get
  a write-only `password` field (hashed with Argon2; setting it revokes the user's sessions).
  Administrators cannot delete their own account.
- **Audit:** every write is logged as `data.create` / `data.update` / `data.delete` with the
  changed columns before and after; the change page shows this history.

Use:

- Pydantic request schemas.
- Pydantic response schemas.
- Consistent error responses.
- Pagination.
- Filtering.
- Sorting.
- API documentation.
- Proper HTTP status codes.

Avoid putting business logic inside API route handlers.

Delivery endpoints and payloads are described in [Delivery & Fulfillment Architecture §7](../architecture/delivery-architecture.md#7-api).

## Dashboard analytics

`GET /api/v1/admin/analytics` (permission `payments.view`) and `GET /api/v1/merchant/analytics`
(the signed-in merchant only) return the data behind the dashboard charts for the last `days`
calendar days in Asia/Riyadh, ending today, compared with the `days` before them:

- `kpis`: gross sales, orders, average and median order value (relative change in percent) and
  the refund rate (percentage of gross sales, change in points). `change_pct` is `null` when the
  previous period has nothing to compare with.
- `trend`: one point per day (empty days are 0) with a trailing 7-day moving average that
  already includes the previous period, and `slope_per_day`, the least-squares slope of daily
  gross sales in halalas per day.
- `weekdays`: average orders and sales per weekday, `0` = Sunday.
- `order_statuses`, `payment_methods` (top 3 + `OTHER` beyond four), `top_items` and, for the
  marketplace only, `top_merchants` (top 5 by gross sales).

SQL selects only the raw rows of the two periods; the aggregation is done with pandas and numpy
in `app/modules/analytics/service.py`. The frontend draws them with Chart.js
(`src/lib/charts`, `src/lib/components/app/charts`).
