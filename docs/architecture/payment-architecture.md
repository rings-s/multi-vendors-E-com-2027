# Payment Architecture

## 1. Payment onboarding

Use the payment provider's approved merchant onboarding mechanism.

For Moyasar, investigate the officially supported platform/sub-merchant onboarding API.

Collect or submit the information required by the provider:

- Merchant identity.
- Business information.
- Beneficiary information.
- IBAN.
- Required verification documents.
- Other required compliance information.

The payment provider should handle sensitive bank verification through its approved process.

Never store full bank credentials or unnecessary identity documents.

Store provider identifiers and onboarding status.

Example database fields:

- merchant_id
- provider
- provider_account_id
- recipient_id
- onboarding_status
- verification_status
- payout_status
- created_at
- updated_at

Support onboarding retries and provider status synchronization.

---

## 2. Payment system — highest priority

### 2.1 Business requirements

Implement a genuine marketplace payment architecture.

The platform must support:

- Customer payments.
- Merchant-specific payment allocations.
- Platform commission.
- Automatic split payments.
- Direct merchant settlement.
- Payment status synchronization.
- Refunds.
- Chargebacks.
- Settlement tracking.
- Financial reconciliation.

### 2.2 Payment provider architecture

Create a provider-independent interface.

Example:

```python
class PaymentProvider:
    async def create_payment(self, data):
        ...

    async def retrieve_payment(self, payment_id):
        ...

    async def create_merchant_account(self, data):
        ...

    async def get_merchant_account(self, account_id):
        ...

    async def create_split_payment(self, data):
        ...

    async def refund_payment(self, payment_id, amount=None):
        ...

    async def verify_webhook(self, request):
        ...

    async def get_settlement(self, settlement_id):
        ...
```

Implement:

- MoyasarProvider.
- MockPaymentProvider.

Keep provider-specific request and response schemas inside their respective adapters.

Do not spread Moyasar-specific logic throughout the application.

#### Important provider verification rule

Before implementing Moyasar integration:

1. Read the official Moyasar Platform API documentation.
2. Verify the current merchant onboarding endpoints.
3. Verify the current split-payment request schema.
4. Verify supported payment methods.
5. Verify recipient requirements.
6. Verify settlement behavior.
7. Verify refunds and chargeback behavior.
8. Verify webhook authentication.
9. Identify features requiring commercial approval.
10. Document anything unavailable or requiring provider authorization.

Official resources:

- https://moyasar.com/en/solutions/platforms-and-marketplaces/
- https://platform-docs.moyasar.com/
- https://platform-docs.moyasar.com/guides/splits

Never invent API endpoints, fields, authentication mechanisms, or payment capabilities.

If production marketplace access has not been granted, implement the adapter boundary and mock integration without pretending that production split payments are operational.

### 2.3 Commission management

The platform must support configurable commissions.

Examples:

- 5%.
- 10%.
- 15%.

Support:

- Global commission.
- Merchant-specific commission.
- Category-specific commission.
- Fixed commission where contractually supported.
- Effective dates.
- Commission history.

The commission must be calculated on the server.

Use Decimal for financial calculations and integer halalas when communicating amounts to payment APIs.

Never use floating-point arithmetic for money.

### 2.4 Payment allocation

Example:

Customer payment: 100 SAR.

Platform commission: 10%.

Seller proceeds: 90 SAR.

Payment allocations:

```json
{
  "currency": "SAR",
  "total_amount": 10000,
  "allocations": [
    {
      "recipient": "merchant",
      "amount": 9000
    },
    {
      "recipient": "platform",
      "amount": 1000
    }
  ]
}
```

This is an internal allocation representation, not a provider API request.

Enforce:

- Sum of allocations equals payable amount.
- No negative amounts.
- No duplicate allocations.
- Valid recipient IDs.
- Valid merchant status.
- Valid commission configuration.

Explicitly define whether payment-processing fees are paid by the platform or merchant.

Never silently deduct fees from the seller's proceeds.

Delivery charges are split explicitly as well: each allocation records its delivery part, and whether platform commission applies to delivery fees is an explicit platform setting. See [Delivery & Fulfillment Architecture §5](delivery-architecture.md#5-financial-model).

### 2.5 Payment lifecycle

Implement the following states:

- CREATED.
- PENDING.
- AUTHORIZED.
- PAID.
- FAILED.
- CANCELLED.
- PARTIALLY_REFUNDED.
- REFUNDED.
- DISPUTED.

Only verified payment confirmation can transition an order into its paid state.

### 2.6 Webhooks

Implement secure webhook endpoints.

Requirements:

- Verify provider signatures using the documented mechanism.
- Reject invalid events.
- Persist incoming event identifiers.
- Make processing idempotent.
- Handle duplicate events.
- Handle out-of-order events.
- Retry recoverable processing failures.
- Log processing errors.
- Never trust browser redirects as proof of payment.

### 2.7 Refunds

Support:

- Full refunds.
- Partial refunds.
- Merchant cancellation.
- Platform-initiated refunds.
- Refund status tracking.

The refund process must account for the original split allocation.

Do not assume that reversing the original payment automatically reverses every recipient's allocation.

Verify the provider's actual refund and recovery behavior.

---

## 3. Financial ledger

Build a proper financial ledger.

Do not use a simple merchant balance field as the source of truth.

Use immutable financial entries with corrections represented through reversing entries.

### Suggested entities

#### MerchantLedgerAccount

- id
- merchant_id
- currency
- account_type
- created_at

#### LedgerTransaction

- id
- reference
- transaction_type
- source_type
- source_id
- status
- created_at

#### LedgerEntry

- id
- transaction_id
- account_id
- direction
- amount
- currency
- description
- created_at

#### CommissionTransaction

- id
- order_id
- merchant_id
- gross_amount
- commission_rate
- commission_amount
- processing_fee
- seller_net_amount

#### Settlement

- id
- merchant_id
- provider_settlement_id
- amount
- currency
- status
- initiated_at
- completed_at
- failure_reason

### Financial requirements

Support:

- Total sales.
- Gross transaction amount.
- Platform commission.
- Payment fees.
- Refunds.
- Chargebacks.
- Merchant net earnings.
- Pending settlement.
- Completed settlement.
- Settlement failures.

The ledger must be reconcilable with provider records.

Never mark a settlement completed simply because a payment succeeded.

Payment success and bank settlement are separate events.
