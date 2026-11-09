import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PaySource(BaseModel):
    """Provider payment source.

    Moyasar: card data must be tokenised client-side with the publishable key; send
    ``{"type": "token", "token": "token_..."}`` (or applepay/samsungpay/stcpay sources).
    Mock: ``{"type": "mock", "outcome": "redirect" | "paid" | "failed"}``.
    """

    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=2, max_length=30)


class PayRequest(BaseModel):
    source: PaySource


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    merchant_order_id: uuid.UUID
    provider: str
    is_test: bool
    status: str
    amount: int
    refunded_amount: int
    currency: Literal["SAR"] = "SAR"
    payment_method: str | None
    transaction_url: str | None
    failure_reason: str | None
    paid_at: datetime | None
    created_at: datetime


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_type: str
    merchant_id: uuid.UUID | None
    recipient_id: str
    amount: int
    delivery_amount: int  # part of amount coming from the delivery charge
    is_fee_source: bool
    refundable: bool


class PaymentAdminOut(PaymentOut):
    merchant_id: uuid.UUID
    customer_user_id: uuid.UUID
    provider_payment_id: str | None
    fee: int | None
    fee_bearer: str
    provider_response: dict[str, Any] | None
    last_synced_at: datetime | None
    allocations: list[AllocationOut]


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    merchant_order_id: uuid.UUID
    amount: int
    merchant_portion: int
    platform_portion: int
    scope: str
    delivery_portion: int
    delivery_platform_portion: int
    currency: str
    status: str
    initiated_by: str
    reason: str
    failure_reason: str | None
    created_at: datetime
    completed_at: datetime | None


class RefundDecision(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class RefundCreate(BaseModel):
    amount: int | None = Field(default=None, gt=0)
    # AUTO: items first, then the delivery charge. DELIVERY refunds only the delivery charge.
    scope: Literal["AUTO", "ITEMS", "DELIVERY"] = "AUTO"
    reason: str = Field(min_length=3, max_length=2000)
    restock: bool = False


class ChargebackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    merchant_id: uuid.UUID
    amount: int
    merchant_portion: int
    platform_portion: int
    delivery_portion: int
    delivery_platform_portion: int
    status: str
    reason: str
    provider_reference: str
    opened_at: datetime
    resolved_at: datetime | None


class ChargebackCreate(BaseModel):
    payment_id: uuid.UUID
    amount: int = Field(gt=0)
    provider_reference: str = Field(min_length=3, max_length=100)
    reason: str = Field(default="", max_length=2000)


class ChargebackResolve(BaseModel):
    outcome: Literal["WON", "LOST"]


class WebhookEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    event_id: str
    event_type: str
    status: str
    attempts: int
    is_live: bool
    last_error: str | None
    created_at: datetime
    processed_at: datetime | None
