"""Financial reconciliation against provider records and ledger self-checks.

* Payments: provider status/amount/refunded/fee compared with local records.
  With ``apply=True`` the provider's state is applied via the normal state machine.
* Ledger: every transaction balanced, trial balance zero, and each merchant's
  payable balance equal to the value derived from payments, refunds, chargebacks,
  merchant-borne fees and completed settlements.
* Delivery: delivery money reconciles on its own (see ``check_delivery``).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import aliased
from sqlmodel import and_, case, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.integrations.payments.base import PaymentProvider
from app.modules.admin.audit import record_audit
from app.modules.delivery.models import Delivery
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, FinancialReconciliation, LedgerComponent, ReconciliationStatus
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
from app.modules.payments.service import apply_provider_state
from app.modules.settlements.models import Settlement, SettlementStatus

MAX_PAYMENTS_PER_RUN = 500


async def expected_merchant_payable(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    captured = [s.value for s in CAPTURED_STATUSES]
    earned = (
        await session.exec(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
            .join(Payment, col(Payment.id) == col(PaymentAllocation.payment_id))
            .where(
                Payment.merchant_id == merchant_id,
                col(Payment.status).in_(captured),
                PaymentAllocation.recipient_type == RecipientType.MERCHANT.value,
            )
        )
    ).first()
    refunded = (
        await session.exec(
            select(func.coalesce(func.sum(Refund.merchant_portion), 0)).where(
                Refund.merchant_id == merchant_id, Refund.status == RefundStatus.SUCCEEDED.value
            )
        )
    ).first()
    charged_back = (
        await session.exec(
            select(func.coalesce(func.sum(Chargeback.merchant_portion), 0)).where(
                Chargeback.merchant_id == merchant_id, Chargeback.status == ChargebackStatus.LOST.value
            )
        )
    ).first()
    merchant_fees = (
        await session.exec(
            select(func.coalesce(func.sum(Payment.fee), 0)).where(
                Payment.merchant_id == merchant_id,
                col(Payment.status).in_(captured),
                Payment.fee_bearer == FeeBearer.MERCHANT.value,
            )
        )
    ).first()
    settled = (
        await session.exec(
            select(func.coalesce(func.sum(Settlement.amount), 0)).where(
                Settlement.merchant_id == merchant_id, Settlement.status == SettlementStatus.COMPLETED.value
            )
        )
    ).first()
    return int(earned or 0) - int(refunded or 0) - int(charged_back or 0) - int(merchant_fees or 0) - int(settled or 0)


def _reversed_delivery(model: type[Refund] | type[Chargeback], *, platform: bool) -> Any:
    """Delivery amount reversed by succeeded refunds / lost chargebacks (merchant or platform side)."""
    amount = model.delivery_platform_portion if platform else model.delivery_portion - model.delivery_platform_portion
    status = RefundStatus.SUCCEEDED.value if model is Refund else ChargebackStatus.LOST.value
    return select(func.coalesce(func.sum(amount), 0)).where(model.status == status)


async def _delivery_allocations(session: AsyncSession, recipient: RecipientType, merchant_id: uuid.UUID | None) -> int:
    stmt = (
        select(func.coalesce(func.sum(PaymentAllocation.delivery_amount), 0))
        .join(Payment, col(Payment.id) == col(PaymentAllocation.payment_id))
        .where(
            col(Payment.status).in_([s.value for s in CAPTURED_STATUSES]),
            PaymentAllocation.recipient_type == recipient.value,
        )
    )
    if merchant_id is not None:
        stmt = stmt.where(Payment.merchant_id == merchant_id)
    return int((await session.exec(stmt)).first() or 0)


async def expected_merchant_delivery(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    """Merchant's delivery earnings per payments and reversals (the DELIVERY part of its payable)."""
    earned = await _delivery_allocations(session, RecipientType.MERCHANT, merchant_id)
    reversed_total = 0
    for model in (Refund, Chargeback):
        stmt = _reversed_delivery(model, platform=False).where(model.merchant_id == merchant_id)
        reversed_total += int((await session.exec(stmt)).first() or 0)
    return earned - reversed_total


async def check_delivery(session: AsyncSession, merchant_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """Delivery money is reconcilable on its own:

    * each merchant's DELIVERY ledger entries equal its delivery allocations minus reversals;
    * the platform's delivery accounts equal the platform's delivery allocations minus reversals;
    * every captured payment's delivery allocations match the merchant order's delivery terms.
    """
    issues: list[dict[str, Any]] = []
    for merchant_id in merchant_ids:
        expected = await expected_merchant_delivery(session, merchant_id)
        actual = await ledger.component_balance(
            session, (AccountType.MERCHANT_PAYABLE,), LedgerComponent.DELIVERY, merchant_id
        )
        if expected != actual:
            issues.append(
                {"type": "merchant_delivery", "merchant_id": str(merchant_id), "expected": expected, "ledger": actual}
            )
    platform_expected = await _delivery_allocations(session, RecipientType.PLATFORM, None)
    for model in (Refund, Chargeback):
        platform_expected -= int((await session.exec(_reversed_delivery(model, platform=True))).first() or 0)
    platform_actual = await ledger.component_balance(
        session, (AccountType.DELIVERY_COMMISSION, AccountType.DELIVERY_FEE_REVENUE), LedgerComponent.DELIVERY
    )
    if platform_expected != platform_actual:
        issues.append({"type": "platform_delivery", "expected": platform_expected, "ledger": platform_actual})

    merchant_alloc = aliased(PaymentAllocation)
    platform_alloc = aliased(PaymentAllocation)
    platform_share = case(
        (
            col(MerchantOrder.delivery_fee_recipient) == "PLATFORM",
            MerchantOrder.delivery_fee + MerchantOrder.delivery_vat,
        ),
        else_=col(MerchantOrder.delivery_commission),
    )
    rows = await session.exec(
        select(col(Payment.id), col(MerchantOrder.number))
        .join(MerchantOrder, col(MerchantOrder.id) == col(Payment.merchant_order_id))
        .join(Delivery, col(Delivery.merchant_order_id) == col(MerchantOrder.id))
        .join(
            merchant_alloc,
            and_(
                merchant_alloc.payment_id == Payment.id, merchant_alloc.recipient_type == RecipientType.MERCHANT.value
            ),  # type: ignore[arg-type]
        )
        .join(
            platform_alloc,
            and_(
                platform_alloc.payment_id == Payment.id, platform_alloc.recipient_type == RecipientType.PLATFORM.value
            ),  # type: ignore[arg-type]
        )
        .where(
            col(Payment.status).in_([s.value for s in CAPTURED_STATUSES]),
            (platform_alloc.delivery_amount != platform_share)
            | (
                merchant_alloc.delivery_amount + platform_alloc.delivery_amount
                != MerchantOrder.delivery_fee + MerchantOrder.delivery_vat
            )
            | (platform_alloc.amount != MerchantOrder.commission_total + platform_alloc.delivery_amount),
        )
    )
    for payment_id, number in rows.all():
        issues.append({"type": "delivery_allocation", "payment_id": str(payment_id), "merchant_order": number})
    return issues


async def check_ledger(session: AsyncSession) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for transaction_id in await ledger.unbalanced_transactions(session):
        issues.append({"type": "unbalanced_transaction", "transaction_id": str(transaction_id)})
    trial = await ledger.trial_balance(session)
    if trial != 0:
        issues.append({"type": "trial_balance", "difference": trial})
    merchant_ids = list((await session.exec(select(Payment.merchant_id).distinct())).all())
    for merchant_id in merchant_ids:
        expected = await expected_merchant_payable(session, merchant_id)
        actual = await ledger.merchant_payable(session, merchant_id)
        if expected != actual:
            issues.append(
                {"type": "merchant_payable", "merchant_id": str(merchant_id), "expected": expected, "ledger": actual}
            )
    issues.extend(await check_delivery(session, merchant_ids))
    return issues


async def run_reconciliation(
    session: AsyncSession,
    provider: PaymentProvider,
    *,
    period_start: datetime | None,
    period_end: datetime | None,
    apply: bool,
    actor_user_id: uuid.UUID | None,
) -> FinancialReconciliation:
    run = FinancialReconciliation(
        provider=provider.name,
        scope="payments_and_ledger",
        period_start=period_start,
        period_end=period_end,
        status=ReconciliationStatus.RUNNING.value,
        details=[],
        triggered_by_user_id=actor_user_id,
    )
    session.add(run)
    await session.flush()

    stmt = select(Payment).where(Payment.provider == provider.name, col(Payment.provider_payment_id).is_not(None))
    if period_start:
        stmt = stmt.where(Payment.created_at >= period_start)
    if period_end:
        stmt = stmt.where(Payment.created_at < period_end)
    payments = (
        await session.exec(stmt.order_by(col(Payment.created_at)).limit(MAX_PAYMENTS_PER_RUN).with_for_update())
    ).all()

    details: list[dict[str, Any]] = []
    applied = 0
    for payment in payments:
        assert payment.provider_payment_id
        try:
            remote = await provider.retrieve_payment(payment.provider_payment_id)
        except AppError as exc:
            details.append({"type": "provider_lookup_failed", "payment_id": str(payment.id), "error": exc.message})
            continue
        differences: dict[str, dict[str, Any]] = {}
        if remote.status.value != payment.status:
            differences["status"] = {"local": payment.status, "provider": remote.status.value}
        if remote.amount != payment.amount:
            differences["amount"] = {"local": payment.amount, "provider": remote.amount}
        if remote.refunded_amount != payment.refunded_amount:
            differences["refunded"] = {"local": payment.refunded_amount, "provider": remote.refunded_amount}
        if remote.fee is not None and remote.fee != payment.fee:
            differences["fee"] = {"local": payment.fee, "provider": remote.fee}
        if differences:
            entry: dict[str, Any] = {
                "type": "payment_mismatch",
                "payment_id": str(payment.id),
                "differences": differences,
            }
            if apply:
                try:
                    async with session.begin_nested():
                        await apply_provider_state(session, payment, remote, provider)
                    applied += 1
                    entry["applied"] = True
                except AppError as exc:
                    entry["applied"] = False
                    entry["error"] = exc.message
            details.append(entry)

    details.extend(await check_ledger(session))
    run.checked_count = len(payments)
    run.mismatch_count = len(details)
    run.applied_updates = applied
    run.details = details
    run.status = ReconciliationStatus.COMPLETED.value
    run.completed_at = utcnow()
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="reconciliation.run",
        entity_type="financial_reconciliation",
        entity_id=run.id,
        after={"checked": run.checked_count, "mismatches": run.mismatch_count, "applied": applied},
    )
    await session.flush()
    return run
