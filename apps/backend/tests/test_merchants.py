"""Merchant registration, verification workflow and payment onboarding."""

from tests.helpers import (
    API,
    Client,
    active_merchant,
    approve_merchant,
    create_admin,
    create_category,
    create_product,
    onboard_payments,
    register_customer,
    register_merchant,
)


async def test_registration_creates_draft_merchant_and_hidden_store(client: Client) -> None:
    merchant = await register_merchant(client)
    me = await client.get(f"{API}/merchants/me", merchant)
    assert me["status"] == "DRAFT"
    assert me["can_accept_payments"] is False
    assert me["contact_phone"].startswith("+9665")
    assert merchant.user["roles"] == ["MERCHANT"]
    # Unapproved stores are never public.
    assert (await client.request("GET", f"{API}/stores/{merchant.extra['slug']}")).status_code == 404


async def test_duplicate_store_slug_rejected(client: Client) -> None:
    merchant = await register_merchant(client)
    me = await client.get(f"{API}/merchants/me", merchant)
    response = await client.request(
        "POST",
        f"{API}/merchants/register",
        json={
            "owner_full_name": "Someone Else",
            "email": "slug-clash@example.com",
            "password": "correct-horse-battery-staple",
            "mobile": "0551234567",
            "business_name": "Clash",
            "store_name": "Clash",
            "store_slug": me["store_slug"],
            "city": "Jeddah",
            "address": {"region": "makkah", "city": "Jeddah"},
        },
    )
    assert response.status_code == 409


async def test_invalid_saudi_data_rejected(client: Client) -> None:
    response = await client.request(
        "POST",
        f"{API}/merchants/register",
        json={
            "owner_full_name": "Bad Data",
            "email": "bad-data@example.com",
            "password": "correct-horse-battery-staple",
            "mobile": "+12025550123",
            "business_name": "Bad",
            "store_name": "Bad",
            "store_slug": "bad-data-store",
            "city": "Riyadh",
            "address": {"region": "not-a-region", "city": "Riyadh"},
        },
    )
    assert response.status_code == 422
    locations = {tuple(d["loc"]) for d in response.json()["error"]["details"]}
    assert ("body", "mobile") in locations
    assert ("body", "address", "region") in locations


async def test_verification_workflow(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    merchant = await register_merchant(client, category["id"])
    merchant_id = merchant.extra["merchant_id"]

    await client.post(f"{API}/merchants/onboarding/submit", merchant)
    await client.post(f"{API}/admin/merchants/{merchant_id}/start_review", admin, json={})
    # Rejection-type transitions require a reason.
    response = await client.request("POST", f"{API}/admin/merchants/{merchant_id}/request_info", admin, json={})
    assert response.status_code == 422
    await client.post(
        f"{API}/admin/merchants/{merchant_id}/request_info", admin, json={"reason": "Upload your CR certificate"}
    )
    me = await client.get(f"{API}/merchants/me", merchant)
    assert me["status"] == "ADDITIONAL_INFO_REQUIRED"
    # The merchant may edit and resubmit.
    await client.patch(
        f"{API}/merchants/onboarding",
        merchant,
        json={"business_description": "Updated details with our commercial registration."},
    )
    await client.post(f"{API}/merchants/onboarding/submit", merchant)
    await client.post(f"{API}/admin/merchants/{merchant_id}/approve", admin, json={})

    history = await client.get(f"{API}/merchants/onboarding/history", merchant)
    assert [h["to_status"] for h in history] == [
        "DRAFT",
        "SUBMITTED",
        "UNDER_REVIEW",
        "ADDITIONAL_INFO_REQUIRED",
        "SUBMITTED",
        "APPROVED",
    ]
    # Approval is not enough: payments need provider activation first.
    me = await client.get(f"{API}/merchants/me", merchant)
    assert me["status"] == "APPROVED"
    assert me["can_accept_payments"] is False

    notifications = await client.get(f"{API}/notifications", merchant)
    assert "merchant_approved" in {n["type"] for n in notifications["items"]}

    # Every transition is audit-logged.
    logs = await client.get(f"{API}/admin/audit-logs", admin, params={"entity_id": merchant_id})
    assert logs["total"] >= 1


async def test_invalid_transition_rejected(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await register_merchant(client)
    response = await client.request(
        "POST", f"{API}/admin/merchants/{merchant.extra['merchant_id']}/approve", admin, json={}
    )
    assert response.status_code == 409  # DRAFT cannot jump to APPROVED


async def test_payment_onboarding_requires_approval(client: Client) -> None:
    merchant = await register_merchant(client)
    response = await client.request(
        "POST",
        f"{API}/merchants/payment-account",
        merchant,
        json={
            "bank_account": {"beneficiary_name": "Merchant", "iban": "SA0380000000608010167519"},
            "website": "https://example.com",
            "owners_count": 1,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_approved"


async def test_payment_onboarding_stores_only_masked_iban(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    merchant = await register_merchant(client, category["id"])
    await approve_merchant(client, merchant, admin)
    account = await onboard_payments(client, merchant)
    assert account["onboarding_status"] == "ACTIVE"
    assert account["payout_status"] == "ENABLED"
    assert account["can_accept_payments"] is True
    assert account["provider"] == "mock" and account["is_test"] is True
    masked = account["bank_account"]["iban_masked"]
    assert masked.startswith("SA") and "*" in masked
    assert len(masked.replace("*", "")) == 8
    # Now the store is public.
    store = await client.get(f"{API}/stores/{merchant.extra['slug']}")
    assert store["slug"] == merchant.extra["slug"]


async def test_provider_status_sync_via_webhook(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    merchant = await register_merchant(client, category["id"])
    await approve_merchant(client, merchant, admin)
    account = await onboard_payments(client, merchant)
    # The provider disables the account; the signed webhook updates our record.
    await client.post(
        f"{API}/mock-provider/merchants/{account['provider_account_id']}/status",
        json={"status": "disabled", "reasons": ["Compliance review"]},
    )
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    assert account["onboarding_status"] == "DISABLED"
    assert account["can_accept_payments"] is False
    # Re-activated by the provider.
    await client.post(
        f"{API}/mock-provider/merchants/{account['provider_account_id']}/status", json={"status": "active"}
    )
    account = await client.post(f"{API}/merchants/payment-account/sync", merchant)
    assert account["can_accept_payments"] is True


async def test_suspension_hides_store_and_blocks_purchases(client: Client) -> None:
    admin = await create_admin(client)
    category = await create_category(client, admin)
    merchant = await register_merchant(client, category["id"])
    await approve_merchant(client, merchant, admin)
    await onboard_payments(client, merchant)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    await client.post(f"{API}/cart/items", customer, json={"product_id": product["id"], "quantity": 1})

    merchant_id = merchant.extra["merchant_id"]
    await client.post(f"{API}/admin/merchants/{merchant_id}/suspend", admin, json={"reason": "Policy violation"})
    assert (await client.request("GET", f"{API}/stores/{merchant.extra['slug']}")).status_code == 404
    assert (await client.request("GET", f"{API}/products/{product['id']}")).status_code == 404
    cart = await client.get(f"{API}/cart", customer)
    assert cart["can_checkout"] is False

    await client.post(f"{API}/admin/merchants/{merchant_id}/reactivate", admin, json={})
    assert (await client.request("GET", f"{API}/stores/{merchant.extra['slug']}")).status_code == 200


async def test_location_map_pin_round_trip_and_validation(client: Client) -> None:
    merchant = await register_merchant(client)
    base = {"region": "riyadh", "city": "Riyadh", "district": "Al Olaya"}

    created = await client.post(
        f"{API}/merchant/store/locations",
        merchant,
        json={**base, "label": "Showroom", "latitude": 24.7136, "longitude": 46.6753},
        expect=201,
    )
    assert (created["latitude"], created["longitude"]) == (24.7136, 46.6753)

    listed = await client.get(f"{API}/merchant/store/locations", merchant)
    assert any(loc["id"] == created["id"] and loc["latitude"] == 24.7136 for loc in listed)
    # Locations without a pin stay valid (the primary address from registration has none).
    assert any(loc["is_primary"] and loc["latitude"] is None for loc in listed)

    cleared = await client.put(
        f"{API}/merchant/store/locations/{created['id']}",
        merchant,
        json={**base, "label": "Showroom", "latitude": None, "longitude": None},
    )
    assert cleared["latitude"] is None and cleared["longitude"] is None

    # A half pin or an out-of-range coordinate is rejected.
    await client.post(f"{API}/merchant/store/locations", merchant, json={**base, "latitude": 24.7}, expect=422)
    await client.post(
        f"{API}/merchant/store/locations", merchant, json={**base, "latitude": 95, "longitude": 46.6}, expect=422
    )


async def test_public_store_locations_expose_only_pickup_points(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    slug = merchant.extra["slug"]
    base = {"region": "riyadh", "city": "Riyadh", "district": "Al Olaya"}

    pickup = await client.post(
        f"{API}/merchant/store/locations",
        merchant,
        json={**base, "label": "Showroom", "is_pickup_location": True, "latitude": 24.71, "longitude": 46.67},
        expect=201,
    )
    await client.post(f"{API}/merchant/store/locations", merchant, json={**base, "label": "Warehouse"}, expect=201)

    public = await client.get(f"{API}/stores/{slug}/locations")
    # The warehouse and the registered business address (not pickup points) stay private.
    assert [loc["id"] for loc in public] == [pickup["id"]]
    assert public[0]["latitude"] == 24.71 and public[0]["label"] == "Showroom"
    assert "is_primary" not in public[0] and "merchant_id" not in public[0]

    hidden = await register_merchant(client)
    await client.get(f"{API}/stores/{hidden.extra['slug']}/locations", expect=404)
