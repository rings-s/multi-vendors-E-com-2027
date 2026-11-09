"""Delivery & fulfillment: zones, pickup, the delivery lifecycle and delivery money."""

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest

from tests import db
from tests.helpers import (
    API,
    Actor,
    Client,
    active_merchant,
    add_address,
    checkout,
    create_admin,
    create_product,
    create_zone,
    enable_pickup,
    register_customer,
)

DELIVERY_ISSUES = {"merchant_delivery", "platform_delivery", "delivery_allocation"}


async def pay(client: Client, customer: Actor, order: dict[str, Any]) -> dict[str, Any]:
    """Pay every merchant order of ``order`` through the hosted flow (signed webhook)."""
    for mo in order["merchant_orders"]:
        payment = await client.post(
            f"{API}/payments/{mo['payment']['id']}/pay",
            customer,
            json={"source": {"type": "mock", "outcome": "redirect"}},
        )
        await client.request(
            "POST",
            f"{API}/mock-provider/payments/{payment['id']}/complete",
            data={"outcome": "paid"},
            expect=303,
            follow_redirects=False,
        )
    return await client.get(f"{API}/orders/{order['id']}", customer)


async def set_status(client: Client, merchant: Actor, mo_id: str, status: str, expect: int = 200, **extra: Any) -> Any:
    return await client.post(
        f"{API}/merchant/orders/{mo_id}/delivery/status", merchant, json={"status": status, **extra}, expect=expect
    )


async def assert_delivery_reconciles() -> None:
    issues = [i for i in await db.reconciliation_issues() if i["type"] in DELIVERY_ISSUES]
    assert issues == []
    await db.assert_ledger_consistent()


@pytest.fixture
async def delivery_commission(client: Client) -> AsyncIterator[Actor]:
    """Temporarily charge 20% commission on delivery fees (platform setting)."""
    admin = await create_admin(client)
    previous = (await client.get(f"{API}/admin/settings", admin))["delivery"]
    await client.put(
        f"{API}/admin/settings/delivery",
        admin,
        json={"commission_applies_to": "ITEMS_AND_DELIVERY", "delivery_commission_rate": "20"},
    )
    try:
        yield admin
    finally:
        await client.put(f"{API}/admin/settings/delivery", admin, json=previous)


# -- configuration & quoting -----------------------------------------------------------------


async def test_most_specific_zone_applies_with_normalized_place_names(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(client, merchant, name="Kingdom", fee=5000, eta_min_minutes=2880, eta_max_minutes=7200)
    await create_zone(client, merchant, name="Riyadh region", region="riyadh", fee=3000)
    await create_zone(client, merchant, name="Riyadh city", region="riyadh", cities=["Riyadh", "الرياض"], fee=2000)
    await create_zone(
        client,
        merchant,
        name="North Riyadh",
        region="riyadh",
        cities=["Riyadh"],
        districts=["Al Malqa", "Al Yasmin"],
        fee=1000,
        eta_min_minutes=60,
        eta_max_minutes=180,
    )
    product = await create_product(client, merchant, price=10000)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})

    async def quote(**address: Any) -> dict[str, Any]:
        addr = await add_address(client, customer, **address)
        return (await client.post(f"{API}/checkout/quote", customer, json={"address_id": addr["id"]}))["groups"][0]

    group = await quote(district="al-malqa")  # normalized district match
    assert group["delivery"]["zone_name"] == "North Riyadh" and group["delivery_fee"] == 1000
    assert (group["delivery"]["eta_min_minutes"], group["delivery"]["eta_max_minutes"]) == (60, 180)
    group = await quote(city="الرياض", district="Al Olaya")
    assert group["delivery"]["zone_name"] == "Riyadh city" and group["delivery_fee"] == 2000
    group = await quote(city="Al Kharj", district="")
    assert group["delivery"]["zone_name"] == "Riyadh region" and group["delivery_fee"] == 3000
    group = await quote(region="makkah", city="Jeddah", district="")
    assert group["delivery"]["zone_name"] == "Kingdom" and group["delivery_fee"] == 5000

    public = await client.get(f"{API}/stores/{merchant.extra['slug']}/delivery")
    assert public["delivery_offered"] is True and public["pickup_offered"] is False
    assert {z["name"] for z in public["zones"]} == {"Kingdom", "Riyadh region", "Riyadh city", "North Riyadh"}


async def test_address_outside_zones_blocks_checkout(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(client, merchant, name="Riyadh", region="riyadh", fee=1500)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    address = await add_address(client, customer, region="makkah", city="Jeddah")
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    cart = await client.get(f"{API}/cart", customer)
    assert cart["can_checkout"] is False
    assert "address_outside_delivery_zones" in cart["groups"][0]["issues"]
    response = await checkout(client, customer, address_id=address["id"], expect=422)
    assert response["error"]["code"] == "cart_not_purchasable"


async def test_zone_validation_and_tenant_isolation(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    other = await active_merchant(client, admin)
    url = f"{API}/merchant/delivery/zones"
    base = {"name": "Zone", "fee": 1000, "eta_min_minutes": 60, "eta_max_minutes": 120}
    for bad in (
        {**base, "cities": ["Riyadh"]},  # cities need a region
        {**base, "region": "riyadh", "districts": ["Al Malqa"]},  # districts need a city
        {**base, "eta_min_minutes": 200},  # window reversed
        {**base, "fee": -1},
        {**base, "region": "atlantis"},
    ):
        assert (await client.request("POST", url, merchant, json=bad)).status_code == 422, bad
    zone = await client.post(url, merchant, json={**base, "region": "riyadh"}, expect=201)
    assert (await client.request("PUT", f"{url}/{zone['id']}", other, json=base)).status_code == 404
    assert (await client.request("DELETE", f"{url}/{zone['id']}", other)).status_code == 404
    assert zone["id"] not in {z["id"] for z in await client.get(url, other)}
    updated = await client.put(f"{url}/{zone['id']}", merchant, json={**base, "fee": 1200, "is_active": False})
    assert updated["fee"] == 1200 and updated["is_active"] is False
    await client.delete(f"{url}/{zone['id']}", merchant, expect=204)


async def test_customer_address_coordinates_and_instructions(client: Client) -> None:
    customer = await register_customer(client)
    response = await client.request(
        "POST",
        f"{API}/customers/addresses",
        customer,
        json={"recipient_name": "A B", "phone": "0551234567", "region": "riyadh", "city": "Riyadh", "latitude": 24.7},
    )
    assert response.status_code == 422
    address = await add_address(
        client, customer, latitude=24.8107, longitude=46.6343, delivery_instructions="Ring the second bell"
    )
    assert address["latitude"] == 24.8107 and address["delivery_instructions"] == "Ring the second bell"
    cleared = await client.patch(f"{API}/customers/addresses/{address['id']}", customer, json={"clear_location": True})
    assert cleared["latitude"] is None and cleared["longitude"] is None


# -- merchant delivery lifecycle ---------------------------------------------------------------


async def test_merchant_delivery_lifecycle_and_explicit_money(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(
        client, merchant, name="Riyadh", region="riyadh", fee=2500, eta_min_minutes=120, eta_max_minutes=480
    )
    product = await create_product(client, merchant, price=10000, stock=5)
    customer = await register_customer(client)
    address = await add_address(client, customer, latitude=24.8107, longitude=46.6343)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    order = await checkout(client, customer, address_id=address["id"], instructions="Leave at the reception")

    mo = order["merchant_orders"][0]
    # Delivery is charged separately from items; VAT applies to both (VAT-registered merchant).
    assert (mo["items_subtotal"], mo["delivery_fee"], mo["delivery_vat"], mo["vat_total"]) == (10000, 2500, 375, 1875)
    assert mo["total"] == 14375 and order["delivery_total"] == 2500
    delivery = mo["delivery"]
    assert delivery["status"] == "PENDING" and delivery["method"] == "DELIVERY" and delivery["provider"] == "merchant"
    assert delivery["address"]["district"] == "Al Malqa"
    assert (delivery["latitude"], delivery["longitude"]) == (24.8107, 46.6343)
    assert delivery["instructions"] == "Leave at the reception"
    assert delivery["fee_recipient"] == "MERCHANT" and delivery["cost_bearer"] == "MERCHANT"

    # Not payable yet: the merchant cannot confirm an unpaid order.
    await set_status(client, merchant, mo["id"], "CONFIRMED", expect=409)
    order = await pay(client, customer, order)
    mo_id = mo["id"]

    view = await client.get(f"{API}/merchant/orders/{mo_id}", merchant)
    # Item commission (10%) excludes delivery; the delivery charge is the merchant's.
    assert view["commission_total"] == 1000 and view["delivery_commission"] == 0
    assert view["merchant_net"] == 13375 and view["merchant_delivery_share"] == 2875
    assert view["delivery"]["next_statuses"] == ["CONFIRMED"]
    payment = await client.get(f"{API}/admin/payments/{view['payment']['id']}", admin)
    alloc = {a["recipient_type"]: a for a in payment["allocations"]}
    assert (alloc["MERCHANT"]["amount"], alloc["MERCHANT"]["delivery_amount"]) == (13375, 2875)
    assert (alloc["PLATFORM"]["amount"], alloc["PLATFORM"]["delivery_amount"]) == (1000, 0)
    lines = await db.ledger_lines(view["payment"]["id"])
    assert ("MERCHANT_PAYABLE", "CREDIT", 2875, "DELIVERY") in lines
    assert ("MERCHANT_PAYABLE", "CREDIT", 10500, "GOODS") in lines
    assert ("PLATFORM_COMMISSION", "CREDIT", 1000, "GOODS") in lines

    view = await set_status(client, merchant, mo_id, "CONFIRMED")
    assert view["status"] == "ACCEPTED" and view["delivery"]["estimated_latest_at"] is not None
    assert view["delivery"]["next_statuses"] == ["PREPARING", "OUT_FOR_DELIVERY"]
    await set_status(client, merchant, mo_id, "READY_FOR_PICKUP", expect=409)  # not a pickup order
    view = await set_status(client, merchant, mo_id, "PREPARING")
    assert view["status"] == "PROCESSING"
    view = await set_status(client, merchant, mo_id, "OUT_FOR_DELIVERY", carrier="Own driver")
    assert view["status"] == "SHIPPED" and view["delivery"]["attempts"] == 1
    # A failure needs a reason; it can be retried.
    assert (
        await client.request(
            "POST", f"{API}/merchant/orders/{mo_id}/delivery/status", merchant, json={"status": "FAILED"}
        )
    ).status_code == 422
    view = await set_status(client, merchant, mo_id, "FAILED", failure_reason="Customer unreachable")
    assert view["delivery"]["status"] == "FAILED" and view["delivery"]["failure_reason"] == "Customer unreachable"
    assert view["status"] == "SHIPPED"
    view = await set_status(client, merchant, mo_id, "OUT_FOR_DELIVERY")
    assert view["delivery"]["attempts"] == 2 and view["delivery"]["failure_reason"] is None
    view = await set_status(client, merchant, mo_id, "DELIVERED")
    assert view["status"] == "DELIVERED" and view["delivery"]["next_statuses"] == []
    await set_status(client, merchant, mo_id, "OUT_FOR_DELIVERY", expect=409)

    order = await client.get(f"{API}/orders/{order['id']}", customer)
    customer_delivery = order["merchant_orders"][0]["delivery"]
    assert customer_delivery["next_statuses"] == []  # customers cannot change delivery status
    assert [e["to_status"] for e in customer_delivery["events"]] == [
        "PENDING",
        "CONFIRMED",
        "PREPARING",
        "OUT_FOR_DELIVERY",
        "FAILED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
    ]
    notifications = (await client.get(f"{API}/notifications", customer))["items"]
    assert "delivery_status_changed" in {n["type"] for n in notifications}
    queue = await client.get(f"{API}/merchant/deliveries", merchant)
    assert mo_id in {d["merchant_order_id"] for d in queue["items"]}
    assert (await client.get(f"{API}/merchant/deliveries", merchant, params={"active": True}))["total"] == 0
    await assert_delivery_reconciles()


async def test_customer_pickup_needs_no_address_and_has_no_fee(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)  # pickup only
    location = await enable_pickup(client, merchant)
    product = await create_product(client, merchant, price=10000)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})

    cart = await client.get(f"{API}/cart", customer)
    group = cart["groups"][0]
    assert group["delivery_method"] == "PICKUP" and cart["can_checkout"] is True
    assert group["delivery"]["pickup_location"]["id"] == location["id"]
    assert cart["needs_address"] is False

    order = await checkout(client, customer, deliveries=[{"store_id": merchant.extra["store_id"], "method": "PICKUP"}])
    assert order["delivery_address"] is None
    mo = order["merchant_orders"][0]
    assert mo["delivery_method"] == "PICKUP" and mo["delivery_fee"] == 0 and mo["total"] == 11500
    assert mo["delivery"]["pickup_location"]["label"] == "Main branch"
    assert mo["delivery"]["cost_bearer"] == "CUSTOMER"
    assert mo["delivery"]["eta_max_minutes"] == 90

    await pay(client, customer, order)
    await set_status(client, merchant, mo["id"], "CONFIRMED")
    await set_status(client, merchant, mo["id"], "OUT_FOR_DELIVERY", expect=409)  # pickup has no dispatch
    view = await set_status(client, merchant, mo["id"], "READY_FOR_PICKUP")
    assert view["status"] == "PROCESSING" and view["delivery"]["next_statuses"] == ["DELIVERED", "FAILED"]
    view = await set_status(client, merchant, mo["id"], "DELIVERED")
    assert view["status"] == "DELIVERED"
    await assert_delivery_reconciles()


async def test_choosing_between_delivery_and_pickup(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(client, merchant, name="Riyadh", region="riyadh", fee=2000)
    await enable_pickup(client, merchant)
    await enable_pickup(client, merchant, label="Second branch", district="Al Yasmin")
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    address = await add_address(client, customer)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    store_id = merchant.extra["store_id"]

    quote = await client.post(f"{API}/checkout/quote", customer, json={"address_id": address["id"]})
    group = quote["groups"][0]
    assert group["delivery_method"] == "DELIVERY" and group["delivery_fee"] == 2000  # default: delivery
    assert {o["method"] for o in group["delivery_options"]} == {"DELIVERY", "PICKUP"}
    pickup = next(o for o in group["delivery_options"] if o["method"] == "PICKUP")
    assert len(pickup["pickup_points"]) == 2

    # Two pickup points: the customer must choose one.
    response = await checkout(
        client, customer, address_id=address["id"], deliveries=[{"store_id": store_id, "method": "PICKUP"}], expect=422
    )
    assert response["error"]["code"] == "cart_not_purchasable"
    point = pickup["pickup_points"][1]["id"]
    foreign = await client.request(
        "POST",
        f"{API}/checkout",
        customer,
        json={
            "contact_phone": "0551234567",
            "accept_terms": True,
            "deliveries": [{"store_id": store_id, "method": "PICKUP", "pickup_location_id": str(uuid.uuid4())}],
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert foreign.status_code == 422
    order = await checkout(
        client, customer, deliveries=[{"store_id": store_id, "method": "PICKUP", "pickup_location_id": point}]
    )
    mo = order["merchant_orders"][0]
    assert mo["delivery_fee"] == 0 and mo["delivery"]["pickup_location"]["label"] == "Second branch"


async def test_store_offering_nothing_cannot_sell_physical_items(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    address = await add_address(client, customer)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    response = await checkout(client, customer, address_id=address["id"], expect=422)
    assert response["error"]["code"] == "cart_not_purchasable"
    assert response["error"]["details"][0]["issues"] == ["delivery_not_offered"]


async def test_legacy_fulfillment_endpoint_drives_the_delivery(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    await enable_pickup(client, merchant)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    order = await checkout(client, customer, deliveries=[{"store_id": merchant.extra["store_id"], "method": "PICKUP"}])
    mo_id = order["merchant_orders"][0]["id"]
    await pay(client, customer, order)
    url = f"{API}/merchant/orders/{mo_id}/fulfillment"
    await client.post(url, merchant, json={"status": "ACCEPTED"})
    view = await client.post(url, merchant, json={"status": "SHIPPED"})  # pickup: becomes ready for pickup
    assert view["delivery"]["status"] == "READY_FOR_PICKUP"
    view = await client.post(url, merchant, json={"status": "DELIVERED"})
    assert view["status"] == "DELIVERED" and view["delivery"]["status"] == "DELIVERED"


async def test_other_merchants_cannot_update_a_delivery(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    other = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    address = await add_address(client, customer)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    order = await pay(client, customer, await checkout(client, customer, address_id=address["id"]))
    await set_status(client, other, order["merchant_orders"][0]["id"], "CONFIRMED", expect=404)


# -- cancellations, failures and refunds ---------------------------------------------------------


async def _delivered_setup(client: Client, fee: int = 2500) -> tuple[Actor, Actor, Actor, dict[str, Any]]:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(client, merchant, name="Riyadh", region="riyadh", fee=fee)
    product = await create_product(client, merchant, price=10000, stock=5)
    customer = await register_customer(client)
    address = await add_address(client, customer)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    order = await pay(client, customer, await checkout(client, customer, address_id=address["id"]))
    return admin, merchant, customer, order


async def test_cancelling_before_dispatch_cancels_the_delivery(client: Client) -> None:
    _admin, merchant, customer, order = await _delivered_setup(client)
    mo_id = order["merchant_orders"][0]["id"]
    await set_status(client, merchant, mo_id, "CONFIRMED")
    await client.post(f"{API}/merchant/orders/{mo_id}/cancel", merchant, json={"reason": "Damaged in storage"})
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    mo = order["merchant_orders"][0]
    assert mo["status"] == "CANCELLED" and mo["delivery"]["status"] == "CANCELLED"
    assert mo["payment"]["status"] == "REFUNDED" and mo["payment"]["refunded_amount"] == 14375
    await assert_delivery_reconciles()


async def test_failed_delivery_can_be_cancelled_with_full_refund(client: Client) -> None:
    _admin, merchant, customer, order = await _delivered_setup(client)
    mo_id = order["merchant_orders"][0]["id"]
    await set_status(client, merchant, mo_id, "CONFIRMED")
    await set_status(client, merchant, mo_id, "OUT_FOR_DELIVERY")
    # Out for delivery: no longer cancellable…
    response = await client.request(
        "POST", f"{API}/merchant/orders/{mo_id}/cancel", merchant, json={"reason": "Changed plans"}
    )
    assert response.status_code == 409
    # …unless the delivery failed.
    await set_status(client, merchant, mo_id, "FAILED", failure_reason="Address does not exist")
    await client.post(f"{API}/merchant/orders/{mo_id}/cancel", merchant, json={"reason": "Undeliverable"})
    mo = (await client.get(f"{API}/orders/{order['id']}", customer))["merchant_orders"][0]
    assert mo["status"] == "CANCELLED" and mo["delivery"]["status"] == "CANCELLED"
    assert mo["payment"]["refunded_amount"] == mo["total"]
    await assert_delivery_reconciles()


async def test_delivery_refund_scopes(client: Client, delivery_commission: Actor) -> None:
    admin, merchant, customer, order = await _delivered_setup(client)
    mo = order["merchant_orders"][0]
    view = await client.get(f"{API}/merchant/orders/{mo['id']}", merchant)
    # 20% delivery commission is separate from item commission and taken from the fee excl. VAT.
    assert view["commission_total"] == 1000 and view["delivery_commission"] == 500
    assert view["merchant_net"] == 14375 - 1000 - 500
    commissions = await client.get(f"{API}/merchant/commissions", merchant)
    ct = next(t for t in commissions["transactions"]["items"] if t["merchant_order_id"] == mo["id"])
    assert ct["commission_amount"] == 1000 and ct["seller_net_amount"] == 12875
    payment_id = mo["payment"]["id"]
    capture = await db.ledger_lines(payment_id)
    assert ("DELIVERY_COMMISSION", "CREDIT", 500, "DELIVERY") in capture
    assert ("MERCHANT_PAYABLE", "CREDIT", 2375, "DELIVERY") in capture

    url = f"{API}/admin/payments/{payment_id}/refunds"
    # Delivery-only refund cannot exceed the delivery charge (fee 2500 + VAT 375).
    too_much = await client.request("POST", url, admin, json={"amount": 2876, "scope": "DELIVERY", "reason": "Late"})
    assert too_much.status_code == 422 and too_much.json()["error"]["details"]["refundable"] == 2875
    delivery_refund = await client.post(url, admin, json={"scope": "DELIVERY", "reason": "Late delivery"}, expect=201)
    assert delivery_refund["amount"] == 2875 and delivery_refund["delivery_portion"] == 2875
    assert delivery_refund["delivery_platform_portion"] == 500 and delivery_refund["merchant_portion"] == 2375
    assert ("DELIVERY_COMMISSION", "DEBIT", 500, "DELIVERY") in await db.ledger_lines(delivery_refund["id"])
    nothing = await client.request("POST", url, admin, json={"scope": "DELIVERY", "reason": "Again"})
    assert nothing.status_code == 422

    # AUTO refunds items first; ITEMS refunds never touch delivery.
    partial = await client.post(url, admin, json={"amount": 5000, "reason": "Damaged part"}, expect=201)
    assert partial["delivery_portion"] == 0 and partial["platform_portion"] == 435  # round(5000 * 1000 / 11500)
    rest = await client.post(url, admin, json={"scope": "ITEMS", "reason": "Return"}, expect=201)
    assert rest["amount"] == 6500 and rest["delivery_portion"] == 0
    assert partial["platform_portion"] + rest["platform_portion"] == 1000  # no rounding drift

    summary = (await client.get(f"{API}/merchant/earnings", merchant))["summary"]
    assert summary["delivery_charges"] == 2875 and summary["product_sales"] == 11500
    assert summary["platform_delivery_share"] == 0 and summary["delivery_refunds"] == 2875
    assert summary["delivery_earnings"] == 0 and summary["platform_commission"] == 0
    assert "20" in summary["delivery_commission_note"]
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    mo = (await client.get(f"{API}/orders/{order['id']}", customer))["merchant_orders"][0]
    assert mo["status"] == "REFUNDED" and mo["delivery"]["status"] == "CANCELLED"
    await assert_delivery_reconciles()


async def test_full_refund_and_lost_chargeback_cover_delivery(client: Client, delivery_commission: Actor) -> None:
    admin, merchant, _customer, order = await _delivered_setup(client)
    payment_id = order["merchant_orders"][0]["payment"]["id"]
    chargeback = await client.post(
        f"{API}/admin/chargebacks",
        admin,
        json={"payment_id": payment_id, "amount": 14375, "provider_reference": f"cb-{uuid.uuid4().hex[:8]}"},
        expect=201,
    )
    lost = await client.post(f"{API}/admin/chargebacks/{chargeback['id']}/resolve", admin, json={"outcome": "LOST"})
    assert lost["delivery_portion"] == 2875 and lost["delivery_platform_portion"] == 500
    assert lost["platform_portion"] == 1500 and lost["merchant_portion"] == 12875
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    await assert_delivery_reconciles()


async def test_delivery_finance_setting_must_be_explicit(client: Client) -> None:
    admin = await create_admin(client)
    url = f"{API}/admin/settings/delivery"
    for bad in (
        {"commission_applies_to": "ITEMS_ONLY", "delivery_commission_rate": "5"},
        {"commission_applies_to": "ITEMS_AND_DELIVERY", "delivery_commission_rate": "0"},
        {"commission_applies_to": "EVERYTHING", "delivery_commission_rate": "5"},
    ):
        assert (await client.request("PUT", url, admin, json=bad)).status_code == 422, bad
    settings = await client.get(f"{API}/admin/settings", admin)
    assert settings["delivery"]["commission_applies_to"] == "ITEMS_ONLY"


# -- pure calculations (incl. the future platform-received fee model) ------------------------------


def test_delivery_charge_split_models() -> None:
    from app.modules.delivery.models import CostBearer, DeliveryMethod, FeeRecipient
    from app.modules.delivery.pricing import DeliveryTerms, delivery_charge

    merchant_terms = DeliveryTerms(FeeRecipient.MERCHANT, CostBearer.MERCHANT)
    charge = delivery_charge(
        method=DeliveryMethod.DELIVERY,
        fee=2500,
        fee_waived=0,
        terms=merchant_terms,
        vat_rate=Decimal("15"),
        commission_on_delivery=False,
        commission_rate=Decimal("0"),
    )
    assert (charge.gross, charge.platform_share, charge.merchant_share, charge.commission) == (2875, 0, 2875, 0)
    with_commission = delivery_charge(
        method=DeliveryMethod.DELIVERY,
        fee=2500,
        fee_waived=0,
        terms=merchant_terms,
        vat_rate=Decimal("15"),
        commission_on_delivery=True,
        commission_rate=Decimal("12.5"),
    )
    assert with_commission.commission == 313 and with_commission.merchant_share == 2875 - 313
    platform = delivery_charge(
        method=DeliveryMethod.DELIVERY,
        fee=2000,
        fee_waived=0,
        terms=DeliveryTerms(FeeRecipient.PLATFORM, CostBearer.PLATFORM),
        vat_rate=Decimal("15"),
        commission_on_delivery=True,
        commission_rate=Decimal("20"),
    )
    # A platform-received fee is never also charged as commission.
    assert (platform.commission, platform.platform_share, platform.merchant_share) == (0, 2300, 0)


def test_allocations_and_refund_split_for_platform_received_fee() -> None:
    from app.modules.payments.allocation import build_allocations
    from app.modules.payments.models import FeeBearer, Payment, PaymentAllocation
    from app.modules.payments.refunds import Reversed, split_portions

    merchant_id = uuid.uuid4()
    specs = build_allocations(
        total=13800,  # items 10000 + VAT 1500, delivery 2000 + VAT 300 received by the platform
        commission=1000,
        delivery_platform=2300,
        delivery_merchant=0,
        merchant_id=merchant_id,
        merchant_recipient_id="rcp_m",
        platform_recipient_id="rcp_p",
        merchant_can_accept_payments=True,
        fee_bearer=FeeBearer.PLATFORM,
    )
    by_type = {s.recipient_type.value: s for s in specs}
    assert (by_type["MERCHANT"].amount, by_type["MERCHANT"].delivery_amount) == (10500, 0)
    assert (by_type["PLATFORM"].amount, by_type["PLATFORM"].delivery_amount) == (3300, 2300)

    payment = Payment(
        order_id=uuid.uuid4(),
        merchant_order_id=uuid.uuid4(),
        merchant_id=merchant_id,
        customer_user_id=uuid.uuid4(),
        provider="mock",
        is_test=True,
        amount=13800,
        fee_bearer="PLATFORM",
        allocations=[
            PaymentAllocation(
                payment_id=uuid.uuid4(),
                recipient_type=s.recipient_type.value,
                recipient_id=s.recipient_id,
                amount=s.amount,
                delivery_amount=s.delivery_amount,
            )
            for s in specs
        ],
    )
    from app.modules.payments.models import RefundScope

    delivery = split_portions(payment, 2300, Reversed(), RefundScope.DELIVERY)
    assert (delivery.platform, delivery.merchant, delivery.delivery_platform) == (2300, 0, 2300)
    already = Reversed(amount=2300, platform=2300, delivery=2300, delivery_platform=2300)
    items = split_portions(payment, 11500, already)
    assert (items.platform, items.merchant, items.delivery) == (1000, 10500, 0)


def test_place_normalization() -> None:
    from app.modules.delivery.pricing import normalize_place

    assert normalize_place("  Al-Olaya ") == normalize_place("al olaya")
    assert normalize_place("الرياض") == normalize_place("الریاض")
    assert normalize_place("مكة المكرمة") == normalize_place("مكه المكرمه")
    assert normalize_place(None) == ""
