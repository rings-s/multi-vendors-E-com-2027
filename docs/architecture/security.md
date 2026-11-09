# Security

## 1. Authentication and authorization

Implement secure authentication.

Support:

- Customer registration.
- Merchant registration.
- Email/password authentication.
- Email verification.
- Password reset.
- Access tokens.
- Refresh token rotation.
- Session invalidation.
- Role-based access control.

Roles:

- CUSTOMER.
- MERCHANT.
- ADMIN.
- SUPER_ADMIN.

Use secure HTTP-only cookies where appropriate for the web application.

Implement CSRF protection for cookie-authenticated state-changing requests.

Enforce authorization in the backend.

A merchant must never access another merchant's:

- Orders.
- Customers.
- Products.
- Payments.
- Financial information.
- Settlements.

Never rely on frontend role checks for authorization.

---

## 2. Security and compliance

Security is mandatory.

Implement:

- Input validation.
- SQL injection prevention.
- XSS prevention.
- CSRF protection where applicable.
- Rate limiting.
- Secure password hashing.
- Refresh-token rotation.
- Secure session management.
- CORS restrictions.
- Secret management.
- Webhook verification.
- Payment idempotency.
- Audit logs.
- Database transaction integrity.
- Merchant tenant isolation.
- File upload validation.
- Secure image storage.

### Saudi regulatory considerations

Design with awareness of:

- Saudi Personal Data Protection Law (PDPL).
- Applicable SAMA payment regulations.
- ZATCA VAT requirements.
- E-commerce requirements.
- Consumer protection.
- Merchant verification requirements.

Do not claim the platform is legally compliant simply because these controls exist.

Identify which activities require licensing, contractual approval, or legal review.

Do not assume that operating as a marketplace automatically grants authorization to receive, hold, or distribute funds.

The payment provider's approved legal and commercial arrangement must determine the actual fund flow.
