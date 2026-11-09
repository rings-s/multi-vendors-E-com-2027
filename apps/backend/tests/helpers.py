"""Reusable API flows for tests. Everything goes through the HTTP API except the
creation of administrator accounts (which, as in production, is done out of band
with the CLI)."""

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

PASSWORD = "correct-horse-battery-staple"


def saudi_iban(seed: int | None = None) -> str:
    """Build a checksum-valid Saudi IBAN (SA + 2 check digits + 20 characters)."""
    rng = random.Random(seed)
    bban = "80" + "".join(str(rng.randint(0, 9)) for _ in range(18))
    numeric = "".join(str(int(ch, 36)) for ch in bban + "SA00")
    check = 98 - int(numeric) % 97
    return f"SA{check:02d}{bban}"


def mobile() -> str:
    return "+9665" + "".join(str(random.randint(0, 9)) for _ in range(8))


@dataclass
class Actor:
    token: str
    user: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class Client:
    """Thin wrapper over httpx that never relies on cookies (bearer auth only)."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def request(
        self, method: str, url: str, actor: Actor | None = None, expect: int | None = None, **kwargs: Any
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if actor is not None:
            headers.update(actor.headers)
        self.http.cookies.clear()
        response = await self.http.request(method, url, headers=headers, **kwargs)
        if expect is not None:
            assert response.status_code == expect, f"{method} {url} -> {response.status_code}: {response.text}"
        return response

    async def get(self, url: str, actor: Actor | None = None, expect: int | None = 200, **kw: Any) -> Any:
        return (await self.request("GET", url, actor, expect, **kw)).json()

    async def post(self, url: str, actor: Actor | None = None, expect: int | None = 200, **kw: Any) -> Any:
        response = await self.request("POST", url, actor, expect, **kw)
        return response.json() if response.content else None

    async def patch(self, url: str, actor: Actor | None = None, expect: int | None = 200, **kw: Any) -> Any:
        return (await self.request("PATCH", url, actor, expect, **kw)).json()

    async def put(self, url: str, actor: Actor | None = None, expect: int | None = 200, **kw: Any) -> Any:
        return (await self.request("PUT", url, actor, expect, **kw)).json()

    async def delete(self, url: str, actor: Actor | None = None, expect: int | None = 200, **kw: Any) -> Any:
        response = await self.request("DELETE", url, actor, expect, **kw)
        return response.json() if response.content else None


API = "/api/v1"


async def register_customer(c: Client, *, language: str = "en") -> Actor:
    email = f"customer-{uuid.uuid4().hex[:10]}@example.com"
    data = await c.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Test Customer", "preferred_language": language},
        expect=201,
    )
    return Actor(token=data["access_token"], user=data["user"], extra={"email": email})


async def create_admin(c: Client, *, super_admin: bool = True) -> Actor:
    from app.database.session import get_sessionmaker
    from app.modules.auth import service
    from app.modules.auth.models import RoleName

    email = f"admin-{uuid.uuid4().hex[:10]}@example.com"
    async with get_sessionmaker()() as session, session.begin():
        await service.create_user(
            session,
            email=email,
            password=PASSWORD,
            full_name="Test Admin",
            phone=None,
            roles=[RoleName.SUPER_ADMIN if super_admin else RoleName.ADMIN],
            preferred_language="en",
        )
    data = await c.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    return Actor(token=data["access_token"], user=data["user"], extra={"email": email})


async def create_category(c: Client, admin: Actor, kind: str = "BOTH") -> dict[str, Any]:
    suffix = uuid.uuid4().hex[:8]
    return await c.post(
        f"{API}/admin/categories",
        admin,
        json={"slug": f"cat-{suffix}", "name_en": f"Category {suffix}", "name_ar": f"تصنيف {suffix}", "kind": kind},
        expect=201,
    )


async def register_merchant(c: Client, category_id: str | None = None) -> Actor:
    suffix = uuid.uuid4().hex[:8]
    email = f"merchant-{suffix}@example.com"
    data = await c.post(
        f"{API}/merchants/register",
        json={
            "owner_full_name": "Noura Al-Qahtani",
            "email": email,
            "password": PASSWORD,
            "mobile": mobile(),
            "business_name": f"Business {suffix}",
            "store_name": f"Store {suffix}",
            "store_slug": f"store-{suffix}",
            "category_id": category_id,
            "business_description": "Handmade goods from Riyadh.",
            "city": "Riyadh",
            "address": {"region": "riyadh", "city": "Riyadh", "district": "Al Olaya", "postal_code": "12211"},
            "commercial_registration_number": "1010123456",
            "vat_number": "300000000000003",
            "preferred_language": "en",
        },
        expect=201,
    )
    actor = Actor(token=data["access_token"], user=data["user"], extra={"email": email, "slug": f"store-{suffix}"})
    me = await c.get(f"{API}/merchants/me", actor)
    actor.extra["merchant_id"] = me["id"]
    actor.extra["store_id"] = me["store_id"]
    return actor


async def approve_merchant(c: Client, merchant: Actor, admin: Actor) -> None:
    await c.post(f"{API}/merchants/onboarding/submit", merchant)
    await c.post(f"{API}/admin/merchants/{merchant.extra['merchant_id']}/approve", admin, json={})


async def onboard_payments(c: Client, merchant: Actor) -> dict[str, Any]:
    await c.post(
        f"{API}/merchants/payment-account",
        merchant,
        json={
            "bank_account": {"beneficiary_name": "Noura Trading Est.", "iban": saudi_iban(), "bank_name": "SNB"},
            "website": "https://example.com",
            "owners_count": 1,
        },
    )
    return await c.post(f"{API}/merchants/payment-account/submit", merchant)


async def active_merchant(
    c: Client, admin: Actor, category_id: str | None = None, *, delivery_zone: bool = True
) -> Actor:
    """An approved merchant that can take payments. By default it delivers everywhere
    in Saudi Arabia for free (a nationwide zone), so orders need no delivery setup."""
    if category_id is None:
        category_id = (await create_category(c, admin))["id"]
    merchant = await register_merchant(c, category_id)
    merchant.extra["category_id"] = category_id
    await approve_merchant(c, merchant, admin)
    account = await onboard_payments(c, merchant)
    assert account["can_accept_payments"], account
    if delivery_zone:
        zone = await create_zone(c, merchant, name="Saudi Arabia", fee=0)
        merchant.extra["zone_id"] = zone["id"]
    return merchant


async def create_zone(c: Client, merchant: Actor, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Zone", "fee": 0, "eta_min_minutes": 1440, "eta_max_minutes": 4320, **fields}
    return await c.post(f"{API}/merchant/delivery/zones", merchant, json=body, expect=201)


async def enable_pickup(c: Client, merchant: Actor, **location: Any) -> dict[str, Any]:
    """Turn on customer pickup with one pickup location; returns the location."""
    loc = await c.post(
        f"{API}/merchant/store/locations",
        merchant,
        json={
            "label": "Main branch",
            "region": "riyadh",
            "city": "Riyadh",
            "district": "Al Olaya",
            "is_pickup_location": True,
            "latitude": 24.6907,
            "longitude": 46.6853,
            **location,
        },
        expect=201,
    )
    settings = await c.get(f"{API}/merchant/delivery/settings", merchant)
    await c.put(
        f"{API}/merchant/delivery/settings",
        merchant,
        json={
            "delivery_enabled": settings["delivery_enabled"],
            "pickup_enabled": True,
            "pickup_preparation_minutes": 90,
            "delivery_policy": settings["delivery_policy"],
        },
    )
    return loc


async def create_product(
    c: Client, merchant: Actor, *, price: int = 10000, stock: int = 10, discounted: int | None = None, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": f"Product {uuid.uuid4().hex[:6]}",
        "description": "A product",
        "sku": f"SKU-{uuid.uuid4().hex[:8]}",
        "price": price,
        "status": "ACTIVE",
        "stock_quantity": stock,
        **extra,
    }
    if discounted is not None:
        body["discounted_price"] = discounted
    return await c.post(f"{API}/merchant/products", merchant, json=body, expect=201)


async def create_service(c: Client, merchant: Actor, *, price: int = 20000) -> dict[str, Any]:
    return await c.post(
        f"{API}/merchant/services",
        merchant,
        json={"title": "Consultation", "price": price, "duration_minutes": 60, "status": "ACTIVE"},
        expect=201,
    )


async def add_address(c: Client, customer: Actor, **fields: Any) -> dict[str, Any]:
    return await c.post(
        f"{API}/customers/addresses",
        customer,
        json={
            "recipient_name": "Test Customer",
            "phone": mobile(),
            "region": "riyadh",
            "city": "Riyadh",
            "district": "Al Malqa",
            "postal_code": "13521",
            "is_default": True,
            **fields,
        },
        expect=201,
    )


async def checkout(
    c: Client,
    customer: Actor,
    *,
    address_id: str | None = None,
    expect: int = 201,
    deliveries: list[dict[str, Any]] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "address_id": address_id,
        "contact_phone": mobile(),
        "accept_terms": True,
        "payment_method": "mock",
    }
    if deliveries is not None:
        body["deliveries"] = deliveries
    if instructions is not None:
        body["delivery_instructions"] = instructions
    return await c.post(
        f"{API}/checkout", customer, json=body, headers={"Idempotency-Key": uuid.uuid4().hex}, expect=expect
    )


async def place_order(
    c: Client, customer: Actor, items: list[tuple[dict[str, Any], int]], *, address: dict[str, Any] | None = None
) -> dict[str, Any]:
    await c.delete(f"{API}/cart", customer)
    for product, quantity in items:
        await c.post(f"{API}/cart/items", customer, json={"product_id": product["id"], "quantity": quantity})
    if address is None:
        address = await add_address(c, customer)
    return await checkout(c, customer, address_id=address["id"])


async def pay(c: Client, customer: Actor, payment_id: str, outcome: str = "paid") -> dict[str, Any]:
    return await c.post(
        f"{API}/payments/{payment_id}/pay", customer, json={"source": {"type": "mock", "outcome": outcome}}
    )


async def paid_order(
    c: Client, customer: Actor, product: dict[str, Any], quantity: int = 1
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Place an order for one merchant and pay it through the hosted (redirect) flow,
    which confirms the payment via a signed webhook."""
    order = await place_order(c, customer, [(product, quantity)])
    mo = order["merchant_orders"][0]
    payment = await pay(c, customer, mo["payment"]["id"], outcome="redirect")
    assert payment["status"] == "PENDING", payment
    await c.request(
        "POST",
        f"{API}/mock-provider/payments/{payment['id']}/complete",
        data={"outcome": "paid"},
        expect=303,
        follow_redirects=False,
    )
    order = await c.get(f"{API}/orders/{order['id']}", customer)
    return order, order["merchant_orders"][0]
