import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.cart.pricing import MerchantGroup, PricedLine, Quote
from app.modules.delivery.schemas import DeliveryOptionOut


class CartItemAdd(BaseModel):
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    quantity: int = Field(default=1, ge=1, le=999)

    @model_validator(mode="after")
    def _one(self) -> "CartItemAdd":
        if (self.product_id is None) == (self.service_id is None):
            raise ValueError("Provide exactly one of product_id or service_id.")
        if self.variant_id and not self.product_id:
            raise ValueError("variant_id requires product_id.")
        return self


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=999)


class QuoteLineOut(BaseModel):
    cart_item_id: uuid.UUID | None
    item_type: str
    product_id: uuid.UUID | None
    variant_id: uuid.UUID | None
    service_id: uuid.UUID | None
    title: str
    sku: str | None
    image_url: str | None
    quantity: int
    unit_price: int
    unit_discount: int
    line_subtotal: int
    line_discount: int
    line_total: int
    available_quantity: int | None
    issues: list[str]


class QuoteGroupOut(BaseModel):
    merchant_id: uuid.UUID
    store_id: uuid.UUID
    store_name: str
    store_slug: str
    fulfillment_type: str
    requires_delivery: bool
    lines: list[QuoteLineOut]
    items_subtotal: int
    discount_total: int
    delivery_method: Literal["NONE", "DELIVERY", "PICKUP"]
    delivery_fee: int  # excl. VAT
    delivery_fee_waived: int
    delivery_vat: int
    # True while the fee cannot be priced yet (no address / pickup point chosen).
    delivery_pending: bool
    delivery: DeliveryOptionOut | None  # the chosen option
    delivery_options: list[DeliveryOptionOut]
    vat_rate: Decimal
    vat_total: int
    total: int
    can_checkout: bool
    issues: list[str]


class QuoteOut(BaseModel):
    currency: Literal["SAR"] = "SAR"
    groups: list[QuoteGroupOut]
    items_subtotal: int
    discount_total: int
    delivery_total: int
    vat_total: int
    total: int
    requires_delivery: bool
    needs_address: bool
    can_checkout: bool
    item_count: int


def _line_out(line: PricedLine) -> QuoteLineOut:
    return QuoteLineOut(
        cart_item_id=line.input.cart_item_id,
        item_type=line.item_type.value,
        product_id=line.input.product_id,
        variant_id=line.input.variant_id,
        service_id=line.input.service_id,
        title=line.title,
        sku=line.sku,
        image_url=line.image_url,
        quantity=line.quantity,
        unit_price=line.unit_price,
        unit_discount=line.unit_discount,
        line_subtotal=line.line_subtotal,
        line_discount=line.line_discount,
        line_total=line.line_total,
        available_quantity=line.available_quantity,
        issues=line.issues,
    )


def _group_out(group: MerchantGroup) -> QuoteGroupOut:
    delivery = group.delivery
    return QuoteGroupOut(
        merchant_id=group.merchant.id,
        store_id=group.store.id,
        store_name=group.store.name,
        store_slug=group.store.slug,
        fulfillment_type=group.fulfillment_type.value,
        requires_delivery=group.requires_delivery,
        lines=[_line_out(line) for line in group.lines],
        items_subtotal=group.items_subtotal,
        discount_total=group.discount_total,
        delivery_method=delivery.method.value,  # type: ignore[arg-type]
        delivery_fee=delivery.charge.fee,
        delivery_fee_waived=delivery.charge.fee_waived,
        delivery_vat=delivery.charge.vat,
        delivery_pending=delivery.pending,
        delivery=DeliveryOptionOut.of(delivery.quote) if delivery.quote else None,
        delivery_options=[DeliveryOptionOut.of(q) for q in delivery.options],
        vat_rate=group.vat_rate,
        vat_total=group.vat_total,
        total=group.total,
        can_checkout=group.can_checkout,
        issues=group.issues,
    )


def quote_out(quote: Quote) -> QuoteOut:
    return QuoteOut(
        groups=[_group_out(g) for g in quote.groups],
        items_subtotal=quote.items_subtotal,
        discount_total=quote.discount_total,
        delivery_total=quote.delivery_total,
        vat_total=quote.vat_total,
        total=quote.total,
        requires_delivery=quote.requires_delivery,
        needs_address=quote.needs_address,
        can_checkout=quote.can_checkout,
        item_count=sum(line.quantity for g in quote.groups for line in g.lines),
    )
