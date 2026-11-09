# Product Requirements

## 1. Customer application

### 1.1 Public homepage

Build a premium marketplace homepage.

Include:

- Header navigation.
- Search.
- Category navigation.
- Featured stores.
- Featured products.
- Popular services.
- Recently added stores.
- Promotional sections.
- Customer testimonials.
- Footer.

The homepage must be configurable through the admin dashboard.

### 1.2 Store discovery

Customers should be able to:

- Browse all approved stores.
- Search stores by name.
- Filter by category.
- Filter by city.
- Filter by rating.
- Sort by popularity.
- Sort by newest.
- View store information.

Only approved and active merchants should appear publicly.

### 1.3 Storefront

Each merchant gets a public storefront.

Example:

`marketplace.com/stores/store-slug`

Storefront includes:

- Store logo.
- Cover image.
- Store name.
- Description.
- Category.
- Location.
- Business contact details.
- Operating status.
- Ratings.
- Product catalog.
- Services.
- Reviews.
- Store policies.

### 1.4 Product catalog

Support:

- Product title.
- Description.
- Images.
- Price.
- Discounted price.
- SKU.
- Category.
- Stock quantity.
- Product variants.
- Availability.
- Shipping requirements.
- Product status.

Products must belong to a merchant.

### 1.5 Service catalog

Support:

- Service title.
- Description.
- Images.
- Price.
- Duration.
- Availability.
- Service category.
- Location.
- Merchant information.

Keep service fulfillment extensible for future scheduling capabilities.

### 1.6 Shopping cart

Implement:

- Add to cart.
- Remove from cart.
- Update quantities.
- Validate product availability.
- Calculate subtotals.
- Calculate shipping if applicable.
- Display taxes where applicable.
- Display discounts.
- Display final amount.

Support multiple merchants in one shopping cart at the application level.

However, payment splitting must be designed carefully.

Each merchant's order allocation must be calculated independently.

Do not assume the provider supports multiple sellers in a single transaction.

If the provider only supports one seller per split transaction, implement merchant-specific checkout groups and separate payment transactions.

Never charge a single transaction that cannot be correctly allocated and reconciled.

### 1.7 Checkout

Checkout must include:

- Customer details.
- Saudi mobile number.
- Delivery address where applicable.
- Order summary.
- Merchant breakdown.
- Shipping costs.
- Applicable VAT.
- Payment method.
- Terms and conditions.
- Final confirmation.

Never trust frontend-provided prices or commission calculations.

All financial calculations must be performed and validated by the backend.

### 1.8 Customer orders

Customers can:

- View orders.
- View payment status.
- View fulfillment status.
- View merchant information.
- Track delivery where supported.
- Request cancellation.
- Request refunds.
- Download receipts.

---

## 2. Merchant registration and onboarding

This is a critical application module.

Every merchant must complete business registration before selling.

### 2.1 Merchant registration

Collect:

- Owner's full name.
- Email.
- Saudi mobile number.
- Business name.
- Store name.
- Business category.
- Business description.
- City.
- Business address.
- Business registration information where applicable.
- Tax registration information where applicable.

### 2.2 Merchant verification

Support verification statuses:

- Draft.
- Submitted.
- Under review.
- Additional information required.
- Approved.
- Rejected.
- Suspended.

Do not allow merchants to accept payments before the required verification and provider activation are complete.

### 2.3 Payment onboarding

See [Payment Architecture — Payment onboarding](../architecture/payment-architecture.md#1-payment-onboarding).

---

## 3. Merchant dashboard

Build a complete merchant dashboard.

### Overview

Display:

- Total sales.
- Orders today.
- Total orders.
- Net earnings.
- Platform commissions.
- Pending settlements.
- Completed settlements.
- Recent transactions.
- Sales charts.

### Store management

- Edit store information.
- Update logo and cover.
- Manage store status.
- Configure store policies.
- Manage locations.

### Product management

- Create products.
- Edit products.
- Delete/archive products.
- Upload images.
- Manage variants.
- Manage inventory.
- Manage availability.
- Set discounts.

### Service management

- Create services.
- Edit services.
- Manage availability.
- Configure prices and durations.

### Order management

- View orders.
- Accept or reject orders where applicable.
- Update fulfillment status.
- Mark orders as fulfilled.
- View payment details.
- Manage cancellations.

### Financial dashboard

Provide dedicated pages:

- Overview.
- Transactions.
- Earnings.
- Commission history.
- Settlements.
- Refunds.
- Bank account information.
- Payment onboarding status.

The merchant must be able to understand exactly how much they earned and how much was transferred to their bank account.

The merchant must not be able to withdraw money manually if the provider's model uses automatic settlement.

Do not create fake withdrawal functionality.

---

## 4. Administration dashboard

Build a complete administrative interface.

### Overview

Display:

- Total customers.
- Total merchants.
- Active merchants.
- Pending merchant applications.
- Total orders.
- Gross marketplace sales.
- Platform revenue.
- Payment success rate.
- Refund volume.
- Settlement volume.

### Merchant management

- View merchants.
- Review merchant applications.
- Approve merchants.
- Reject applications.
- Suspend merchants.
- Reactivate merchants.
- View merchant verification.
- View payment-provider account status.
- View merchant financial history.

### Commission management

Administrators can:

- Set global commission.
- Configure merchant-specific commission.
- Configure category-specific commission.
- View historical commission changes.

Require authorization and audit logging for commission changes.

### Payment management

Administrators can:

- View all payments.
- Search by payment reference.
- View split allocations.
- View payment-provider responses.
- View payment status.
- View refunds.
- View chargebacks.
- View settlement records.
- Trigger permitted reconciliation operations.

### Order management

- Search orders.
- Filter by merchant.
- Filter by customer.
- Filter by date.
- View order history.
- Investigate payment failures.
- Review cancellation requests.

### Platform settings

- Marketplace configuration.
- Currency configuration.
- Tax configuration.
- Payment provider configuration.
- Commission defaults.
- Categories.
- Languages.
- Email templates.
- Audit logs.

---

## 5. Frontend design system

The visual quality must be premium.

Do not create a generic Bootstrap-style marketplace or a conventional SaaS template.

Design the interface as a carefully crafted modern commerce product.

### Design direction

- Minimalist.
- Premium.
- Editorial.
- Functional.
- Modern.
- Strong typography.
- Clear information hierarchy.
- Excellent spacing.
- Subtle motion.
- Responsive.

Support dark and light themes.

Create one centralized design-token system.

Use consistent:

- Colors.
- Typography.
- Spacing.
- Border radii.
- Shadows.
- Surface levels.
- Component states.

Use Arabic-compatible typography.

Use proper RTL layout rather than simply changing text alignment.

### Customer interface

Design:

- Homepage.
- Discovery.
- Category pages.
- Search results.
- Storefront.
- Product details.
- Service details.
- Shopping cart.
- Checkout.
- Payment result.
- Customer account.
- Order history.

### Merchant interface

Design:

- Dashboard.
- Store profile.
- Products.
- Services.
- Inventory.
- Orders.
- Customers.
- Transactions.
- Earnings.
- Settlements.
- Payment onboarding.
- Settings.

### Admin interface

Design:

- Overview.
- Merchant management.
- Customer management.
- Product moderation.
- Order management.
- Payments.
- Commissions.
- Settlements.
- Reconciliation.
- Settings.

### UX requirements

- Responsive layouts.
- Accessible forms.
- Keyboard navigation.
- Loading states.
- Skeleton screens.
- Empty states.
- Error states.
- Success feedback.
- Confirmation dialogs.
- Toast notifications.
- Clear validation errors.

Do not use decorative components that do not serve a purpose.

Do not use fake charts or hardcoded financial metrics in production pages.

---

## 6. Internationalization

Implement Arabic and English from the beginning.

Requirements:

- Arabic RTL.
- English LTR.
- Translated navigation.
- Translated validation.
- Translated notifications.
- Translated system messages.
- Localized dates.
- SAR formatting.
- Saudi phone formatting.

Persist the user's language preference.

All customer-facing and merchant-facing interfaces must support both languages.

---

## 7. Notifications

Build an internal notification system.

Support:

- Merchant approval.
- Merchant rejection.
- Payment success.
- Payment failure.
- New order.
- Order status change.
- Refund status.
- Settlement completion.
- Settlement failure.
- Account suspension.

Use an extensible notification architecture.

Start with in-app notifications and transactional email where configured.

Do not make WhatsApp integration a dependency of the initial release.

Do not invent external provider credentials.

---

## 8. Testing

Testing is a mandatory part of development.

### Backend tests

Use pytest.

Test:

- Authentication.
- Authorization.
- Merchant isolation.
- Merchant onboarding.
- Product creation.
- Cart calculations.
- Order creation.
- Commission calculation.
- Payment allocation.
- Payment success.
- Payment failure.
- Duplicate webhooks.
- Out-of-order webhooks.
- Full refunds.
- Partial refunds.
- Settlement updates.
- Ledger consistency.
- Reconciliation.

### Critical financial tests

Verify:

1. Total allocation always equals the transaction amount.
2. Platform commission is calculated correctly.
3. Seller proceeds are calculated correctly.
4. A failed payment never credits the seller.
5. Duplicate webhooks never create duplicate ledger entries.
6. A refund cannot exceed the refundable amount.
7. A settlement cannot be marked complete without verified confirmation.
8. Merchant A cannot access Merchant B's financial records.
9. Currency conversion is never silently performed.
10. Financial rounding is deterministic.

### Frontend tests

Use appropriate Svelte testing tools.

Test:

- Registration.
- Login.
- Merchant onboarding.
- Product management.
- Checkout.
- Order history.
- Dashboard navigation.
- Financial data rendering.
- Arabic RTL.
- English LTR.

Use Playwright for end-to-end critical flows.
