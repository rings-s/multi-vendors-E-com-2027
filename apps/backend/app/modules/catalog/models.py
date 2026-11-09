"""Catalog: Category, Product, ProductImage, ProductVariant, Inventory, Service,
ServiceImage, Review."""

import uuid
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    BigInteger,
    CheckConstraint,
    Field,
    Index,
    Relationship,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)

from app.database.base import Timestamps, UUIDPrimaryKey


class CategoryKind(StrEnum):
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    BOTH = "BOTH"


class CatalogStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    BLOCKED = "BLOCKED"  # set by platform moderation


class ServiceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ServiceLocationType(StrEnum):
    AT_STORE = "AT_STORE"
    AT_CUSTOMER = "AT_CUSTOMER"
    ONLINE = "ONLINE"


class Category(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "categories"

    parent_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="RESTRICT")
    slug: str = Field(max_length=80, unique=True)
    name_en: str = Field(max_length=120)
    name_ar: str = Field(max_length=120)
    kind: str = Field(default=CategoryKind.BOTH.value, max_length=10)
    is_active: bool = True
    sort_order: int = 0


class ProductImage(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "product_images"

    product_id: uuid.UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    url: str = Field(max_length=500)
    alt: str = Field(default="", max_length=200)
    sort_order: int = 0


class ProductVariant(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "sku"),
        CheckConstraint("price IS NULL OR price > 0", name="price_positive"),
        CheckConstraint(
            "discounted_price IS NULL OR (discounted_price > 0 AND (price IS NULL OR discounted_price < price))",
            name="discount_valid",
        ),
    )

    product_id: uuid.UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    sku: str = Field(max_length=64)
    name: str = Field(max_length=200)
    options: dict[str, str] = Field(default_factory=dict, sa_type=JSONB)
    price: int | None = Field(default=None, sa_type=BigInteger)  # overrides product price when set
    discounted_price: int | None = Field(default=None, sa_type=BigInteger)
    is_active: bool = True


class Product(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("merchant_id", "sku"),
        UniqueConstraint("store_id", "slug"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint(
            "discounted_price IS NULL OR (discounted_price > 0 AND discounted_price < price)",
            name="discount_valid",
        ),
    )

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="RESTRICT", index=True)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="SET NULL")
    title: str = Field(max_length=200)
    slug: str = Field(max_length=120)
    description: str = Field(default="", sa_type=Text)
    sku: str = Field(max_length=64)
    price: int = Field(sa_type=BigInteger)  # halalas
    discounted_price: int | None = Field(default=None, sa_type=BigInteger)  # halalas
    status: str = Field(default=CatalogStatus.DRAFT.value, max_length=20, index=True)
    is_available: bool = True
    requires_shipping: bool = True
    weight_grams: int | None = None
    moderation_note: str | None = Field(default=None, sa_type=Text)
    is_featured: bool = False

    images: list[ProductImage] = Relationship(
        sa_relationship_kwargs={
            "lazy": "selectin",
            "order_by": "ProductImage.sort_order",
            "cascade": "all, delete-orphan",
        }
    )
    variants: list[ProductVariant] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"}
    )

    @property
    def effective_price(self) -> int:
        return self.discounted_price if self.discounted_price is not None else self.price


class Inventory(UUIDPrimaryKey, Timestamps, table=True):
    """Stock per product (variant_id NULL) or per variant.

    ``quantity_reserved`` holds stock reserved by unpaid checkouts; it is committed
    (subtracted from on-hand) when the payment is verified, and released otherwise.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("quantity_reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="reserved_le_on_hand"),
        Index(
            "uq_inventory_product_only",
            "product_id",
            unique=True,
            postgresql_where=text("variant_id IS NULL"),
        ),
        Index(
            "uq_inventory_variant",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
    )

    product_id: uuid.UUID = Field(foreign_key="products.id", ondelete="CASCADE", index=True)
    variant_id: uuid.UUID | None = Field(default=None, foreign_key="product_variants.id", ondelete="CASCADE")
    quantity_on_hand: int = 0
    quantity_reserved: int = 0

    @property
    def available(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved


class ServiceImage(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "service_images"

    service_id: uuid.UUID = Field(foreign_key="services.id", ondelete="CASCADE", index=True)
    url: str = Field(max_length=500)
    alt: str = Field(default="", max_length=200)
    sort_order: int = 0


class Service(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("store_id", "slug"),
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint(
            "discounted_price IS NULL OR (discounted_price > 0 AND discounted_price < price)",
            name="discount_valid",
        ),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
    )

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="RESTRICT", index=True)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="SET NULL")
    title: str = Field(max_length=200)
    slug: str = Field(max_length=120)
    description: str = Field(default="", sa_type=Text)
    price: int = Field(sa_type=BigInteger)
    discounted_price: int | None = Field(default=None, sa_type=BigInteger)
    duration_minutes: int
    availability: str = Field(default=ServiceAvailability.AVAILABLE.value, max_length=20)
    location_type: str = Field(default=ServiceLocationType.AT_STORE.value, max_length=20)
    location: str = Field(default="", max_length=300)
    status: str = Field(default=CatalogStatus.DRAFT.value, max_length=20, index=True)
    moderation_note: str | None = Field(default=None, sa_type=Text)
    is_featured: bool = False

    images: list[ServiceImage] = Relationship(
        sa_relationship_kwargs={
            "lazy": "selectin",
            "order_by": "ServiceImage.sort_order",
            "cascade": "all, delete-orphan",
        }
    )

    @property
    def effective_price(self) -> int:
        return self.discounted_price if self.discounted_price is not None else self.price


class ReviewStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    HIDDEN = "HIDDEN"


class Review(UUIDPrimaryKey, Timestamps, table=True):
    """A review by a customer who purchased from the store (merchant order)."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        UniqueConstraint("merchant_order_id", "customer_user_id"),
    )

    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="CASCADE", index=True)
    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="CASCADE")
    customer_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    rating: int = Field(sa_type=SmallInteger)
    comment: str = Field(default="", sa_type=Text)
    status: str = Field(default=ReviewStatus.PUBLISHED.value, max_length=20)
