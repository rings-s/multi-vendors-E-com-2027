"""Direct database assertions for financial invariants."""

import uuid
from typing import Any

from sqlmodel import func, select

from app.database.session import get_sessionmaker
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, LedgerEntry, LedgerTransaction


async def merchant_payable(merchant_id: str) -> int:
    async with get_sessionmaker()() as session:
        return await ledger.merchant_payable(session, uuid.UUID(merchant_id))


async def ledger_postings(source_id: str) -> list[dict[str, Any]]:
    """All ledger transactions (with entries) posted for a source record."""
    async with get_sessionmaker()() as session:
        rows = await session.exec(
            select(LedgerTransaction)
            .where(LedgerTransaction.source_id == uuid.UUID(source_id))
            .order_by(LedgerTransaction.created_at)
        )
        return [
            {
                "type": t.transaction_type,
                "entries": [(e.direction, e.amount) for e in t.entries],
                "is_test": t.is_test,
            }
            for t in rows.all()
        ]


async def merchant_ledger_count(merchant_id: str) -> int:
    async with get_sessionmaker()() as session:
        return int(
            (
                await session.exec(
                    select(func.count())
                    .select_from(LedgerTransaction)
                    .where(LedgerTransaction.merchant_id == uuid.UUID(merchant_id))
                )
            ).first()
            or 0
        )


async def assert_ledger_consistent() -> None:
    async with get_sessionmaker()() as session:
        assert await ledger.unbalanced_transactions(session) == []
        assert await ledger.trial_balance(session) == 0
        negative = (
            await session.exec(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.amount <= 0))
        ).first()
        assert negative == 0


async def ledger_lines(source_id: str) -> list[tuple[str, str, int, str | None]]:
    """(account_type, direction, amount, component) of every entry posted for a source record."""
    from app.modules.ledger.models import LedgerAccount

    async with get_sessionmaker()() as session:
        rows = await session.exec(
            select(LedgerAccount.account_type, LedgerEntry.direction, LedgerEntry.amount, LedgerEntry.component)
            .join(LedgerEntry, LedgerEntry.account_id == LedgerAccount.id)  # type: ignore[arg-type]
            .join(LedgerTransaction, LedgerTransaction.id == LedgerEntry.transaction_id)  # type: ignore[arg-type]
            .where(LedgerTransaction.source_id == uuid.UUID(source_id))
        )
        return sorted((str(a), str(d), int(m), c) for a, d, m, c in rows.all())


async def reconciliation_issues() -> list[dict[str, Any]]:
    """Ledger/delivery self-checks of the reconciliation (no provider calls)."""
    from app.modules.payments.reconciliation import check_ledger

    async with get_sessionmaker()() as session:
        return await check_ledger(session)


async def platform_commission_balance() -> int:
    async with get_sessionmaker()() as session:
        return await ledger.balance(session, AccountType.PLATFORM_COMMISSION)


async def execute(sql: str, **params: Any) -> Any:
    from sqlmodel import text

    async with get_sessionmaker()() as session, session.begin():
        return (await session.exec(text(sql), params=params)).all()
