# Moyasar Integration — Verification Record

This record follows the provider verification rule in
[payment-architecture.md §2.2](payment-architecture.md#22-payment-provider-architecture).
The adapter (`apps/backend/app/integrations/payments/moyasar.py`) only implements behaviour listed
as **verified** below. Anything else is refused with `ProviderCapabilityUnavailable` (HTTP 503) or
stored for manual reconciliation.

Last checked against the official documentation: **2026-11-08**.

Sources:

- https://platform-docs.moyasar.com/ (introduction, live/test key prefixes)
- https://platform-docs.moyasar.com/api/authentication
- https://platform-docs.moyasar.com/guides/managing-merchants/overview
- https://platform-docs.moyasar.com/guides/managing-merchants/define-fees
- https://platform-docs.moyasar.com/guides/splits
- https://platform-docs.moyasar.com/guides/webhooks

## 1. Verified behaviour

| Area | Verified behaviour | Adapter |
| --- | --- | --- |
| Platform API base and auth | `https://apimig.moyasar.com/v1`, HTTP Basic with the **platform API key** as the username and an empty password. | `MOYASAR_PLATFORM_API_BASE`, `MOYASAR_PLATFORM_API_KEY` |
| Merchant creation | `POST /merchants` with `type`, `admin_email`, `owners_count`, `signatory` (`owner`, `commercial_contract`, `power_of_attorney`), `signatory_count` (only for the latter two), `activity_license_required`, `name`, `public_name`, `country`, `time_zone`, `website`, `email`, `enabled_schemes` (`mada`, `visa`, `master`), `fees`. | `create_merchant_account` |
| Fees object | `mada_charge_rate`, `mada_charge_fixed`, `mada_refund_fixed`, `cc_charge_rate`, `cc_charge_fixed`, `cc_refund_fixed` are required; `stcpay_*` only when STC Pay is enabled. | `MOYASAR_MERCHANT_FEES` (JSON). This is the commercial agreement with Moyasar, so it is **configuration only**. Onboarding is refused while it is unset. |
| Key prefixes | Live keys start with `pk_live_` / `sk_live_`, test keys with `pk_test_` / `sk_test_`. | `MOYASAR_LIVE` must match. Webhooks whose `live` flag differs are rejected. |
| Split payments | `splits[]` with `recipient_id` (entity id, or the platform id), `amount` (minor units), optional `reference`, `description`, `fee_source`, `refundable`. Split totals must equal the payment amount. Zero or one `fee_source`; when none is given the merchant's highest split pays the fee. Entity splits cannot be negative. | `create_split_payment`. One merchant per payment. A fee source is always sent explicitly, so fees are never silently taken from the seller. Splits sent are always positive. |
| Split enablement | Splitting is off by default. It is available only to selected partners, enabled through the account manager, for aggregation clients only. Splits on sources Moyasar does not aggregate are ignored. | `MOYASAR_SPLITS_ENABLED=false` by default. Payments are refused until it is switched on. |
| Split refunds | By default every split is reversed on refund or void. `refundable: false` blocks that split's refund, and the remainder is then taken from the merchant account. Voids always reverse every split. | Splits are sent `refundable: true`. The ledger reverses allocations proportionally and cumulatively (`payments/refunds.py`). |
| Split settlement | Funds go from the gateway directly to each recipient. The processing fee (plus VAT) is deducted from the fee-source split after payment. | Fee posted to the fee bearer's ledger account (`PROCESSING_FEES` or the merchant payable). |
| Webhook envelope | `{id, type, created_at, secret_token, account_name, live, data}`, plus headers `X-Event-ID`, `X-Event-Type`, `X-Event-Attempt-Number`, `X-Event-Secret`. | `verify_webhook` |
| Webhook authenticity | A shared secret in `secret_token` or `X-Event-Secret`. **No HMAC or signature scheme is documented.** | Constant-time comparison against `MOYASAR_WEBHOOK_SECRET` / `MOYASAR_PLATFORM_WEBHOOK_SECRET`. The secret is stripped before the event is stored. Payment state is always re-fetched from the API, never taken from the webhook body. |
| Webhook retries | Five attempts in total, with delays of 60 s, 600 s, 1800 s and 3600 s. Any non-2xx response counts as a failure. Timeouts: 10 s connect, 5 s write, 10 s read. | Recoverable processing failures return 5xx so Moyasar retries. Events are idempotent on `(provider, event_id)`. Admins can reprocess `FAILED` events. |
| Merchant events | `merchant_created`, `merchant_updated`, `merchant_semi_activated`, `merchant_activated`, `merchant_un_hold`, `merchant_review_failed`, `merchant_disabled`, `merchant_hold`, `merchant_rejected`, `merchant_contract_generated`. | The account is re-synchronised with `GET /merchants/:id`. |
| Payments API | `POST /payments` (`given_id`, `amount`, `currency`, `description`, `callback_url`, `source`, `metadata`), `GET /payments/:id`, `POST /payments/:id/refund` with an optional `amount`. HTTP Basic with the secret key. | Raw `creditcard` sources are rejected: card data must be tokenised client-side with the publishable key. |

## 2. Not verified, or requiring Moyasar approval

| Item | Status | Safe development alternative |
| --- | --- | --- |
| Marketplace (platform) account approval | **Requires commercial approval** from Moyasar. Not assumed. | The mock provider (`PAYMENT_PROVIDER=mock`), which refuses to start in production. |
| Payment splitting | **Requires Moyasar to enable it** for the platform. | `MOYASAR_SPLITS_ENABLED=false`. Checkout payments fail with 503 until it is enabled. |
| Merchant fee schedule | **Contractual.** Values are agreed with Moyasar. | `MOYASAR_MERCHANT_FEES` must be set before onboarding. |
| Platform recipient id | Issued by Moyasar. | `MOYASAR_PLATFORM_RECIPIENT_ID`. Payments are refused while it is unset. |
| Settlement / transfer lookup API | Not documented in the sources above. `balance_transferred` and `merchant_balance_transferred` webhooks exist, but their `data` schema is not documented. | Events are stored as `IGNORED` and never applied automatically. A super-admin records settlements from Moyasar settlement files (`POST /admin/settlements/reconciled`, audited). |
| Chargeback / dispute API and events | Not documented. | Chargebacks are recorded by administrators (`POST /admin/chargebacks`). The mock provider simulates provider events. |
| IBAN / beneficiary submission and document upload | The Documents API exists (Document Types guide), but the document-type mapping was not verified for this release. | Only a masked IBAN reference is stored. Bank verification happens in Moyasar's onboarding (documents and Nafath signing) through the merchant dashboard invite sent to `admin_email`. Documents the provider still requires (`required_documents`) are mirrored as `MerchantDocumentReference` rows (`REQUIRED` → `SATISFIED`) and shown in `GET /merchants/payment-account`. No files are stored by the platform. |
| `semi_active` meaning | Not documented. | Treated as not yet able to accept payments. |
| Maximum recipients per payment | Not documented. | One merchant per payment ("checkout groups"). |

## 3. Re-verification checklist (before going live)

1. Confirm the platform agreement and that splitting is enabled.
2. Obtain the platform recipient id, platform API key, secret key and webhook secrets.
3. Configure `MOYASAR_MERCHANT_FEES` with the agreed schedule.
4. Confirm the webhook secret mechanism with Moyasar (no signature scheme is documented).
5. Confirm refund recovery behaviour for platform splits on partial refunds.
6. Obtain the settlement-file format and the `balance_transferred` payload, so settlement ingestion can be automated.
7. Run a sandbox payment end to end with `PAYMENT_PROVIDER=moyasar` and `MOYASAR_LIVE=false`.
