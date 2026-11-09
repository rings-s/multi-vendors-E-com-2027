"""Commerce: Order, MerchantOrder, OrderItem, Shipment, OrderStatusHistory.

An ``Order`` is what the customer checks out. It is split into one ``MerchantOrder``
per merchant (a "checkout group"); each merchant order is paid by its own payment
transaction so its allocation can always be reconciled independently.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger, CheckConstraint, Field, Relationship, Text, UniqueConstraint

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"  # mixed final states (e.g. some refunded, some fulfilled)


class MerchantOrderStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class FulfillmentType(StrEnum):
    PHYSICAL = "PHYSICAL"
    SERVICE = "SERVICE"


class ItemType(StrEnum):
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"


class InventoryState(StrEnum):
    NONE = "NONE"
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"


class CancellationStatus(StrEnum):
    NONE = "NONE"
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Order(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("customer_user_id", "idempotency_key"),
        CheckConstraint("total >= 0", name="total_non_negative"),
        CheckConstraint(
            "total = items_subtotal - discount_total + delivery_total + vat_total", name="total_consistent"
        ),
    )

    number: str = Field(max_length=30, unique=True)
    customer_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    idempotency_key: str = Field(max_length=100)
    status: str = Field(default=OrderStatus.PENDING_PAYMENT.value, max_length=30, index=True)
    currency: str = Field(default="SAR", max_length=3)
    items_subtotal: int = Field(sa_type=BigInteger)
    discount_total: int = Field(sa_type=BigInteger)
    delivery_total: int = Field(sa_type=BigInteger)  # sum of the merchant orders' delivery fees (excl. VAT)
    vat_total: int = Field(sa_type=BigInteger)
    total: int = Field(sa_type=BigInteger)
    contact_name: str = Field(max_length=200)
    contact_email: str = Field(max_length=320)
    contact_phone: str = Field(max_length=20)
    delivery_address: dict[str, str] | None = Field(default=None, sa_type=JSONB)
    terms_accepted_at: datetime

    merchant_orders: list["MerchantOrder"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"lazy": "selectin", "order_by": "MerchantOrder.number"},
    )


class OrderItem(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price > 0 AND unit_discount >= 0 AND unit_discount < unit_price", name="price_valid"),
        CheckConstraint("line_subtotal = unit_price * quantity", name="subtotal_consistent"),
        CheckConstraint("line_discount = unit_discount * quantity", name="discount_consistent"),
        CheckConstraint("line_total = line_subtotal - line_discount", name="total_consistent"),
        CheckConstraint("commission_amount >= 0 AND commission_amount <= line_total", name="commission_range"),
        CheckConstraint(
            "(item_type = 'PRODUCT' AND product_id IS NOT NULL) OR (item_type = 'SERVICE' AND service_id IS NOT NULL)",
            name="item_reference",
        ),
    )

    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", index=True)
    item_type: str = Field(max_length=20)
    product_id: uuid.UUID | None = Field(default=None, foreign_key="products.id", ondelete="RESTRICT")
    variant_id: uuid.UUID | None = Field(default=None, foreign_key="product_variants.id", ondelete="RESTRICT")
    service_id: uuid.UUID | None = Field(default=None, foreign_key="services.id", ondelete="RESTRICT")
    category_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="SET NULL")
    title: str = Field(max_length=300)
    sku: str | None = Field(default=None, max_length=64)
    requires_shipping: bool = False
    unit_price: int = Field(sa_type=BigInteger)
    unit_discount: int = Field(sa_type=BigInteger)
    quantity: int
    line_subtotal: int = Field(sa_type=BigInteger)
    line_discount: int = Field(sa_type=BigInteger)
    line_total: int = Field(sa_type=BigInteger)
    # Commission snapshot: rate changes never affect existing orders.
    commission_rule_id: uuid.UUID | None = Field(default=None, foreign_key="commission_rules.id", ondelete="RESTRICT")
    commission_rate_type: str = Field(max_length=20)
    commission_rate: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)
    commission_fixed: int | None = Field(default=None, sa_type=BigInteger)
    commission_amount: int = Field(sa_type=BigInteger)


class ShipmentStatus(StrEnum):
    PENDING = "PENDING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"


class Shipment(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "shipments"

    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", index=True)
    carrier: str = Field(default="", max_length=100)
    tracking_number: str | None = Field(default=None, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default=ShipmentStatus.PENDING.value, max_length=20)
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None


class MerchantOrder(UUIDPrimaryKey, Timestamps, table=True):
    """One merchant's part of an order, with its full financial snapshot.

    Delivery money is always explicit and never folded into item figures:

    * ``delivery_fee`` (excl. VAT) and ``delivery_vat`` (part of ``vat_total``) are what
      the customer pays for delivery; ``delivery_fee_waived`` is a fee waived by a
      free-delivery threshold and borne by ``delivery_cost_bearer``.
    * ``commission_total`` is commission on items only; ``delivery_commission`` is the
      separate commission on the delivery fee (0 unless the platform is configured to
      charge it).
    * When ``delivery_fee_recipient`` is PLATFORM, the delivery charge goes to the
      platform and is excluded from ``merchant_net``.
    """

    __tablename__ = "merchant_orders"
    __table_args__ = (
        CheckConstraint(
            "items_subtotal >= 0 AND discount_total >= 0 AND delivery_fee >= 0 AND vat_total >= 0"
            " AND delivery_vat >= 0 AND delivery_vat <= vat_total AND delivery_fee_waived >= 0",
            name="amounts_non_negative",
        ),
        CheckConstraint("total = items_subtotal - discount_total + delivery_fee + vat_total", name="total_consistent"),
        CheckConstraint(
            "commission_total >= 0 AND delivery_commission >= 0 AND delivery_commission <= delivery_fee"
            " AND commission_total + delivery_commission <= total",
            name="commission_range",
        ),
        CheckConstraint(
            "merchant_net = total - commission_total - delivery_commission"
            " - CASE WHEN delivery_fee_recipient = 'PLATFORM' THEN delivery_fee + delivery_vat ELSE 0 END",
            name="net_consistent",
        ),
        CheckConstraint("delivery_method IN ('NONE', 'DELIVERY', 'PICKUP')", name="delivery_method_valid"),
        CheckConstraint(
            "(delivery_method = 'NONE') = (delivery_fee_recipient IS NULL AND delivery_cost_bearer IS NULL)",
            name="delivery_terms_recorded",
        ),
        CheckConstraint(
            "delivery_method = 'DELIVERY' OR (delivery_fee = 0 AND delivery_vat = 0 AND delivery_fee_waived = 0)",
            name="delivery_fee_requires_delivery",
        ),
        CheckConstraint(
            "delivery_fee_recipient IS DISTINCT FROM 'PLATFORM' OR delivery_commission = 0",
            name="delivery_commission_merchant_only",
        ),
    )

    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="RESTRICT")
    customer_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    number: str = Field(max_length=40, unique=True)
    status: str = Field(default=MerchantOrderStatus.PENDING_PAYMENT.value, max_length=30, index=True)
    fulfillment_type: str = Field(max_length=20)
    currency: str = Field(default="SAR", max_length=3)
    items_subtotal: int = Field(sa_type=BigInteger)
    discount_total: int = Field(sa_type=BigInteger)
    delivery_method: str = Field(default="NONE", max_length=20)
    delivery_fee: int = Field(sa_type=BigInteger)  # charged to the customer, excl. VAT
    delivery_fee_waived: int = Field(default=0, sa_type=BigInteger)  # free-delivery threshold
    delivery_vat: int = Field(default=0, sa_type=BigInteger)  # VAT on the delivery fee (part of vat_total)
    delivery_fee_recipient: str | None = Field(default=None, max_length=20)  # MERCHANT | PLATFORM
    delivery_cost_bearer: str | None = Field(default=None, max_length=20)  # MERCHANT | PLATFORM | CUSTOMER
    vat_rate: Decimal = Field(max_digits=5, decimal_places=2)
    vat_total: int = Field(sa_type=BigInteger)
    total: int = Field(sa_type=BigInteger)
    commission_total: int = Field(sa_type=BigInteger)  # commission on items only
    delivery_commission: int = Field(default=0, sa_type=BigInteger)
    delivery_commission_rate: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)
    merchant_net: int = Field(sa_type=BigInteger)
    inventory_state: str = Field(default=InventoryState.NONE.value, max_length=20)
    reservation_expires_at: datetime | None = Field(default=None, index=True)
    paid_at: datetime | None = None
    accepted_at: datetime | None = None
    fulfilled_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_status: str = Field(default=CancellationStatus.NONE.value, max_length=20)
    cancellation_reason: str | None = Field(default=None, sa_type=Text)
    cancellation_requested_at: datetime | None = None
    merchant_note: str | None = Field(default=None, sa_type=Text)

    order: Order = Relationship(back_populates="merchant_orders", sa_relationship_kwargs={"lazy": "selectin"})
    items: list[OrderItem] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "order_by": "OrderItem.created_at"}
    )
    shipments: list[Shipment] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "order_by": "Shipment.created_at"}
    )

    @property
    def delivery_gross(self) -> int:
        """What the customer pays for delivery (fee + VAT on it)."""
        return self.delivery_fee + self.delivery_vat

    @property
    def goods_gross(self) -> int:
        """What the customer pays for items (after discounts, incl. their VAT)."""
        return self.total - self.delivery_gross

    @property
    def platform_delivery_share(self) -> int:
        """Delivery money going to the platform (delivery commission or the platform's own fee)."""
        if self.delivery_fee_recipient == "PLATFORM":
            return self.delivery_gross
        return self.delivery_commission

    @property
    def merchant_delivery_share(self) -> int:
        return self.delivery_gross - self.platform_delivery_share


class OrderStatusHistory(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "order_status_history"

    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT", index=True)
    merchant_order_id: uuid.UUID | None = Field(
        default=None, foreign_key="merchant_orders.id", ondelete="RESTRICT", index=True
    )
    from_status: str | None = Field(default=None, max_length=30)
    to_status: str = Field(max_length=30)
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    note: str | None = Field(default=None, sa_type=Text)
