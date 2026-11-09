"""Payments, split allocations, commissions and webhooks (critical financial tests)."""

import uuid
from typing import Any

from app.integrations.payments.factory import get_payment_provider
from app.integrations.payments.mock import MockPaymentProvider
from tests import db
from tests.helpers import (
    API,
    Actor,
    Client,
    active_merchant,
    create_admin,
    create_category,
    create_product,
    paid_order,
    pay,
    place_order,
    register_customer,
)


def mock_provider() -> MockPaymentProvider:
    provider = get_payment_provider()
    assert isinstance(provider, MockPaymentProvider)
    return provider


async def send_webhook(client: Client, event_type: str, data: dict[str, Any], event_id: str | None = None) -> Any:
    request = mock_provider().build_webhook(event_type, data, event_id=event_id)
    response = await client.request("POST", f"{API}/webhooks/mock", content=request.body, headers=request.headers)
    return response


async def admin_payment(client: Client, admin: Actor, payment_id: str) -> dict[str, Any]:
    return await client.get(f"{API}/admin/payments/{payment_id}", admin)


async def test_successful_payment_allocates_and_credits_ledger(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, price=10000)
    customer = await register_customer(client)
    order, mo = await paid_order(client, customer, product)

    assert order["status"] == "PAID" and mo["status"] == "PAID"
    payment = await admin_payment(client, admin, mo["payment"]["id"])
    assert payment["is_test"] is True and payment["provider"] == "mock"
    # Allocation: 10% commission on the 100 SAR item (pre-VAT); merchant gets the rest incl. VAT.
    allocations = {a["recipient_type"]: a for a in payment["allocations"]}
    assert allocations["PLATFORM"]["amount"] == 1000
    assert allocations["MERCHANT"]["amount"] == 10500
    assert sum(a["amount"] for a in payment["allocations"]) == payment["amount"] == 11500
    assert all(a["amount"] >= 0 for a in payment["allocations"])
    # Fees are explicitly borne by the platform (default) and never deducted from the seller.
    assert payment["fee_bearer"] == "PLATFORM"
    assert allocations["PLATFORM"]["is_fee_source"] is True
    assert allocations["MERCHANT"]["is_fee_source"] is False

    postings = await db.ledger_postings(payment["id"])
    captured = next(p for p in postings if p["type"] == "PAYMENT_CAPTURED")
    assert sorted(captured["entries"]) == sorted([("DEBIT", 11500), ("CREDIT", 10500), ("CREDIT", 1000)])
    assert captured["is_test"] is True
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500
    await db.assert_ledger_consistent()

    # Commission record is visible to the merchant.
    commissions = await client.get(f"{API}/merchant/commissions", merchant)
    assert commissions["current_rule"]["scope"] == "GLOBAL"
    record = commissions["transactions"]["items"][0]
    assert record["commission_amount"] == 1000
    assert record["gross_amount"] == 11500

    # The merchant is notified of the new paid order; the customer of the payment.
    merchant_types = {n["type"] for n in (await client.get(f"{API}/notifications", merchant))["items"]}
    assert "new_order" in merchant_types
    customer_types = {n["type"] for n in (await client.get(f"{API}/notifications", customer))["items"]}
    assert "payment_succeeded" in customer_types


async def test_failed_payment_never_credits_seller(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=3)
    customer = await register_customer(client)
    order = await place_order(client, customer, [(product, 1)])
    mo = order["merchant_orders"][0]
    payment = await pay(client, customer, mo["payment"]["id"], outcome="failed")
    assert payment["status"] == "FAILED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    assert await db.merchant_ledger_count(merchant.extra["merchant_id"]) == 0
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    assert order["merchant_orders"][0]["status"] == "PENDING_PAYMENT"

    # The customer can retry with a fresh payment.
    retry = await client.post(f"{API}/payments/merchant-orders/{mo['id']}/retry", customer)
    assert retry["id"] != payment["id"] and retry["status"] == "CREATED"
    paid = await pay(client, customer, retry["id"], outcome="paid")
    assert paid["status"] == "PAID"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500 + 0  # 100 SAR + 15% VAT - 10 SAR
    await db.assert_ledger_consistent()


async def test_payment_status_comes_from_provider_not_browser(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    order = await place_order(client, customer, [(product, 1)])
    payment_id = order["merchant_orders"][0]["payment"]["id"]
    payment = await pay(client, customer, payment_id, outcome="redirect")
    assert payment["status"] == "PENDING"
    assert payment["transaction_url"]
    # A browser claiming success changes nothing: sync asks the provider, which still says "initiated".
    synced = await client.post(f"{API}/payments/{payment_id}/sync", customer, params={"status": "paid"})
    assert synced["status"] == "PENDING"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0


async def test_paying_twice_is_rejected(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _order, mo = await paid_order(client, customer, product)
    response = await client.request(
        "POST",
        f"{API}/payments/{mo['payment']['id']}/pay",
        customer,
        json={"source": {"type": "mock", "outcome": "paid"}},
    )
    assert response.status_code == 409


async def test_duplicate_webhooks_never_duplicate_ledger_entries(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _order, mo = await paid_order(client, customer, product)
    payment_id = mo["payment"]["id"]
    before = await db.ledger_postings(payment_id)

    event_id = str(uuid.uuid4())
    first = await send_webhook(client, "payment.paid", {"id": payment_id}, event_id=event_id)
    second = await send_webhook(client, "payment.paid", {"id": payment_id}, event_id=event_id)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["outcome"] == "duplicate"
    # A new event id for the same state is processed but is also idempotent.
    third = await send_webhook(client, "payment.paid", {"id": payment_id})
    assert third.status_code == 200 and third.json()["outcome"] == "processed"

    assert await db.ledger_postings(payment_id) == before
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500
    await db.assert_ledger_consistent()


async def test_out_of_order_webhooks_are_monotonic(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _order, mo = await paid_order(client, customer, product)
    payment_id = mo["payment"]["id"]
    # Stale events arriving after the capture never move the payment backwards.
    for stale in ("payment.initiated", "payment.failed"):
        response = await send_webhook(client, stale, {"id": payment_id})
        assert response.status_code == 200
    payment = await admin_payment(client, admin, payment_id)
    assert payment["status"] == "PAID"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500


async def test_state_machine_ignores_failure_after_capture(client: Client) -> None:
    """Even if a provider reported a regression, a captured payment is never un-captured."""
    from app.database.session import get_sessionmaker
    from app.integrations.payments.base import ProviderPayment
    from app.modules.payments.models import Payment, PaymentStatus
    from app.modules.payments.service import apply_provider_state

    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _, mo = await paid_order(client, customer, product)
    async with get_sessionmaker()() as session, session.begin():
        payment = await session.get(Payment, uuid.UUID(mo["payment"]["id"]), with_for_update=True)
        assert payment is not None
        remote = ProviderPayment(
            provider_payment_id=payment.provider_payment_id or str(payment.id),
            status=PaymentStatus.FAILED,
            raw_status="failed",
            amount=payment.amount,
            currency="SAR",
            refunded_amount=0,
            fee=payment.fee,
            transaction_url=None,
            failure_reason="Card declined",
            is_live=False,
            payment_method=None,
            raw={},
        )
        await apply_provider_state(session, payment, remote, get_payment_provider())
        assert payment.status == PaymentStatus.PAID.value


async def test_invalid_webhook_signature_rejected(client: Client) -> None:
    request = mock_provider().build_webhook("payment.paid", {"id": str(uuid.uuid4())})
    headers = {"x-mock-signature": "0" * 64}
    response = await client.request("POST", f"{API}/webhooks/mock", content=request.body, headers=headers)
    assert response.status_code == 401
    response = await client.request("POST", f"{API}/webhooks/mock", content=request.body)
    assert response.status_code == 401
    # Unknown/inactive providers are refused.
    response = await client.request("POST", f"{API}/webhooks/moyasar", content=b"{}")
    assert response.status_code == 404


async def test_webhook_processing_failure_is_retryable(client: Client) -> None:
    admin = await create_admin(client)
    event_id = str(uuid.uuid4())
    # Unknown payment: processing fails, the event is stored as FAILED and the provider gets a 5xx to retry.
    response = await send_webhook(client, "payment.paid", {"id": str(uuid.uuid4())}, event_id=event_id)
    assert response.status_code == 500
    events = await client.get(f"{API}/admin/webhook-events", admin, params={"status": "FAILED"})
    row = next(e for e in events["items"] if e["event_id"] == event_id)
    assert row["last_error"]
    result = await client.post(f"{API}/admin/webhook-events/{row['id']}/reprocess", admin, expect=None)
    assert result is not None


async def test_merchant_specific_commission_and_history(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    rule = await client.post(
        f"{API}/admin/commissions",
        admin,
        json={
            "scope": "MERCHANT",
            "merchant_id": merchant.extra["merchant_id"],
            "rate_type": "PERCENTAGE",
            "rate": "15",
            "note": "Premium placement",
        },
        expect=201,
    )
    product = await create_product(client, merchant, price=12345)
    customer = await register_customer(client)
    _, mo = await paid_order(client, customer, product)
    payment = await admin_payment(client, admin, mo["payment"]["id"])
    allocations = {a["recipient_type"]: a["amount"] for a in payment["allocations"]}
    # 15% of 123.45 SAR = 18.5175 -> 18.52 SAR (ROUND_HALF_UP, deterministic)
    assert allocations["PLATFORM"] == 1852
    assert allocations["PLATFORM"] + allocations["MERCHANT"] == payment["amount"]

    # Changing the rate later never changes existing orders.
    await client.post(f"{API}/admin/commissions/{rule['id']}/end", admin)
    await client.post(
        f"{API}/admin/commissions",
        admin,
        json={
            "scope": "MERCHANT",
            "merchant_id": merchant.extra["merchant_id"],
            "rate_type": "PERCENTAGE",
            "rate": "5",
        },
        expect=201,
    )
    payment = await admin_payment(client, admin, mo["payment"]["id"])
    assert {a["recipient_type"]: a["amount"] for a in payment["allocations"]}["PLATFORM"] == 1852
    history = await client.get(f"{API}/admin/commissions", admin, params={"merchant_id": merchant.extra["merchant_id"]})
    assert history["total"] >= 2
    logs = await client.get(f"{API}/admin/audit-logs", admin, params={"entity_type": "commission_rule"})
    assert logs["total"] >= 2


async def test_category_commission_and_fixed_commission(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    await client.post(
        f"{API}/admin/commissions",
        admin,
        json={"scope": "CATEGORY", "category_id": category["id"], "rate_type": "FIXED", "fixed_amount": 300},
        expect=201,
    )
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, price=5000, category_id=category["id"])
    customer = await register_customer(client)
    _, mo = await paid_order(client, customer, product, quantity=2)
    payment = await admin_payment(client, admin, mo["payment"]["id"])
    allocations = {a["recipient_type"]: a["amount"] for a in payment["allocations"]}
    assert allocations["PLATFORM"] == 600  # 3 SAR fixed per unit x 2
    assert allocations["MERCHANT"] == payment["amount"] - 600


async def test_merchant_without_active_provider_account_cannot_be_paid(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    order = await place_order(client, customer, [(product, 1)])
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    await client.post(
        f"{API}/mock-provider/merchants/{account['provider_account_id']}/status", json={"status": "disabled"}
    )
    response = await client.request(
        "POST",
        f"{API}/payments/{order['merchant_orders'][0]['payment']['id']}/pay",
        customer,
        json={"source": {"type": "mock", "outcome": "paid"}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "merchant_cannot_accept_payments"


async def test_customer_cannot_access_other_customers_payments(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    owner = await register_customer(client)
    intruder = await register_customer(client)
    order, mo = await paid_order(client, owner, product)
    assert (await client.request("GET", f"{API}/payments/{mo['payment']['id']}", intruder)).status_code == 404
    assert (await client.request("GET", f"{API}/orders/{order['id']}", intruder)).status_code == 404
