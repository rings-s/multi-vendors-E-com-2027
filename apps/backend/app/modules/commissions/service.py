"""Commission rules: resolution, calculation and history-preserving changes.

Resolution order for a sold line: merchant-specific rule > category-specific rule
(nearest category up the tree) > global rule, each evaluated at the order time.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement
from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict, ValidationFailed
from app.core.money import percentage_of
from app.core.security import utcnow
from app.modules.admin.audit import record_audit
from app.modules.catalog.service import category_ancestors
from app.modules.commissions.models import CommissionRateType, CommissionRule, CommissionScope


@dataclass(frozen=True)
class LineCommission:
    rule_id: uuid.UUID
    rate_type: CommissionRateType
    rate: Decimal | None
    fixed: int | None
    amount: int


def _active_at(at: datetime) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    return (
        col(CommissionRule.effective_from) <= at,
        or_(col(CommissionRule.effective_to).is_(None), col(CommissionRule.effective_to) > at),
    )


async def resolve_rule(
    session: AsyncSession, *, merchant_id: uuid.UUID, category_id: uuid.UUID | None, at: datetime
) -> CommissionRule:
    rule = (
        await session.exec(
            select(CommissionRule).where(
                CommissionRule.scope == CommissionScope.MERCHANT.value,
                CommissionRule.merchant_id == merchant_id,
                *_active_at(at),
            )
        )
    ).first()
    if rule is not None:
        return rule
    if category_id is not None:
        for cat_id in await category_ancestors(session, category_id):
            rule = (
                await session.exec(
                    select(CommissionRule).where(
                        CommissionRule.scope == CommissionScope.CATEGORY.value,
                        CommissionRule.category_id == cat_id,
                        *_active_at(at),
                    )
                )
            ).first()
            if rule is not None:
                return rule
    rule = (
        await session.exec(
            select(CommissionRule).where(CommissionRule.scope == CommissionScope.GLOBAL.value, *_active_at(at))
        )
    ).first()
    if rule is None:
        raise ValidationFailed("No commission configuration is in effect.", code="commission_not_configured")
    return rule


def calculate(rule: CommissionRule, *, line_total: int, quantity: int) -> LineCommission:
    rate_type = CommissionRateType(rule.rate_type)
    if rate_type == CommissionRateType.PERCENTAGE:
        assert rule.rate is not None
        amount = percentage_of(line_total, Decimal(rule.rate))
    else:
        assert rule.fixed_amount is not None
        amount = rule.fixed_amount * quantity
    amount = min(amount, line_total)  # commission never exceeds the amount it applies to
    return LineCommission(rule_id=rule.id, rate_type=rate_type, rate=rule.rate, fixed=rule.fixed_amount, amount=amount)


async def line_commission(
    session: AsyncSession,
    *,
    merchant_id: uuid.UUID,
    category_id: uuid.UUID | None,
    line_total: int,
    quantity: int,
    at: datetime,
) -> LineCommission:
    rule = await resolve_rule(session, merchant_id=merchant_id, category_id=category_id, at=at)
    return calculate(rule, line_total=line_total, quantity=quantity)


async def set_rule(
    session: AsyncSession,
    *,
    scope: CommissionScope,
    merchant_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    rate_type: CommissionRateType,
    rate: Decimal | None,
    fixed_amount: int | None,
    effective_from: datetime | None,
    note: str | None,
    actor_user_id: uuid.UUID,
    ip: str | None,
) -> CommissionRule:
    """Create a new rule; the currently effective rule for the same target is closed.

    Existing orders keep the commission snapshot taken at checkout.
    """
    start = effective_from or utcnow()
    if start < utcnow().replace(microsecond=0) and effective_from is not None:
        raise ValidationFailed("Commission changes cannot be backdated.", code="backdated_commission")
    target: list[ColumnElement[bool]] = [col(CommissionRule.scope) == scope.value]
    target.append(
        col(CommissionRule.merchant_id) == merchant_id if merchant_id else col(CommissionRule.merchant_id).is_(None)
    )
    target.append(
        col(CommissionRule.category_id) == category_id if category_id else col(CommissionRule.category_id).is_(None)
    )
    scheduled = (
        await session.exec(select(CommissionRule.id).where(*target, CommissionRule.effective_from >= start))
    ).first()
    if scheduled:
        raise Conflict("A commission change is already scheduled at or after this date.", code="commission_scheduled")
    current = (await session.exec(select(CommissionRule).where(*target, *_active_at(start)).with_for_update())).first()
    before = None
    if current is not None:
        before = _rule_dict(current)
        current.effective_to = start
    rule = CommissionRule(
        scope=scope.value,
        merchant_id=merchant_id,
        category_id=category_id,
        rate_type=rate_type.value,
        rate=rate if rate_type == CommissionRateType.PERCENTAGE else None,
        fixed_amount=fixed_amount if rate_type == CommissionRateType.FIXED else None,
        effective_from=start,
        created_by_user_id=actor_user_id,
        note=note,
    )
    session.add(rule)
    await session.flush()
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="commission.set",
        entity_type="commission_rule",
        entity_id=rule.id,
        before=before,
        after=_rule_dict(rule),
        ip_address=ip,
    )
    return rule


async def end_rule(
    session: AsyncSession, rule_id: uuid.UUID, *, actor_user_id: uuid.UUID, ip: str | None
) -> CommissionRule:
    rule = await session.get(CommissionRule, rule_id, with_for_update=True)
    if rule is None:
        from app.core.errors import NotFound

        raise NotFound("Commission rule not found.")
    if rule.scope == CommissionScope.GLOBAL.value:
        raise Conflict("The global commission cannot be ended; set a new one instead.", code="global_required")
    now = utcnow()
    if rule.effective_to is not None and rule.effective_to <= now:
        raise Conflict("This rule is no longer in effect.", code="rule_ended")
    if rule.effective_from >= now:
        raise Conflict("Scheduled rules cannot be ended before they start.", code="rule_scheduled")
    before = _rule_dict(rule)
    rule.effective_to = now
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="commission.end",
        entity_type="commission_rule",
        entity_id=rule.id,
        before=before,
        after=_rule_dict(rule),
        ip_address=ip,
    )
    await session.flush()
    return rule


def _rule_dict(rule: CommissionRule) -> dict[str, object]:
    return {
        "scope": rule.scope,
        "merchant_id": str(rule.merchant_id) if rule.merchant_id else None,
        "category_id": str(rule.category_id) if rule.category_id else None,
        "rate_type": rule.rate_type,
        "rate": str(rule.rate) if rule.rate is not None else None,
        "fixed_amount": rule.fixed_amount,
        "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
        "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
    }
