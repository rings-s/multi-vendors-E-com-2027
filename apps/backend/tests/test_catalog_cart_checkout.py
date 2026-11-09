"""Catalog, public discovery, cart pricing, inventory and checkout."""

import uuid

from tests.helpers import (
    API,
    Client,
    active_merchant,
    add_address,
    checkout,
    create_admin,
    create_category,
    create_product,
    create_service,
    create_zone,
    mobile,
    place_order,
    register_customer,
)


async def test_product_creation_with_variants_and_public_listing(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    title = f"Oud Perfume {uuid.uuid4().hex[:6]}"
    product = await create_product(
        client,
        merchant,
        title=title,
        price=25000,
        stock=0,
        variants=[
            {"sku": f"V-{uuid.uuid4().hex[:6]}", "name": "50ml", "options": {"size": "50ml"}, "stock_quantity": 3},
            {
                "sku": f"V-{uuid.uuid4().hex[:6]}",
                "name": "100ml",
                "options": {"size": "100ml"},
                "price": 40000,
                "stock_quantity": 1,
            },
        ],
    )
    assert product["merchant_id"] == merchant.extra["merchant_id"]
    assert len(product["variants"]) == 2
    public = await client.get(f"{API}/products/{product['id']}")
    assert public["title"] == title
    results = await client.get(f"{API}/products", params={"q": title})
    assert [p["id"] for p in results["items"]] == [product["id"]]
    store_products = await client.get(f"{API}/stores/{merchant.extra['slug']}/products")
    assert store_products["total"] == 1

    # A product with variants requires choosing one.
    customer = await register_customer(client)
    response = await client.request("POST", f"{API}/cart/items", customer, json={"product_id": product["id"]})
    assert response.status_code == 422
    variant = next(v for v in product["variants"] if v["name"] == "100ml")
    cart = await client.post(
        f"{API}/cart/items", customer, json={"product_id": product["id"], "variant_id": variant["id"]}
    )
    assert cart["items_subtotal"] == 40000


async def test_draft_products_are_not_public(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, status="DRAFT")
    assert (await client.request("GET", f"{API}/products/{product['id']}")).status_code == 404


async def test_cart_pricing_discount_delivery_and_vat(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin, delivery_zone=False)
    await create_zone(client, merchant, name="Riyadh", region="riyadh", fee=2500, free_delivery_threshold=50000)
    product = await create_product(client, merchant, price=10000, discounted=8000, stock=20)
    customer = await register_customer(client)
    await add_address(client, customer)  # default address: priced in the cart

    cart = await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"], "quantity": 2})
    group = cart["groups"][0]
    line = group["lines"][0]
    assert line["unit_price"] == 10000 and line["unit_discount"] == 2000
    assert line["line_subtotal"] == 20000 and line["line_discount"] == 4000 and line["line_total"] == 16000
    assert group["delivery_method"] == "DELIVERY" and group["delivery_fee"] == 2500
    # VAT 15% on discounted items + delivery (merchant is VAT-registered).
    assert group["vat_total"] == round((16000 + 2500) * 0.15)
    assert group["delivery_vat"] == 375
    assert cart["total"] == 16000 + 2500 + 2775

    # Reaching the free-delivery threshold waives the delivery fee.
    item_id = line["cart_item_id"]
    cart = await client.patch(f"{API}/cart/items/{item_id}", customer, json={"quantity": 7})
    assert cart["groups"][0]["delivery_fee"] == 0
    assert cart["groups"][0]["delivery_fee_waived"] == 2500
    assert cart["total"] == 56000 + 8400

    cart = await client.delete(f"{API}/cart/items/{item_id}", customer)
    assert cart["item_count"] == 0 and cart["total"] == 0


async def test_cart_rejects_client_prices(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, price=10000)
    customer = await register_customer(client)
    cart = await client.post(
        f"{API}/cart/items", customer, json={"product_id": product["id"], "quantity": 1, "price": 1, "total": 1}
    )
    assert cart["items_subtotal"] == 10000


async def test_stock_validation(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=2)
    customer = await register_customer(client)
    cart = await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"], "quantity": 3})
    assert cart["can_checkout"] is False
    assert "insufficient_stock" in cart["groups"][0]["lines"][0]["issues"]
    address = await add_address(client, customer)
    response = await checkout(client, customer, address_id=address["id"], expect=422)
    assert response["error"]["code"] == "cart_not_purchasable"


async def test_checkout_reserves_inventory_and_prevents_overselling(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=1)
    first = await register_customer(client)
    second = await register_customer(client)
    await place_order(client, first, [(product, 1)])
    # The last unit is reserved by the first checkout.
    cart = await client.post(f"{API}/cart/items", second, json={"product_id": product["id"], "quantity": 1})
    assert cart["can_checkout"] is False
    inventory = await client.get(f"{API}/merchant/inventory", merchant)
    row = next(i for i in inventory if i["product_id"] == product["id"])
    assert row["quantity_reserved"] == 1 and row["available"] == 0


async def test_multi_merchant_cart_creates_separate_checkout_groups(client: Client) -> None:
    admin = await create_admin(client)
    merchant_a = await active_merchant(client, admin)
    merchant_b = await active_merchant(client, admin)
    product_a = await create_product(client, merchant_a, price=10000)
    product_b = await create_product(client, merchant_b, price=5000)
    customer = await register_customer(client)
    order = await place_order(client, customer, [(product_a, 1), (product_b, 2)])

    assert len(order["merchant_orders"]) == 2
    by_merchant = {mo["merchant_id"]: mo for mo in order["merchant_orders"]}
    mo_a = by_merchant[merchant_a.extra["merchant_id"]]
    mo_b = by_merchant[merchant_b.extra["merchant_id"]]
    # Each merchant order is paid by its own payment transaction.
    assert mo_a["payment"]["id"] != mo_b["payment"]["id"]
    assert mo_a["payment"]["amount"] == mo_a["total"] == 11500
    assert mo_b["payment"]["amount"] == mo_b["total"] == 11500
    assert order["total"] == mo_a["total"] + mo_b["total"]
    # The cart is emptied after checkout.
    cart = await client.get(f"{API}/cart", customer)
    assert cart["item_count"] == 0


async def test_checkout_requires_terms_and_address(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    response = await client.request(
        "POST",
        f"{API}/checkout",
        customer,
        json={"contact_phone": mobile(), "accept_terms": False},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "terms_not_accepted"
    response = await checkout(client, customer, expect=422)
    assert response["error"]["code"] == "address_required"
    # Idempotency-Key header is mandatory.
    response = await client.request(
        "POST", f"{API}/checkout", customer, json={"contact_phone": mobile(), "accept_terms": True}
    )
    assert response.status_code == 422


async def test_checkout_is_idempotent(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, stock=5)
    customer = await register_customer(client)
    address = await add_address(client, customer)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"]})
    key = uuid.uuid4().hex
    body = {"address_id": address["id"], "contact_phone": mobile(), "accept_terms": True}
    first = await client.post(f"{API}/checkout", customer, json=body, headers={"Idempotency-Key": key}, expect=None)
    second = await client.post(f"{API}/checkout", customer, json=body, headers={"Idempotency-Key": key}, expect=None)
    assert first["id"] == second["id"]
    orders = await client.get(f"{API}/orders", customer)
    assert orders["total"] == 1


async def test_service_checkout_needs_no_address(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    service = await create_service(client, merchant, price=30000)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"service_id": service["id"]})
    order = await checkout(client, customer)
    mo = order["merchant_orders"][0]
    assert mo["fulfillment_type"] == "SERVICE"
    assert mo["delivery_fee"] == 0 and mo["delivery_method"] == "NONE" and mo["delivery"] is None
    assert order["delivery_address"] is None


async def test_store_discovery_filters(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    merchant = await active_merchant(client, admin, category["id"])
    stores = await client.get(f"{API}/stores", params={"category": category["slug"]})
    assert merchant.extra["slug"] in {s["slug"] for s in stores["items"]}
    stores = await client.get(f"{API}/stores", params={"city": "Jeddah", "q": merchant.extra["slug"]})
    assert merchant.extra["slug"] not in {s["slug"] for s in stores["items"]}
    homepage = await client.get(f"{API}/homepage")
    assert isinstance(homepage, dict)
