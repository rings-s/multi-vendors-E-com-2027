# Delivery & Fulfillment Architecture

Delivery is a first-class module (`apps/backend/app/modules/delivery`). It owns where a store
delivers, what delivery costs, how a physical merchant order reaches the customer and how
delivery money is split, recorded and reconciled. The order domain only stores a
provider-independent financial snapshot. It never depends on a specific delivery provider.

## 1. Scope

### MVP (implemented)

| Capability | Implementation |
| --- | --- |
| Merchant-managed delivery and customer pickup | `DeliveryMethod.DELIVERY` / `PICKUP`, both fulfilled by the `merchant` provider (`providers/merchant.py`) |
| Zones, fixed fees, free-delivery thresholds, delivery times | `DeliveryZone` (nationwide / region / cities / districts, `fee`, `free_delivery_threshold`, `eta_min_minutes`–`eta_max_minutes`) and `StoreDeliverySettings` (methods offered, pickup preparation time, policy) |
| Address, district, coordinates, instructions | `CustomerAddress.latitude/longitude/delivery_instructions`; snapshotted on `Delivery.address/latitude/longitude/instructions` at checkout |
| Fulfillment statuses | `PENDING, CONFIRMED, PREPARING, READY_FOR_PICKUP, OUT_FOR_DELIVERY, DELIVERED, FAILED, CANCELLED` (`Delivery.status`) with an append-only `DeliveryEvent` timeline |
| Merchant manages progress | `POST /merchant/orders/{id}/delivery/status`, queue at `GET /merchant/deliveries`, dashboard pages `/merchant/deliveries`, `/merchant/delivery`, `/merchant/orders/{id}` |
| Fee calculated independently | `delivery/pricing.py` (pure): zone matching and threshold only; commission is applied separately and explicitly |
| Fees in checkout, totals, payments, reconciliation | Quote and checkout (`delivery_fee`, `delivery_vat`), `Order.delivery_total`, `PaymentAllocation.delivery_amount`, componentized ledger, `check_delivery` in reconciliation |
| Who bears cost / receives fees | `MerchantOrder.delivery_fee_recipient` and `delivery_cost_bearer`, defined by the provider's `DeliveryTerms` |

### Explicitly not implemented

There is no live tracking, no drivers, no driver dashboard, no OTP proof of delivery and no
third-party courier API. These are not simulated anywhere. Statuses change only when an
authenticated merchant (or the system, on cancellation) changes them. The provider
interface reports these capabilities as `False`, so they are not offered in the API or
the UI.

## 2. Domain model

```
StoreDeliverySettings 1─1 Store ─1─* DeliveryZone
MerchantOrder 1─0..1 Delivery 1─* DeliveryEvent (append-only, DB trigger)
Delivery ─▶ DeliveryZone (snapshot: zone_name, ETA)   ─▶ MerchantAddress (pickup snapshot)
```

* **Configuration** (`store_delivery_settings`, `delivery_zones`) only affects future
  checkouts. Every order keeps its own snapshot, so editing or deleting a zone, or changing
  the platform's delivery-commission setting, never changes an existing order.
* **`Delivery`** is created at checkout for every merchant order that contains items needing
  delivery. Service-only merchant orders have `delivery_method = NONE` and no delivery.
* **Money lives on the merchant order** (see §5). The `Delivery` row holds operational data
  only: method, provider key, status, address/pickup snapshot, coordinates, instructions,
  ETA, estimated window, attempts, failure reason and timestamps.

## 3. Pricing and zone matching

1. Each store offers `DELIVERY` (enabled and at least one active zone) and/or `PICKUP`
   (enabled and at least one location marked `is_pickup_location`).
2. A zone covers all of Saudi Arabia (`region = NULL`), a region, listed cities of that
   region, or listed districts of those cities. The **most specific** active match applies
   (district > city > region > nationwide). Ties are broken by lower fee, then faster ETA,
   then name and id, so the outcome is deterministic.
3. Place names are compared after normalization (NFKC, case folding, Arabic letter variants
   unified, punctuation removed). Merchants list every spelling they accept, e.g.
   `["Riyadh", "الرياض"]`.
4. `fee = 0` when the item value after discounts reaches the zone's
   `free_delivery_threshold`. The waived amount is recorded as `delivery_fee_waived` and
   borne by the cost bearer.
5. VAT on the delivery fee is charged by the fee recipient: a VAT-registered merchant when
   the merchant receives it (and `tax.vat_applies_to_shipping` is on), or the platform when it
   receives it. VAT on items and on delivery is rounded separately, so
   `vat_total = items_vat + delivery_vat`.

The cart is priced against the customer's default address. `POST /checkout/quote` accepts
`{address_id, deliveries:[{store_id, method, pickup_location_id}]}`, and
`POST /checkout` accepts the same fields plus `delivery_instructions`. Without a choice,
each store defaults to delivery when offered, otherwise pickup. A store with
several pickup points requires the customer to choose one. Unavailable choices block
checkout with explicit issue codes: `delivery_not_offered`,
`address_outside_delivery_zones`, `pickup_not_offered`, `pickup_location_required`,
`invalid_pickup_location`. A missing address returns `address_required`.

## 4. Lifecycle

Manual transitions come from the provider (`manual_transitions`). The merchant-managed
provider allows:

| From | Delivery | Pickup |
| --- | --- | --- |
| PENDING | CONFIRMED (only once paid) | CONFIRMED (only once paid) |
| CONFIRMED | PREPARING, OUT_FOR_DELIVERY | PREPARING, READY_FOR_PICKUP |
| PREPARING | OUT_FOR_DELIVERY | READY_FOR_PICKUP |
| OUT_FOR_DELIVERY | DELIVERED, FAILED (reason required) | — |
| READY_FOR_PICKUP | — | DELIVERED (collected), FAILED (not collected) |
| FAILED | OUT_FOR_DELIVERY (new attempt) | READY_FOR_PICKUP |

The merchant order status follows the delivery: CONFIRMED→ACCEPTED,
PREPARING/READY_FOR_PICKUP→PROCESSING, OUT_FOR_DELIVERY→SHIPPED, DELIVERED→DELIVERED.
Cancelling, rejecting or fully refunding the order cancels a delivery that has not been delivered.
A FAILED delivery can be cancelled by the merchant with a full refund even after
dispatch. While a customer cancellation request is pending, the delivery cannot progress.
Confirming sets the promised window (`estimated_earliest_at` / `estimated_latest_at`).
Every change records a `DeliveryEvent` and notifies the customer
(`delivery_status_changed`, localized). The legacy `POST /merchant/orders/{id}/fulfillment`
endpoint drives the same state machine for orders that have a delivery.

## 5. Financial model

### 5.1 Configuration (explicit)

Platform setting `delivery` (`PUT /admin/settings/delivery`, super-admin, audited):

```json
{ "commission_applies_to": "ITEMS_ONLY" | "ITEMS_AND_DELIVERY", "delivery_commission_rate": "0" }
```

`ITEMS_ONLY` (default) requires a rate of 0. `ITEMS_AND_DELIVERY` requires a rate above 0.
Delivery commission is charged only on fees the merchant receives, excluding VAT, and is
always reported separately from item commission. The rate is snapshotted on the order.

### 5.2 Merchant order snapshot

| Column | Meaning |
| --- | --- |
| `delivery_method` | NONE / DELIVERY / PICKUP |
| `delivery_fee` | fee charged, excl. VAT |
| `delivery_fee_waived` | fee waived by a free-delivery threshold (borne by the cost bearer) |
| `delivery_vat` | VAT on the fee (part of `vat_total`) |
| `delivery_fee_recipient` | MERCHANT / PLATFORM (NULL iff NONE) |
| `delivery_cost_bearer` | MERCHANT / PLATFORM / CUSTOMER (NULL iff NONE) |
| `commission_total` | item commission only |
| `delivery_commission`, `delivery_commission_rate` | commission on the delivery fee |
| `merchant_net` | `total − commission_total − delivery_commission − (delivery_fee + delivery_vat if the platform receives the fee)` |

Database check constraints enforce these identities. They also enforce that only DELIVERY
carries a fee, that terms are recorded for every delivered or picked-up order, and that a
platform-received fee never also carries a delivery commission. `CommissionTransaction`
mirrors the snapshot (`delivery_fee`, `delivery_commission_amount`,
`platform_delivery_amount`) in its `seller_net_amount` identity.

### 5.3 Payment split

Provider splits are still one merchant and one platform recipient per payment. Each
`PaymentAllocation` records the part of its amount that comes from delivery:

* merchant: `amount = total − platform amount`, `delivery_amount = merchant delivery share`;
* platform: `amount = item commission + platform delivery share`,
  `delivery_amount = delivery commission` (or the whole delivery charge in a
  platform-received model).

### 5.4 Ledger

New platform accounts: `DELIVERY_COMMISSION` and `DELIVERY_FEE_REVENUE`. Entries tied to a
sale carry `component = GOODS | DELIVERY`, so delivery money stays identifiable inside the
merchant's single payable account:

```
PAYMENT_CAPTURED  Dr PROVIDER_CLEARING                 total
                  Cr MERCHANT_PAYABLE      [GOODS]      merchant items share
                  Cr MERCHANT_PAYABLE      [DELIVERY]   merchant delivery share
                  Cr PLATFORM_COMMISSION   [GOODS]      item commission
                  Cr DELIVERY_COMMISSION   [DELIVERY]   delivery commission
                    (or DELIVERY_FEE_REVENUE when the platform receives the fee)
REFUND/CHARGEBACK the same lines reversed for the refunded part of each component
```

### 5.5 Refunds, chargebacks and adjustments

Refunds have a `scope`:

* `AUTO`: items first, then the delivery charge. A full refund covers both.
* `ITEMS`: items only.
* `DELIVERY`: the delivery charge only, e.g. for a failed or late delivery.

Each refund or lost chargeback records `delivery_portion` and `delivery_platform_portion`.
Within each component the platform/merchant reversal is proportional and cumulative
(no rounding drift), so a full refund reverses every allocation exactly. Without a delivery
charge the result is identical to the original single-component calculation.

### 5.6 Settlement and reconciliation

Settlement is unchanged: the merchant's pending settlement is its `MERCHANT_PAYABLE` balance,
which includes only the merchant's delivery share. A platform-received fee or a delivery
commission never reaches it. `check_ledger` (run by every reconciliation) adds
`check_delivery`:

* each merchant's `MERCHANT_PAYABLE[DELIVERY]` balance = its delivery allocations − reversals;
* platform `DELIVERY_COMMISSION + DELIVERY_FEE_REVENUE` = platform delivery allocations − reversals;
* every captured payment's delivery allocations match its merchant order's delivery terms.

The merchant financial summary reports `product_sales`, `delivery_charges`,
`platform_commission` (items), `platform_delivery_share`, `delivery_refunds` and
`delivery_earnings` separately.

## 6. Provider-independent interface

```python
class DeliveryProvider(ABC):
    key: str                                   # stored on Delivery.provider
    methods: frozenset[DeliveryMethod]
    capabilities: ProviderCapabilities         # manual_status_updates, driver_assignment,
                                               # live_tracking, proof_of_delivery, status_webhooks
    def terms(self, method) -> DeliveryTerms   # fee recipient + cost bearer
    async def quote(self, request) -> DeliveryQuote
    def manual_transitions(self, method)       # statuses a merchant may set by hand
    async def on_confirmed(self, delivery)     # e.g. book a courier
    async def on_cancelled(self, delivery)     # e.g. cancel a booking
```

The registry (`providers/registry.py`) picks the provider for a method. The MVP registers
only `merchant`.

### Future extensions (not implemented)

| Feature | Where it plugs in |
| --- | --- |
| Platform-managed drivers | A `platform` provider with `DeliveryTerms(PLATFORM, PLATFORM)`. The split, ledger (`DELIVERY_FEE_REVENUE`), refunds and reconciliation already handle a platform-received fee (covered by unit tests). Add `Driver` and `DriverAssignment` tables and an assignment service. |
| Driver dashboard / task management | A driver role and a `/driver/*` router reading assignments. Status changes go through `delivery.service.transition` with `EventSource.PROVIDER/PLATFORM`. |
| Tracking and OTP proof of delivery | A `DeliveryProof` table (OTP hash, attempts, verified_at). The provider declares `proof_of_delivery`, and the DELIVERED transition requires a verified proof. Location pings belong in a separate append-only table, not on `Delivery`. |
| Third-party couriers | An adapter per courier (`providers/<name>.py`) that maps its API and webhooks to `DeliveryStatus`, stores `provider_reference`, and verifies webhook signatures like payment webhooks. |
| Several providers per store | Extend `StoreDeliverySettings` with enabled provider keys and let `provider_for` choose among them. Orders already store the provider key per delivery. |

## 7. API

| Endpoint | Purpose |
| --- | --- |
| `GET /cart`, `POST /checkout/quote` | Quote with per-store `delivery_options`, chosen `delivery`, `delivery_fee`, `delivery_vat`, `delivery_pending` |
| `POST /checkout` | `address_id`, `deliveries[]`, `delivery_instructions` |
| `GET /orders/{id}` | Each merchant order includes `delivery` (status, timeline, snapshot, fee terms) |
| `GET /stores/{slug}/delivery` | Public zones, fees, times, methods and policy |
| `GET/PUT /merchant/delivery/settings` | Methods offered, pickup preparation, policy, plus fee terms and commission policy (read-only) |
| `GET/POST /merchant/delivery/zones`, `PUT/DELETE /merchant/delivery/zones/{id}` | Zone management (tenant-isolated) |
| `GET /merchant/deliveries` | Delivery queue (`status`, `method`, `active` filters) |
| `POST /merchant/orders/{id}/delivery/status` | Status change, with `failure_reason` for FAILED and optional courier details |
| `POST /merchant/orders/{id}/refunds`, `POST /admin/payments/{id}/refunds` | `scope`: AUTO / ITEMS / DELIVERY |
| `PUT /admin/settings/delivery` | Commission policy for delivery fees |

## 8. Migration (0004)

Existing stores keep their behaviour. The flat `stores.shipping_fee` and
`free_shipping_threshold` become a nationwide zone per store, and the shipping policy becomes
the delivery policy. `shipping_total`/`shipping_address` are renamed `delivery_fee` (merchant
order) and `delivery_total`/`delivery_address` (order). Legacy physical orders are marked
merchant-delivered, and their delivery VAT is derived from `vat_total`. Legacy payments are
not componentized (their allocations have `delivery_amount = 0` and their ledger entries no
component), which keeps them consistent with the immutable ledger.

## 9. Tests

`apps/backend/tests/test_delivery.py` covers zone specificity and normalization, out-of-zone
and not-offered checkouts, zone validation and tenant isolation, coordinates and
instructions, the full delivery lifecycle (including a failed attempt and retry), pickup,
choosing between methods and pickup points, the legacy fulfillment endpoint, cancellation
before dispatch and after a failure, delivery commission, every refund scope, lost
chargebacks, the explicit settings validation, and the platform-received fee model (unit
tests). Every financial test asserts that the ledger and delivery reconciliation stay
consistent. `apps/frontend/e2e/delivery.e2e.ts` covers pickup checkout with the merchant
fulfilling it from the dashboard, and zone management.
