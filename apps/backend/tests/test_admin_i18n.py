"""Admin dashboard metrics, platform settings, notifications and Arabic/English."""

from tests.helpers import (
    API,
    Client,
    active_merchant,
    create_admin,
    create_product,
    paid_order,
    register_customer,
)


async def test_admin_overview_is_computed_from_data(client: Client) -> None:
    admin = await create_admin(client)
    before = await client.get(f"{API}/admin/overview", admin)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    await paid_order(client, customer, product)
    after = await client.get(f"{API}/admin/overview", admin)
    assert after["total_customers"] == before["total_customers"] + 1
    assert after["total_merchants"] == before["total_merchants"] + 1
    assert after["total_orders"] == before["total_orders"] + 1
    assert after["gross_marketplace_sales"] == before["gross_marketplace_sales"] + 11500
    assert after["platform_revenue"] == before["platform_revenue"] + 1000


async def test_admin_can_search_orders_and_payments(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    order, mo = await paid_order(client, customer, product)
    orders = await client.get(f"{API}/admin/orders", admin, params={"merchant_id": merchant.extra["merchant_id"]})
    assert [o["id"] for o in orders["items"]] == [mo["id"]]
    payments = await client.get(f"{API}/admin/payments", admin, params={"merchant_id": merchant.extra["merchant_id"]})
    assert [p["id"] for p in payments["items"]] == [mo["payment"]["id"]]
    by_number = await client.get(f"{API}/admin/orders", admin, params={"number": order["number"]})
    assert by_number["total"] == 1


async def test_platform_settings_are_validated_and_audited(client: Client) -> None:
    admin = await create_admin(client)
    settings = await client.get(f"{API}/admin/settings", admin)
    assert "tax" in settings and "payments" in settings
    bad = await client.request("PUT", f"{API}/admin/settings/tax", admin, json={"vat_rate": "150"})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["loc"] == ["vat_rate"]
    regular = await create_admin(client, super_admin=False)
    forbidden = await client.request("PUT", f"{API}/admin/settings/tax", regular, json=settings["tax"])
    assert forbidden.status_code == 403
    await client.put(f"{API}/admin/settings/tax", admin, json=settings["tax"])
    logs = await client.get(f"{API}/admin/audit-logs", admin, params={"entity_type": "platform_setting"})
    assert logs["total"] >= 1


async def test_payment_provider_status_is_explicit_about_mock_mode(client: Client) -> None:
    admin = await create_admin(client)
    status = await client.get(f"{API}/admin/payment-provider", admin)
    assert status["provider"] == "mock"
    assert status["is_test"] is True
    health = await client.get("/health")
    assert health["mock_payments"] is True


async def test_notifications_are_localised(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    arabic = await register_customer(client, language="ar")
    english = await register_customer(client, language="en")
    await paid_order(client, arabic, product)
    await paid_order(client, english, product)

    ar = next(
        n for n in (await client.get(f"{API}/notifications", arabic))["items"] if n["type"] == "payment_succeeded"
    )
    en = next(
        n for n in (await client.get(f"{API}/notifications", english))["items"] if n["type"] == "payment_succeeded"
    )
    assert ar["title"] == "تم الدفع بنجاح"
    assert "ريال" in ar["body"]
    assert en["title"] == "Payment successful"
    assert "115.00 SAR" in en["body"]

    # Switching the preferred language re-renders notifications.
    await client.patch(f"{API}/users/me", english, json={"preferred_language": "ar"})
    en_now = next(
        n for n in (await client.get(f"{API}/notifications", english))["items"] if n["type"] == "payment_succeeded"
    )
    assert en_now["title"] == "تم الدفع بنجاح"

    page = await client.get(f"{API}/notifications", english)
    assert page["unread"] >= 1
    await client.post(f"{API}/notifications/read-all", english, expect=204)
    assert (await client.get(f"{API}/notifications", english))["unread"] == 0


async def test_health_and_readiness(client: Client) -> None:
    assert (await client.get("/health"))["status"] == "ok"
    ready = await client.get("/ready")
    assert ready == {"database": True, "redis": True}
