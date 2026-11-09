"""Merchant tenant isolation: merchant A can never reach merchant B's data."""

from tests.helpers import (
    API,
    Client,
    active_merchant,
    create_admin,
    create_product,
    create_service,
    paid_order,
    register_customer,
)


async def test_merchant_cannot_access_another_merchants_records(client: Client) -> None:
    admin = await create_admin(client)
    merchant_a = await active_merchant(client, admin)
    merchant_b = await active_merchant(client, admin)
    product_b = await create_product(client, merchant_b)
    service_b = await create_service(client, merchant_b)
    customer = await register_customer(client)
    _, mo_b = await paid_order(client, customer, product_b)
    refund_b = await client.post(
        f"{API}/merchant/orders/{mo_b['id']}/refunds",
        merchant_b,
        json={"amount": 100, "reason": "Goodwill"},
        expect=201,
    )

    # Products, services and orders of B are invisible (404, not 403, to avoid leaking existence).
    for method, url, body in (
        ("GET", f"{API}/merchant/products/{product_b['id']}", None),
        ("PATCH", f"{API}/merchant/products/{product_b['id']}", {"title": "Hijacked"}),
        ("DELETE", f"{API}/merchant/products/{product_b['id']}", None),
        ("GET", f"{API}/merchant/services/{service_b['id']}", None),
        ("PATCH", f"{API}/merchant/services/{service_b['id']}", {"title": "Hijacked"}),
        ("GET", f"{API}/merchant/orders/{mo_b['id']}", None),
        ("POST", f"{API}/merchant/orders/{mo_b['id']}/fulfillment", {"status": "ACCEPTED"}),
        ("POST", f"{API}/merchant/orders/{mo_b['id']}/reject", {"reason": "Not mine"}),
        ("POST", f"{API}/merchant/orders/{mo_b['id']}/refunds", {"reason": "Steal refund"}),
        ("POST", f"{API}/merchant/refunds/{refund_b['id']}/decision", {"approve": True}),
    ):
        response = await client.request(method, url, merchant_a, json=body)
        assert response.status_code == 404, f"{method} {url} -> {response.status_code}"

    # Lists, financial pages and customers only ever contain A's own data.
    assert (await client.get(f"{API}/merchant/products", merchant_a))["total"] == 0
    assert (await client.get(f"{API}/merchant/orders", merchant_a))["total"] == 0
    assert (await client.get(f"{API}/merchant/customers", merchant_a))["total"] == 0
    assert (await client.get(f"{API}/merchant/transactions", merchant_a))["total"] == 0
    assert (await client.get(f"{API}/merchant/settlements", merchant_a))["total"] == 0
    assert (await client.get(f"{API}/merchant/refunds", merchant_a))["total"] == 0
    commissions = await client.get(f"{API}/merchant/commissions", merchant_a)
    assert commissions["transactions"]["total"] == 0
    summary = (await client.get(f"{API}/merchant/earnings", merchant_a))["summary"]
    assert summary["gross_sales"] == 0 and summary["net_earnings"] == 0
    inventory = await client.get(f"{API}/merchant/inventory", merchant_a)
    assert inventory == []

    # B sees its own data.
    assert (await client.get(f"{API}/merchant/orders", merchant_b))["total"] == 1
    assert (await client.get(f"{API}/merchant/customers", merchant_b))["total"] == 1
    summary_b = (await client.get(f"{API}/merchant/earnings", merchant_b))["summary"]
    assert summary_b["gross_sales"] == 11500


async def test_merchant_order_view_hides_platform_internals(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _, mo = await paid_order(client, customer, product)
    view = await client.get(f"{API}/merchant/orders/{mo['id']}", merchant)
    text = str(view)
    assert "provider_response" not in text
    assert "password" not in text
