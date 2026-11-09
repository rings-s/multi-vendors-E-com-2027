"""Cart and CartItem. Prices are never stored in the cart; they are recalculated."""

import uuid

from sqlmodel import CheckConstraint, Field, Index, Relationship, text

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class CartItem(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND quantity <= 999", name="quantity_range"),
        CheckConstraint(
            "(product_id IS NOT NULL AND service_id IS NULL) OR (product_id IS NULL AND service_id IS NOT NULL)",
            name="exactly_one_item",
        ),
        CheckConstraint("variant_id IS NULL OR product_id IS NOT NULL", name="variant_requires_product"),
        Index(
            "uq_cart_items_product",
            "cart_id",
            "product_id",
            unique=True,
            postgresql_where=text("product_id IS NOT NULL AND variant_id IS NULL"),
        ),
        Index(
            "uq_cart_items_variant",
            "cart_id",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
        Index(
            "uq_cart_items_service",
            "cart_id",
            "service_id",
            unique=True,
            postgresql_where=text("service_id IS NOT NULL"),
        ),
    )

    cart_id: uuid.UUID = Field(foreign_key="carts.id", ondelete="CASCADE", index=True)
    product_id: uuid.UUID | None = Field(default=None, foreign_key="products.id", ondelete="CASCADE")
    variant_id: uuid.UUID | None = Field(default=None, foreign_key="product_variants.id", ondelete="CASCADE")
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", ondelete="CASCADE")
    quantity: int


class Cart(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "carts"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True)
    currency: str = Field(default="SAR", max_length=3)

    items: list[CartItem] = Relationship(
        sa_relationship_kwargs={
            "lazy": "selectin",
            "cascade": "all, delete-orphan",
            "order_by": "CartItem.created_at",
        }
    )
