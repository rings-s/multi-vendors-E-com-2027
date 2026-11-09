"""Operational commands.

    python -m app.cli create-admin --email ops@example.com --name "Ops" [--super]
    python -m app.cli seed-dev

Administrator accounts are never created through the public API; the first
SUPER_ADMIN is created out of band with this command (password read from the
ADMIN_PASSWORD environment variable or prompted for).
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.security import utcnow
from app.database.session import dispose_engine, get_sessionmaker
from app.modules.auth import service as auth
from app.modules.auth.models import RoleName, User
from app.modules.stores.models import Store

DEMO_PASSWORD = "demo-password-123"  # noqa: S105 - development seed only
DEMO_CATEGORIES = (
    ("fashion", "Fashion", "أزياء", "PRODUCT"),
    ("perfumes", "Perfumes & Oud", "عطور وعود", "PRODUCT"),
    ("home", "Home & Living", "المنزل", "PRODUCT"),
    ("beauty-services", "Beauty Services", "خدمات التجميل", "SERVICE"),
    ("consulting", "Consulting", "استشارات", "SERVICE"),
)


async def create_admin(email: str, name: str, password: str, *, super_admin: bool) -> None:
    async with get_sessionmaker()() as session, session.begin():
        user = await auth.create_user(
            session,
            email=email,
            password=password,
            full_name=name,
            phone=None,
            roles=[RoleName.SUPER_ADMIN if super_admin else RoleName.ADMIN],
            preferred_language="ar",
        )
        user.email_verified_at = utcnow()
    print(f"Created {'SUPER_ADMIN' if super_admin else 'ADMIN'} {email}")


async def seed_dev() -> None:
    """Idempotent development data: categories, an admin, a customer and an approved
    demo merchant (mock payment account) with products and a service."""
    from app.integrations.payments.factory import get_payment_provider
    from app.modules.catalog import service as catalog
    from app.modules.catalog.models import Category
    from app.modules.catalog.schemas import ProductIn, ServiceIn
    from app.modules.merchants import service as merchants
    from app.modules.merchants.models import MerchantStatus
    from app.modules.merchants.schemas import BankAccountIn, MerchantRegisterRequest, PaymentOnboardingRequest

    settings = get_settings()
    if settings.is_production or not settings.mock_payments_enabled:
        sys.exit("seed-dev only runs outside production with PAYMENT_PROVIDER=mock.")
    provider = get_payment_provider()

    async with get_sessionmaker()() as session, session.begin():
        categories: dict[str, Category] = {}
        for index, (slug, name_en, name_ar, kind) in enumerate(DEMO_CATEGORIES):
            category = (await session.exec(select(Category).where(Category.slug == slug))).first()
            if category is None:
                category = Category(slug=slug, name_en=name_en, name_ar=name_ar, kind=kind, sort_order=index)
                session.add(category)
            categories[slug] = category
        await session.flush()

        if (await session.exec(select(User.id).where(User.email == "admin@example.com"))).first() is None:
            admin = await auth.create_user(
                session,
                email="admin@example.com",
                password=DEMO_PASSWORD,
                full_name="Platform Admin",
                phone=None,
                roles=[RoleName.SUPER_ADMIN],
            )
            admin.email_verified_at = utcnow()
        admin_id = (await session.exec(select(User.id).where(User.email == "admin@example.com"))).first()
        assert admin_id is not None

        if (await session.exec(select(User.id).where(User.email == "customer@example.com"))).first() is None:
            await auth.create_user(
                session,
                email="customer@example.com",
                password=DEMO_PASSWORD,
                full_name="Sara Al-Harbi",
                phone="+966500000001",
                roles=[RoleName.CUSTOMER],
            )

        if (await session.exec(select(User.id).where(User.email == "merchant@example.com"))).first() is None:
            _, merchant = await merchants.register_merchant(
                session,
                MerchantRegisterRequest(
                    owner_full_name="Faisal Al-Otaibi",
                    email="merchant@example.com",
                    password=DEMO_PASSWORD,
                    mobile="+966500000002",
                    business_name="Najd Oud Trading Est.",
                    store_name="Najd Oud",
                    store_slug="najd-oud",
                    category_id=categories["perfumes"].id,
                    business_description="Hand-blended oud and perfumes from Riyadh since 2010.",
                    city="Riyadh",
                    address={"region": "riyadh", "city": "Riyadh", "district": "Al Olaya", "postal_code": "12211"},
                    commercial_registration_number="1010000001",
                    vat_number="300000000000003",
                ),
            )
            await merchants.submit_application(session, merchant)
            await merchants.transition(
                session, merchant, MerchantStatus.APPROVED, actor_user_id=admin_id, reason="Seed data"
            )
            await merchants.start_payment_onboarding(
                session,
                merchant,
                PaymentOnboardingRequest(
                    bank_account=BankAccountIn(
                        beneficiary_name="Najd Oud Trading Est.", iban="SA0380000000608010167519"
                    ),
                    website="https://najd-oud.example",
                    owners_count=1,
                ),
                provider,
            )
            await merchants.submit_payment_onboarding(session, merchant, provider)
            store = await merchants.get_store(session, merchant.id)
            assert store is not None
            for title, price, discounted, stock in (
                ("Royal Cambodian Oud 3ml", 45000, None, 25),
                ("Rose Taifi Perfume 50ml", 32000, 27500, 40),
                ("Bakhoor Gift Box", 18000, None, 60),
            ):
                await catalog.create_product(
                    session,
                    merchant,
                    store,
                    ProductIn(
                        title=title,
                        description=f"{title} — demo product.",
                        sku=title.upper().replace(" ", "-")[:30],
                        price=price,
                        discounted_price=discounted,
                        category_id=categories["perfumes"].id,
                        status="ACTIVE",
                        stock_quantity=stock,
                    ),
                )
            await _seed_delivery(session, store)
            await catalog.create_service(
                session,
                merchant,
                store,
                ServiceIn(
                    title="Personal Fragrance Consultation",
                    description="A 45-minute consultation to design a signature scent.",
                    price=25000,
                    duration_minutes=45,
                    category_id=categories["consulting"].id,
                    status="ACTIVE",
                ),
            )
    print("Development seed data is ready (mock payments only).")
    print(f"  admin@example.com / customer@example.com / merchant@example.com : {DEMO_PASSWORD}")


async def _seed_delivery(session: AsyncSession, store: Store) -> None:
    """Demo delivery setup: fast delivery in Riyadh, slower elsewhere, and store pickup."""
    from app.modules.delivery import service as delivery
    from app.modules.delivery.schemas import DeliverySettingsIn, ZoneIn
    from app.modules.merchants.models import MerchantAddress

    for zone in (
        ZoneIn(
            name="Riyadh same day",
            region="riyadh",
            cities=["Riyadh", "الرياض"],
            fee=1500,
            free_delivery_threshold=30000,
            eta_min_minutes=120,
            eta_max_minutes=360,
        ),
        ZoneIn(name="Riyadh region", region="riyadh", fee=2500, eta_min_minutes=1440, eta_max_minutes=2880),
        ZoneIn(name="Saudi Arabia", fee=3500, eta_min_minutes=2880, eta_max_minutes=7200),
    ):
        await delivery.create_zone(session, store, zone)
    session.add(
        MerchantAddress(
            merchant_id=store.merchant_id,
            label="Al Olaya showroom",
            region="riyadh",
            city="Riyadh",
            district="Al Olaya",
            street="Olaya Street",
            building_number="7421",
            postal_code="12211",
            is_pickup_location=True,
            latitude=24.6907,
            longitude=46.6853,
        )
    )
    row = await delivery.get_settings(session, store)
    for key, value in (
        DeliverySettingsIn(
            delivery_enabled=True,
            pickup_enabled=True,
            pickup_preparation_minutes=60,
            delivery_policy="We deliver with our own drivers. Free same-day delivery in Riyadh above 300 SAR.",
        )
        .model_dump()
        .items()
    ):
        setattr(row, key, value)


async def _run(args: argparse.Namespace) -> None:
    try:
        if args.command == "create-admin":
            password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (min 10 chars): ")
            if len(password) < 10:
                sys.exit("Password must be at least 10 characters.")
            await create_admin(args.email, args.name, password, super_admin=args.super_admin)
        elif args.command == "seed-dev":
            await seed_dev()
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Create an administrator account.")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--super", dest="super_admin", action="store_true", help="Grant SUPER_ADMIN.")
    sub.add_parser("seed-dev", help="Load idempotent development seed data (mock payments only).")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
