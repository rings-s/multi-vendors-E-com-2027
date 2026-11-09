"""Payment allocation: how a merchant order's payment is split.

Internal representation (integer halalas), e.g. 100 SAR at 10% commission::

    {"currency": "SAR", "total_amount": 10000,
     "allocations": [{"recipient": "merchant", "amount": 9000},
                     {"recipient": "platform", "amount": 1000}]}

Invariants enforced (docs/architecture/payment-architecture.md §2.4):
sum equals the payable amount, no negative amounts, no duplicate recipients,
valid recipient ids, valid merchant status and a valid commission configuration.
"""

import uuid
from dataclasses import dataclass

from app.core.errors import ValidationFailed
from app.integrations.payments.base import SplitInstruction
from app.modules.payments.models import FeeBearer, RecipientType


@dataclass(frozen=True)
class AllocationSpec:
    recipient_type: RecipientType
    recipient_id: str
    amount: int
    merchant_id: uuid.UUID | None
    is_fee_source: bool
    refundable: bool = True
    delivery_amount: int = 0  # part of ``amount`` that comes from the delivery charge


class AllocationError(ValidationFailed):
    code = "invalid_allocation"


def build_allocations(
    *,
    total: int,
    commission: int,
    merchant_id: uuid.UUID,
    merchant_recipient_id: str | None,
    platform_recipient_id: str | None,
    merchant_can_accept_payments: bool,
    fee_bearer: FeeBearer,
    delivery_platform: int = 0,
    delivery_merchant: int = 0,
) -> list[AllocationSpec]:
    """Split a merchant order's total between the merchant and the platform.

    ``commission`` is the item commission. The delivery charge is split explicitly:
    ``delivery_platform`` (delivery commission, or the whole delivery charge when the
    platform receives delivery fees) goes to the platform and ``delivery_merchant`` to
    the merchant. Each allocation records its delivery part so refunds, the ledger
    and reconciliation can keep delivery money separate.
    """
    if not merchant_can_accept_payments:
        raise AllocationError("This merchant cannot accept payments yet.", code="merchant_cannot_accept_payments")
    if not merchant_recipient_id:
        raise AllocationError("The merchant has no verified payment recipient.", code="invalid_recipient")
    if not platform_recipient_id:
        raise AllocationError("The platform recipient is not configured.", code="invalid_recipient")
    if commission < 0 or delivery_platform < 0 or delivery_merchant < 0:
        raise AllocationError("Invalid commission amount.", code="invalid_commission")
    platform_amount = commission + delivery_platform
    merchant_amount = total - platform_amount
    if platform_amount > total or delivery_merchant > merchant_amount:
        raise AllocationError("Invalid commission amount.", code="invalid_commission")
    allocations = [
        AllocationSpec(
            recipient_type=RecipientType.MERCHANT,
            recipient_id=merchant_recipient_id,
            amount=merchant_amount,
            merchant_id=merchant_id,
            is_fee_source=fee_bearer == FeeBearer.MERCHANT,
            delivery_amount=delivery_merchant,
        ),
        AllocationSpec(
            recipient_type=RecipientType.PLATFORM,
            recipient_id=platform_recipient_id,
            amount=platform_amount,
            merchant_id=None,
            is_fee_source=fee_bearer == FeeBearer.PLATFORM,
            delivery_amount=delivery_platform,
        ),
    ]
    validate_allocations(total, allocations)
    return allocations


def validate_allocations(total: int, allocations: list[AllocationSpec]) -> None:
    if total <= 0:
        raise AllocationError("The payable amount must be positive.")
    if any(a.amount < 0 for a in allocations):
        raise AllocationError("Allocations cannot be negative.")
    if any(a.delivery_amount < 0 or a.delivery_amount > a.amount for a in allocations):
        raise AllocationError("An allocation's delivery part must be within its amount.")
    if sum(a.amount for a in allocations) != total:
        raise AllocationError("Allocations must sum to the payable amount.")
    recipients = [(a.recipient_type, a.recipient_id) for a in allocations]
    if len(recipients) != len(set(recipients)) or len({a.recipient_id for a in allocations}) != len(allocations):
        raise AllocationError("Duplicate allocation recipients.")
    if any(not a.recipient_id for a in allocations):
        raise AllocationError("Every allocation needs a recipient.")
    if sum(1 for a in allocations if a.is_fee_source) > 1:
        raise AllocationError("Only one allocation can bear the processing fee.")


def to_split_instructions(allocations: list[AllocationSpec], reference: str) -> tuple[SplitInstruction, ...]:
    """Provider split instructions. Zero-amount allocations are not sent.

    If the fee-bearing allocation is zero (e.g. 0% commission with platform-borne fees),
    the payment is refused rather than letting the provider pick a fee source.
    """
    fee_source = next((a for a in allocations if a.is_fee_source), None)
    if fee_source is not None and fee_source.amount == 0:
        raise AllocationError(
            "The fee-bearing recipient has no allocation; processing fees cannot be charged explicitly.",
            code="fee_source_zero",
        )
    return tuple(
        SplitInstruction(
            recipient_id=a.recipient_id,
            amount=a.amount,
            reference=f"{reference}:{a.recipient_type.value.lower()}",
            is_fee_source=a.is_fee_source,
            refundable=a.refundable,
        )
        for a in allocations
        if a.amount > 0
    )
