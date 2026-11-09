"""Immutable double-entry ledger.

Postings (all amounts in halalas, SAR only):

PAYMENT_CAPTURED   Dr PROVIDER_CLEARING  total
                   Cr MERCHANT_PAYABLE   merchant allocation, items part        [GOODS]
                   Cr MERCHANT_PAYABLE   merchant allocation, delivery part     [DELIVERY]
                   Cr PLATFORM_COMMISSION item commission                       [GOODS]
                   Cr DELIVERY_COMMISSION commission on the delivery fee        [DELIVERY]
                     (or DELIVERY_FEE_REVENUE when the platform receives the delivery fee)
PROCESSING_FEE     Dr PROCESSING_FEES    fee          (fee bearer: PLATFORM)
                   Cr PROVIDER_CLEARING  fee
REFUND/CHARGEBACK  the capture lines reversed for the refunded portion of each
                   component, Cr PROVIDER_CLEARING amount
SETTLEMENT         Dr MERCHANT_PAYABLE   amount       (only on verified bank transfer)
                   Cr PROVIDER_CLEARING  amount

Entries tied to a sale carry a ``component`` (GOODS / DELIVERY), so delivery money
stays identifiable inside the merchant's single payable account.

Each posting is unique per (source_type, source_id, transaction_type), so a
duplicated event can never post twice. A database trigger rejects unbalanced
transactions and any UPDATE/DELETE of ledger rows.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import case, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.money import Currency, ensure_currency
from app.modules.ledger.models import (
    MERCHANT_ACCOUNT_TYPES,
    AccountType,
    Direction,
    LedgerAccount,
    LedgerComponent,
    LedgerEntry,
    LedgerTransaction,
    LedgerTransactionType,
)


class UnbalancedTransaction(ValueError):
    pass


@dataclass(frozen=True)
class Line:
    account_type: AccountType
    direction: Direction
    amount: int
    merchant_id: uuid.UUID | None = None
    description: str = ""
    component: LedgerComponent | None = None


def delivery_platform_account(fee_recipient: str | None) -> AccountType:
    """Platform account for the platform's share of a delivery charge."""
    return AccountType.DELIVERY_FEE_REVENUE if fee_recipient == "PLATFORM" else AccountType.DELIVERY_COMMISSION


async def get_account(
    session: AsyncSession, account_type: AccountType, merchant_id: uuid.UUID | None, currency: str = "SAR"
) -> LedgerAccount:
    is_merchant = account_type in MERCHANT_ACCOUNT_TYPES
    if is_merchant != (merchant_id is not None):
        raise ValueError(f"{account_type} requires merchant_id={'set' if is_merchant else 'None'}")
    stmt = select(LedgerAccount).where(
        LedgerAccount.account_type == account_type.value, LedgerAccount.currency == currency
    )
    stmt = stmt.where(
        LedgerAccount.merchant_id == merchant_id if merchant_id else col(LedgerAccount.merchant_id).is_(None)
    )
    account = (await session.exec(stmt)).first()
    if account is not None:
        return account
    index_where = (
        col(LedgerAccount.merchant_id).is_not(None) if merchant_id else col(LedgerAccount.merchant_id).is_(None)
    )
    elements = ["merchant_id", "account_type", "currency"] if merchant_id else ["account_type", "currency"]
    await session.exec(
        insert(LedgerAccount)
        .values(id=uuid.uuid4(), merchant_id=merchant_id, account_type=account_type.value, currency=currency)
        .on_conflict_do_nothing(index_elements=elements, index_where=index_where)
    )
    account = (await session.exec(stmt)).first()
    assert account is not None
    return account


async def find_posting(
    session: AsyncSession, source_type: str, source_id: uuid.UUID, transaction_type: LedgerTransactionType
) -> LedgerTransaction | None:
    return (
        await session.exec(
            select(LedgerTransaction).where(
                LedgerTransaction.source_type == source_type,
                LedgerTransaction.source_id == source_id,
                LedgerTransaction.transaction_type == transaction_type.value,
            )
        )
    ).first()


async def post(
    session: AsyncSession,
    *,
    transaction_type: LedgerTransactionType,
    source_type: str,
    source_id: uuid.UUID,
    lines: list[Line],
    merchant_id: uuid.UUID | None,
    description: str,
    is_test: bool,
    currency: str = Currency.SAR.value,
) -> LedgerTransaction:
    """Post a balanced transaction idempotently. Returns the existing posting if any."""
    ensure_currency(currency)
    existing = await find_posting(session, source_type, source_id, transaction_type)
    if existing is not None:
        return existing
    lines = [line for line in lines if line.amount != 0]
    if any(line.amount < 0 for line in lines):
        raise UnbalancedTransaction("Ledger amounts must be positive.")
    debits = sum(line.amount for line in lines if line.direction == Direction.DEBIT)
    credits = sum(line.amount for line in lines if line.direction == Direction.CREDIT)
    if debits != credits or debits == 0:
        raise UnbalancedTransaction(f"Unbalanced ledger transaction: debits={debits} credits={credits}")
    transaction = LedgerTransaction(
        reference=f"{transaction_type.value}:{source_type}:{source_id}",
        transaction_type=transaction_type.value,
        source_type=source_type,
        source_id=source_id,
        merchant_id=merchant_id,
        description=description,
        is_test=is_test,
    )
    session.add(transaction)
    await session.flush()
    for line in lines:
        account = await get_account(session, line.account_type, line.merchant_id, currency)
        session.add(
            LedgerEntry(
                transaction_id=transaction.id,
                account_id=account.id,
                direction=line.direction.value,
                amount=line.amount,
                currency=currency,
                component=line.component.value if line.component else None,
                description=line.description,
            )
        )
    await session.flush()
    return transaction


_signed_credit = case((LedgerEntry.direction == Direction.CREDIT.value, LedgerEntry.amount), else_=-LedgerEntry.amount)


async def balance(session: AsyncSession, account_type: AccountType, merchant_id: uuid.UUID | None = None) -> int:
    """Credit-normal balance (credits minus debits) of an account; 0 if it does not exist."""
    stmt = (
        select(func.coalesce(func.sum(_signed_credit), 0))
        .select_from(LedgerEntry)
        .join(LedgerAccount, col(LedgerAccount.id) == col(LedgerEntry.account_id))
        .where(LedgerAccount.account_type == account_type.value)
    )
    stmt = stmt.where(
        LedgerAccount.merchant_id == merchant_id if merchant_id else col(LedgerAccount.merchant_id).is_(None)
    )
    return int((await session.exec(stmt)).first() or 0)


async def component_balance(
    session: AsyncSession,
    account_types: tuple[AccountType, ...],
    component: LedgerComponent,
    merchant_id: uuid.UUID | None = None,
) -> int:
    """Credit-normal balance of the entries of ``component`` in the given accounts."""
    stmt = (
        select(func.coalesce(func.sum(_signed_credit), 0))
        .select_from(LedgerEntry)
        .join(LedgerAccount, col(LedgerAccount.id) == col(LedgerEntry.account_id))
        .where(
            col(LedgerAccount.account_type).in_([a.value for a in account_types]),
            LedgerEntry.component == component.value,
        )
    )
    stmt = stmt.where(
        LedgerAccount.merchant_id == merchant_id if merchant_id else col(LedgerAccount.merchant_id).is_(None)
    )
    return int((await session.exec(stmt)).first() or 0)


async def merchant_payable(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    """Earned but not yet settled to the merchant's bank (pending settlement)."""
    return await balance(session, AccountType.MERCHANT_PAYABLE, merchant_id)


async def unbalanced_transactions(session: AsyncSession) -> list[uuid.UUID]:
    signed = case((LedgerEntry.direction == Direction.DEBIT.value, LedgerEntry.amount), else_=-LedgerEntry.amount)
    rows = await session.exec(
        select(col(LedgerEntry.transaction_id)).group_by(col(LedgerEntry.transaction_id)).having(func.sum(signed) != 0)
    )
    return list(rows.all())


async def trial_balance(session: AsyncSession) -> int:
    """Sum of all debits minus credits across the whole ledger. Always 0 when consistent."""
    signed = case((LedgerEntry.direction == Direction.DEBIT.value, LedgerEntry.amount), else_=-LedgerEntry.amount)
    return int((await session.exec(select(func.coalesce(func.sum(signed), 0)))).first() or 0)
