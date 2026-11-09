"""Remaining marketplace workflows: provider document requirements, reviews, uploads,
moderation, cancellations, inventory, homepage configuration, support and rate limiting."""

import uuid

import pytest

from tests import db
from tests.helpers import (
    API,
    Client,
    active_merchant,
    create_admin,
    create_product,
    paid_order,
    place_order,
    register_customer,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def test_provider_document_requirements_are_tracked(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    assert account["documents"] == []
    url = f"{API}/mock-provider/merchants/{account['provider_account_id']}/status"
    await client.post(
        url,
        json={
            "status": "missing_docs",
            "reasons": ["IBAN certificate is unreadable"],
            "required_documents": ["iban_certificate", "commercial_registration"],
        },
    )
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    assert account["onboarding_status"] == "ACTION_REQUIRED"
    assert account["can_accept_payments"] is False
    assert account["reasons"] == ["IBAN certificate is unreadable"]
    assert {(d["document_type"], d["status"]) for d in account["documents"]} == {
        ("commercial_registration", "REQUIRED"),
        ("iban_certificate", "REQUIRED"),
    }
    # The merchant supplies them through the provider's process; the provider activates the account.
    await client.post(url, json={"status": "active"})
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    assert account["can_accept_payments"] is True
    assert {d["status"] for d in account["documents"]} == {"SATISFIED"}


async def test_review_requires_purchase_and_updates_rating(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    order, mo = await paid_order(client, customer, product)
    review_url = f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/review"
    # Not fulfilled yet.
    response = await client.request("POST", review_url, customer, json={"rating": 5, "comment": "Great"})
    assert response.status_code in (409, 422)
    fulfillment = f"{API}/merchant/orders/{mo['id']}/fulfillment"
    for status in ("ACCEPTED", "SHIPPED", "DELIVERED"):
        await client.post(fulfillment, merchant, json={"status": status})
    review = await client.post(review_url, customer, json={"rating": 4, "comment": "Lovely scent"}, expect=None)
    assert review["rating"] == 4
    duplicate = await client.request("POST", review_url, customer, json={"rating": 1})
    assert duplicate.status_code == 409
    store = await client.get(f"{API}/stores/{merchant.extra['slug']}")
    assert store["rating_count"] == 1 and float(store["rating_avg"]) == 4.0
    reviews = await client.get(f"{API}/stores/{merchant.extra['slug']}/reviews")
    assert reviews["total"] == 1
    # Moderation hides it and recalculates the rating.
    await client.post(f"{API}/admin/reviews/{review['id']}/moderation", admin, json={"status": "HIDDEN"}, expect=204)
    assert (await client.get(f"{API}/stores/{merchant.extra['slug']}/reviews"))["total"] == 0
    assert (await client.get(f"{API}/stores/{merchant.extra['slug']}"))["rating_count"] == 0
    # Other customers cannot review an order they did not place.
    stranger = await register_customer(client)
    response = await client.request("POST", review_url, stranger, json={"rating": 1})
    assert response.status_code == 404


async def test_image_upload_validation(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    customer = await register_customer(client)
    forbidden = await client.request(
        "POST", f"{API}/uploads/images", customer, files={"file": ("a.png", PNG, "image/png")}
    )
    assert forbidden.status_code == 403
    ok = await client.post(f"{API}/uploads/images", merchant, files={"file": ("a.png", PNG, "image/png")}, expect=201)
    assert ok["url"].startswith("/media/product/") and ok["url"].endswith(".png")
    served = await client.request("GET", ok["url"])
    assert served.status_code == 200 and served.content == PNG
    # The declared content type is ignored; content is checked by magic bytes.
    fake = await client.request(
        "POST",
        f"{API}/uploads/images",
        merchant,
        files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert fake.status_code == 422
    empty = await client.request("POST", f"{API}/uploads/images", merchant, files={"file": ("e.png", b"", "image/png")})
    assert empty.status_code == 422
    anonymous = await client.request("POST", f"{API}/uploads/images", files={"file": ("a.png", PNG, "image/png")})
    assert anonymous.status_code == 401


async def test_product_moderation_blocks_public_listing(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    await client.post(
        f"{API}/admin/products/{product['id']}/moderation", admin, json={"action": "block", "note": "Counterfeit"}
    )
    assert (await client.request("GET", f"{API}/products/{product['id']}")).status_code == 404
    mine = await client.get(f"{API}/merchant/products/{product['id']}", merchant)
    assert mine["status"] == "BLOCKED"
    # The merchant cannot simply re-activate a blocked product.
    response = await client.request(
        "PATCH", f"{API}/merchant/products/{product['id']}", merchant, json={"status": "ACTIVE"}
    )
    assert response.status_code in (403, 409, 422)
    await client.post(f"{API}/admin/products/{product['id']}/moderation", admin, json={"action": "unblock"})
    await client.patch(f"{API}/merchant/products/{product['id']}", merchant, json={"status": "ACTIVE"})
    assert (await client.request("GET", f"{API}/products/{product['id']}")).status_code == 200


async def test_customer_cancellation_request_approved_refunds_and_restocks(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=3)
    customer = await register_customer(client)
    order, mo = await paid_order(client, customer, product)
    await client.post(
        f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/cancel", customer, json={"reason": "Ordered twice"}
    )
    pending = await client.get(f"{API}/admin/orders", admin, params={"cancellation_requested": True})
    assert mo["id"] in {o["id"] for o in pending["items"]}
    await client.post(f"{API}/merchant/orders/{mo['id']}/cancellation-decision", merchant, json={"approve": True})
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    mo = order["merchant_orders"][0]
    assert mo["status"] == "CANCELLED"
    assert mo["payment"]["status"] == "REFUNDED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    inventory = await client.get(f"{API}/merchant/inventory", merchant)
    row = next(i for i in inventory if i["product_id"] == product["id"])
    assert row["available"] == 3
    await db.assert_ledger_consistent()


async def test_unpaid_order_cancellation_releases_stock(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=1)
    customer = await register_customer(client)
    order = await place_order(client, customer, [(product, 1)])
    mo = order["merchant_orders"][0]
    await client.post(
        f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/cancel", customer, json={"reason": "Changed mind"}
    )
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    assert order["merchant_orders"][0]["status"] == "CANCELLED"
    inventory = await client.get(f"{API}/merchant/inventory", merchant)
    assert next(i for i in inventory if i["product_id"] == product["id"])["available"] == 1


async def test_inventory_adjustments(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=5)
    inventory = await client.get(f"{API}/merchant/inventory", merchant)
    row = next(i for i in inventory if i["product_id"] == product["id"])
    url = f"{API}/merchant/inventory/{row['id']}"

    def on_hand(rows: list[dict[str, int]]) -> int:
        return next(r for r in rows if r["id"] == row["id"])["quantity_on_hand"]

    assert on_hand(await client.patch(url, merchant, json={"delta": 3})) == 8
    assert on_hand(await client.patch(url, merchant, json={"quantity_on_hand": 2})) == 2
    negative = await client.request("PATCH", url, merchant, json={"delta": -10})
    assert negative.status_code in (409, 422)
    both = await client.request("PATCH", url, merchant, json={"delta": 1, "quantity_on_hand": 1})
    assert both.status_code == 422


async def test_homepage_is_configured_by_admin(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    current = (await client.get(f"{API}/admin/settings", admin))["homepage"]
    hero = f"Hero {uuid.uuid4().hex[:6]}"
    await client.put(
        f"{API}/admin/settings/homepage",
        admin,
        json={
            **current,
            "hero_title_en": hero,
            "featured_store_ids": [merchant.extra["store_id"]],
            "featured_product_ids": [product["id"]],
        },
    )
    try:
        homepage = await client.get(f"{API}/homepage")
        text = str(homepage)
        assert hero in text
        assert merchant.extra["slug"] in text
        assert product["id"] in text
    finally:
        await client.put(f"{API}/admin/settings/homepage", admin, json=current)


async def test_support_tickets(client: Client) -> None:
    admin = await create_admin(client)
    customer = await register_customer(client)
    ticket = await client.post(
        f"{API}/support/tickets",
        customer,
        json={"subject": "Where is my order?", "body": "It has been a week since I ordered."},
        expect=201,
    )
    assert ticket["status"] == "OPEN"
    other = await register_customer(client)
    assert (await client.get(f"{API}/support/tickets", other))["total"] == 0
    tickets = await client.get(f"{API}/admin/support-tickets", admin)
    assert ticket["id"] in {t["id"] for t in tickets["items"]}
    await client.patch(
        f"{API}/admin/support-tickets/{ticket['id']}",
        admin,
        json={"status": "RESOLVED", "admin_response": "Shipped today."},
    )
    mine = (await client.get(f"{API}/support/tickets", customer))["items"][0]
    assert mine["status"] == "RESOLVED" and mine["admin_response"] == "Shipped today."


async def test_auth_endpoints_are_rate_limited(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "auth_rate_limit_per_minute", 3)
    headers = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 250}, 10.0.0.1"}
    body = {"email": f"nobody-{uuid.uuid4().hex}@example.com", "password": "wrong-password-1"}
    statuses = [
        (await client.request("POST", f"{API}/auth/login", json=body, headers=headers)).status_code for _ in range(4)
    ]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429


async def test_every_list_endpoint_responds_without_server_errors(client: Client, app) -> None:  # type: ignore[no-untyped-def]
    """Sweep all parameterless GET endpoints as every role on populated data."""
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    await paid_order(client, customer, product)
    paths = [
        p
        for p, ops in app.openapi()["paths"].items()
        if "get" in ops and "{" not in p and not p.startswith(("/api/docs", "/api/redoc"))
    ]
    assert len(paths) > 40
    failures = []
    for actor in (None, customer, merchant, admin):
        for path in paths:
            response = await client.request("GET", path, actor)
            if response.status_code >= 500:
                failures.append((path, response.status_code, response.text[:200]))
    assert failures == []
