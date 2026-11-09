"""Merchant financial figures, all derived from payments, refunds, chargebacks,
settlements and the ledger (never from a stored balance field)."""

import uuid
from datetime import timedelta
from typing import Any

from pydantic import BaseModel
from sqlmodel import Date, cast, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from app.core.security import utcnow
from app.modules.admin.settings_service import DeliveryFinanceSettings
from app.modules.ledger import service as ledger
from app.modules.orders.models import MerchantOrder
from app.modules.payments.models import (
    CAPTURED_STATUSES,
    Chargeback,
    ChargebackStatus,
    FeeBearer,
    Payment,
    PaymentAllocation,
    RecipientType,
    Refund,
    RefundStatus,
)
from app.modules.settlements.models import Settlement, SettlementStatus


class FinancialSummary(BaseModel):
    """Delivery money is always reported on its own lines; ``platform_commission`` is
    commission on items only and ``delivery_commission`` is shown separately."""

    currency: str = "SAR"
    gross_sales: int  # everything customers paid (items + delivery, incl. VAT)
    product_sales: int  # gross_sales without delivery charges
    delivery_charges: int  # delivery fees incl. VAT paid by customers
    paid_orders: int
    platform_commission: int  # on items, net of reversals
    # The platform's share of delivery charges, net of reversals: the delivery commission
    # (0 unless configured), or the whole charge when the platform receives delivery fees.
    platform_delivery_share: int
    processing_fees_borne: int
    refunds: int
    delivery_refunds: int  # part of refunds + chargebacks that reversed delivery charges
    chargebacks: int
    net_earnings: int
    delivery_earnings: int  # part of net_earnings coming from delivery
    pending_settlement: int
    completed_settlements: int
    failed_settlements: int
    fee_bearer_note: str
    delivery_commission_note: str


class DailyPoint(BaseModel):
    date: str
    orders: int
    gross_sales: int


async def _sum(session: AsyncSession, stmt: SelectOfScalar[Any]) -> int:
    return int((await session.exec(stmt)).first() or 0)


async def summary(
    session: AsyncSession,
    merchant_id: uuid.UUID,
    fee_bearer: str,
    delivery_finance: DeliveryFinanceSettings | None = None,
) -> FinancialSummary:
    delivery_finance = delivery_finance or DeliveryFinanceSettings()
    captured = [s.value for s in CAPTURED_STATUSES]
    gross = await _sum(
        session,
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            col(Payment.merchant_id) == merchant_id, col(Payment.status).in_(captured)
        ),
    )
    paid_orders = await _sum(
        session,
        select(func.count(col(Payment.id))).where(
            col(Payment.merchant_id) == merchant_id, col(Payment.status).in_(captured)
        ),
    )

    def alloc(recipient: RecipientType, column: Any) -> SelectOfScalar[Any]:
        return (
            select(func.coalesce(func.sum(column), 0))
            .join(Payment, col(Payment.id) == col(PaymentAllocation.payment_id))
            .where(
                Payment.merchant_id == merchant_id,
                col(Payment.status).in_(captured),
                PaymentAllocation.recipient_type == recipient.value,
            )
        )

    merchant_alloc = await _sum(session, alloc(RecipientType.MERCHANT, PaymentAllocation.amount))
    platform_alloc = await _sum(session, alloc(RecipientType.PLATFORM, PaymentAllocation.amount))
    merchant_delivery = await _sum(session, alloc(RecipientType.MERCHANT, PaymentAllocation.delivery_amount))
    platform_delivery = await _sum(session, alloc(RecipientType.PLATFORM, PaymentAllocation.delivery_amount))

    def reversals(model: type[Refund] | type[Chargeback], status: str) -> Any:
        return select(  # type: ignore[call-overload]
            func.coalesce(func.sum(model.amount), 0),
            func.coalesce(func.sum(model.merchant_portion), 0),
            func.coalesce(func.sum(model.platform_portion), 0),
            func.coalesce(func.sum(model.delivery_portion), 0),
            func.coalesce(func.sum(model.delivery_platform_portion), 0),
        ).where(model.merchant_id == merchant_id, model.status == status)

    refund_row = (await session.exec(reversals(Refund, RefundStatus.SUCCEEDED.value))).one()
    cb_row = (await session.exec(reversals(Chargeback, ChargebackStatus.LOST.value))).one()
    delivery_reversed = int(refund_row[3]) + int(cb_row[3])
    delivery_platform_reversed = int(refund_row[4]) + int(cb_row[4])
    merchant_fees = await _sum(
        session,
        select(func.coalesce(func.sum(Payment.fee), 0)).where(
            Payment.merchant_id == merchant_id,
            col(Payment.status).in_(captured),
            Payment.fee_bearer == FeeBearer.MERCHANT.value,
        ),
    )
    completed = await _sum(
        session,
        select(func.coalesce(func.sum(Settlement.amount), 0)).where(
            Settlement.merchant_id == merchant_id, Settlement.status == SettlementStatus.COMPLETED.value
        ),
    )
    failed = await _sum(
        session,
        select(func.count(col(Settlement.id))).where(
            Settlement.merchant_id == merchant_id, Settlement.status == SettlementStatus.FAILED.value
        ),
    )
    net = merchant_alloc - int(refund_row[1]) - int(cb_row[1]) - merchant_fees
    platform_reversed = int(refund_row[2]) + int(cb_row[2])
    delivery_charges = merchant_delivery + platform_delivery
    if delivery_finance.commission_applies_to == "ITEMS_AND_DELIVERY":
        commission_note = (
            f"The platform charges {delivery_finance.delivery_commission_rate}% commission on delivery fees, "
            "shown separately from item commission."
        )
    else:
        commission_note = "No commission is charged on delivery fees; you keep the full delivery fee."
    return FinancialSummary(
        gross_sales=gross,
        product_sales=gross - delivery_charges,
        delivery_charges=delivery_charges,
        paid_orders=paid_orders,
        platform_commission=(platform_alloc - platform_delivery) - (platform_reversed - delivery_platform_reversed),
        platform_delivery_share=platform_delivery - delivery_platform_reversed,
        processing_fees_borne=merchant_fees,
        refunds=int(refund_row[0]),
        delivery_refunds=delivery_reversed,
        chargebacks=int(cb_row[0]),
        net_earnings=net,
        delivery_earnings=merchant_delivery - (delivery_reversed - delivery_platform_reversed),
        delivery_commission_note=commission_note,
        pending_settlement=await ledger.merchant_payable(session, merchant_id),
        completed_settlements=completed,
        failed_settlements=failed,
        fee_bearer_note=(
            "Payment processing fees are paid by the platform."
            if fee_bearer == FeeBearer.PLATFORM.value
            else "Payment processing fees are deducted from your proceeds and shown per payment."
        ),
    )


async def daily_sales(session: AsyncSession, merchant_id: uuid.UUID | None, days: int = 30) -> list[DailyPoint]:
    start = (utcnow() - timedelta(days=days - 1)).date()
    day = cast(func.timezone("Asia/Riyadh", MerchantOrder.paid_at), Date)
    stmt = (
        select(
            day.label("day"), func.count(col(MerchantOrder.id)), func.coalesce(func.sum(col(MerchantOrder.total)), 0)
        )
        .where(col(MerchantOrder.paid_at).is_not(None), day >= start)
        .group_by("day")
    )
    if merchant_id is not None:
        stmt = stmt.where(MerchantOrder.merchant_id == merchant_id)
    rows = {r[0]: (int(r[1]), int(r[2])) for r in (await session.exec(stmt)).all()}
    points = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        orders, gross = rows.get(d, (0, 0))
        points.append(DailyPoint(date=d.isoformat(), orders=orders, gross_sales=gross))
    return points
