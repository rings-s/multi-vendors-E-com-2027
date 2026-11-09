"""Settlements: verified bank transfers of merchant earnings.

There is no withdrawal function: the provider settles automatically. A settlement
is recorded only from verified provider data (webhook + provider lookup, or a
provider API lookup) or from an audited reconciliation entry made by a
super-administrator against the provider's records.
"""

import uuid
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.money import CurrencyMismatch, ensure_currency
from app.core.security import utcnow
from app.integrations.payments.base import PaymentProvider, ProviderSettlement
from app.modules.admin.audit import record_audit
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, Direction, LedgerTransactionType
from app.modules.merchants.models import Merchant, MerchantPaymentAccount
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.settlements.models import ConfirmationSource, Settlement, SettlementStatus


async def _complete(
    session: AsyncSession, settlement: Settlement, *, source: ConfirmationSource, reference: str, completed_at: datetime
) -> None:
    settlement.status = SettlementStatus.COMPLETED.value
    settlement.completed_at = completed_at
    settlement.confirmation_source = source.value
    settlement.confirmation_reference = reference
    await session.flush()
    await ledger.post(
        session,
        transaction_type=LedgerTransactionType.SETTLEMENT,
        source_type="settlement",
        source_id=settlement.id,
        merchant_id=settlement.merchant_id,
        description=f"Settlement {settlement.provider_settlement_id} transferred to bank",
        is_test=settlement.is_test,
        lines=[
            ledger.Line(AccountType.MERCHANT_PAYABLE, Direction.DEBIT, settlement.amount, settlement.merchant_id),
            ledger.Line(AccountType.PROVIDER_CLEARING, Direction.CREDIT, settlement.amount),
        ],
    )
    merchant = await session.get(Merchant, settlement.merchant_id)
    if merchant is not None:
        await notify(
            session, merchant.owner_user_id, NotificationType.SETTLEMENT_COMPLETED, {"amount": settlement.amount}
        )


async def record_provider_settlement(
    session: AsyncSession,
    provider: PaymentProvider,
    remote: ProviderSettlement,
    *,
    source: ConfirmationSource,
    reference: str,
) -> Settlement:
    try:
        ensure_currency(remote.currency)
    except CurrencyMismatch as exc:
        raise ValidationFailed("Settlement currency is not SAR; conversion is never performed.") from exc
    account = (
        await session.exec(
            select(MerchantPaymentAccount).where(
                MerchantPaymentAccount.provider == provider.name,
                MerchantPaymentAccount.recipient_id == remote.recipient_id,
            )
        )
    ).first()
    if account is None:
        raise NotFound(f"No merchant is linked to recipient {remote.recipient_id}.")
    settlement = (
        await session.exec(
            select(Settlement)
            .where(
                Settlement.provider == provider.name, Settlement.provider_settlement_id == remote.provider_settlement_id
            )
            .with_for_update()
        )
    ).first()
    if settlement is None:
        settlement = Settlement(
            merchant_id=account.merchant_id,
            provider=provider.name,
            provider_settlement_id=remote.provider_settlement_id,
            amount=remote.amount,
            currency=remote.currency,
            status=SettlementStatus.PROCESSING.value,
            is_test=provider.is_test,
            initiated_at=utcnow(),
            provider_details=remote.raw,
        )
        session.add(settlement)
        await session.flush()
    elif settlement.amount != remote.amount:
        raise ValidationFailed("Settlement amount differs from the provider record.", code="settlement_mismatch")

    if settlement.status == SettlementStatus.COMPLETED.value:
        return settlement  # idempotent
    if remote.status == "COMPLETED":
        if remote.completed_at is None:
            raise ValidationFailed("Provider confirmation lacks a completion time.")
        await _complete(session, settlement, source=source, reference=reference, completed_at=remote.completed_at)
    elif remote.status == "FAILED" and settlement.status != SettlementStatus.FAILED.value:
        settlement.status = SettlementStatus.FAILED.value
        settlement.failure_reason = remote.failure_reason or "Transfer failed"
        merchant = await session.get(Merchant, settlement.merchant_id)
        if merchant is not None:
            await notify(
                session,
                merchant.owner_user_id,
                NotificationType.SETTLEMENT_FAILED,
                {"amount": settlement.amount, "reason": settlement.failure_reason},
            )
    await session.flush()
    return settlement


async def record_reconciled_settlement(
    session: AsyncSession,
    provider: PaymentProvider,
    *,
    merchant_id: uuid.UUID,
    amount: int,
    provider_settlement_id: str,
    completed_at: datetime,
    evidence_reference: str,
    actor_user_id: uuid.UUID,
    ip: str | None,
) -> Settlement:
    """Record a transfer confirmed in the provider's records (audited reconciliation).

    When the provider exposes a settlement lookup, the provider's record is used
    instead of the administrator's input.
    """
    if provider.capabilities.supports_settlement_lookup:
        remote = await provider.get_settlement(provider_settlement_id)
        settlement = await record_provider_settlement(
            session, provider, remote, source=ConfirmationSource.PROVIDER_API, reference=provider_settlement_id
        )
        await record_audit(
            session,
            actor_user_id=actor_user_id,
            action="settlement.reconciled",
            entity_type="settlement",
            entity_id=settlement.id,
            after={
                "merchant_id": str(settlement.merchant_id),
                "amount": settlement.amount,
                "status": settlement.status,
                "provider_settlement_id": provider_settlement_id,
                "evidence_reference": evidence_reference,
                "source": ConfirmationSource.PROVIDER_API.value,
            },
            ip_address=ip,
        )
        return settlement
    merchant = await session.get(Merchant, merchant_id)
    if merchant is None:
        raise NotFound("Merchant not found.")
    if (
        await session.exec(
            select(Settlement.id).where(
                Settlement.provider == provider.name, Settlement.provider_settlement_id == provider_settlement_id
            )
        )
    ).first():
        raise Conflict("This provider settlement is already recorded.", code="settlement_exists")
    pending = await ledger.merchant_payable(session, merchant_id)
    if amount <= 0 or amount > pending:
        raise ValidationFailed(
            "Settlement amount exceeds the merchant's pending settlement balance.",
            code="settlement_exceeds_pending",
            details={"pending": pending},
        )
    if completed_at > utcnow():
        raise ValidationFailed("Completion time cannot be in the future.")
    settlement = Settlement(
        merchant_id=merchant_id,
        provider=provider.name,
        provider_settlement_id=provider_settlement_id,
        amount=amount,
        currency="SAR",
        status=SettlementStatus.PROCESSING.value,
        is_test=provider.is_test,
        initiated_at=completed_at,
        provider_details={"evidence_reference": evidence_reference},
    )
    session.add(settlement)
    await session.flush()
    await _complete(
        session,
        settlement,
        source=ConfirmationSource.ADMIN_RECONCILIATION,
        reference=evidence_reference,
        completed_at=completed_at,
    )
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="settlement.reconciled",
        entity_type="settlement",
        entity_id=settlement.id,
        after={
            "merchant_id": str(merchant_id),
            "amount": amount,
            "provider_settlement_id": provider_settlement_id,
            "evidence_reference": evidence_reference,
        },
        ip_address=ip,
    )
    return settlement
