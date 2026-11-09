import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.validators import SaudiMobile
from app.modules.delivery.schemas import DeliveryChoices, DeliveryOut, RefundScopeLiteral


class CheckoutRequest(DeliveryChoices):
    """``address_id`` is required when any store is delivered to; ``deliveries`` picks
    delivery or pickup per store (default: delivery when the store offers it)."""

    contact_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_phone: SaudiMobile
    contact_email: EmailStr | None = None
    delivery_instructions: str | None = Field(default=None, max_length=500)
    accept_terms: bool
    payment_method: Literal["card", "applepay", "stcpay", "mock"] = "card"


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_type: str
    product_id: uuid.UUID | None
    variant_id: uuid.UUID | None
    service_id: uuid.UUID | None
    title: str
    sku: str | None
    quantity: int
    unit_price: int
    unit_discount: int
    line_subtotal: int
    line_discount: int
    line_total: int


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    carrier: str
    tracking_number: str | None
    tracking_url: str | None
    status: str
    shipped_at: datetime | None
    delivered_at: datetime | None


class PaymentSummary(BaseModel):
    id: uuid.UUID
    status: str
    amount: int
    refunded_amount: int
    is_test: bool
    provider: str
    transaction_url: str | None
    failure_reason: str | None
    created_at: datetime


class MerchantOrderCustomerView(BaseModel):
    id: uuid.UUID
    number: str
    merchant_id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    store_slug: str
    status: str
    fulfillment_type: str
    items_subtotal: int
    discount_total: int
    delivery_method: str
    delivery_fee: int
    delivery_fee_waived: int
    delivery_vat: int
    vat_rate: Decimal
    vat_total: int
    total: int
    cancellation_status: str
    reservation_expires_at: datetime | None
    items: list[OrderItemOut]
    shipments: list[ShipmentOut]
    delivery: DeliveryOut | None
    payment: PaymentSummary | None
    refunded_amount: int


class OrderOut(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    currency: Literal["SAR"] = "SAR"
    items_subtotal: int
    discount_total: int
    delivery_total: int
    vat_total: int
    total: int
    contact_name: str
    contact_email: str
    contact_phone: str
    delivery_address: dict[str, str] | None
    created_at: datetime
    merchant_orders: list[MerchantOrderCustomerView]


class OrderListItem(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    total: int
    store_names: list[str]
    created_at: datetime


class CancellationRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class RefundRequestIn(BaseModel):
    amount: int | None = Field(default=None, gt=0, description="Halalas; omit for the full refundable amount.")
    scope: RefundScopeLiteral = "AUTO"
    reason: str = Field(min_length=3, max_length=2000)


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_order_id: uuid.UUID | None
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


# -- merchant views -------------------------------------------------------------------


class MerchantOrderMerchantView(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    number: str
    order_number: str
    status: str
    fulfillment_type: str
    customer_name: str
    customer_phone: str
    delivery_address: dict[str, str] | None
    items_subtotal: int
    discount_total: int
    delivery_method: str
    delivery_fee: int
    delivery_fee_waived: int
    delivery_vat: int
    delivery_fee_recipient: str | None
    delivery_cost_bearer: str | None
    vat_total: int
    total: int
    commission_total: int  # commission on items only
    delivery_commission: int  # commission on the delivery fee (separate, 0 unless configured)
    merchant_net: int
    merchant_delivery_share: int  # part of merchant_net coming from the delivery charge
    cancellation_status: str
    cancellation_reason: str | None
    merchant_note: str | None
    items: list[OrderItemOut]
    shipments: list[ShipmentOut]
    delivery: DeliveryOut | None
    payment: PaymentSummary | None
    refunded_amount: int
    created_at: datetime
    paid_at: datetime | None


class FulfillmentUpdate(BaseModel):
    status: Literal["ACCEPTED", "PROCESSING", "SHIPPED", "DELIVERED", "COMPLETED"]
    note: str | None = Field(default=None, max_length=2000)
    carrier: str | None = Field(default=None, max_length=100)
    tracking_number: str | None = Field(default=None, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")


class RejectOrder(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class CancellationDecision(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)
