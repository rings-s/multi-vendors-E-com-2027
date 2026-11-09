"""Pure unit tests: money arithmetic, allocation invariants and Saudi validators."""

import uuid
from decimal import Decimal

import pytest

from app.core.errors import ValidationFailed
from app.core.money import (
    CurrencyMismatch,
    ensure_currency,
    halalas_to_sar,
    percentage_of,
    proportional_share,
    sar_to_halalas,
)
from app.core.validators import mask_iban, normalize_saudi_mobile, validate_saudi_iban
from app.modules.payments.allocation import (
    AllocationSpec,
    build_allocations,
    to_split_instructions,
    validate_allocations,
)
from app.modules.payments.models import FeeBearer, RecipientType
from tests.helpers import saudi_iban

MERCHANT = uuid.uuid4()


def test_halalas_conversion_has_no_float_rounding() -> None:
    assert sar_to_halalas("100.10") == 10010
    assert sar_to_halalas(Decimal("0.01")) == 1
    assert halalas_to_sar(10010) == Decimal("100.10")
    with pytest.raises(ValueError):
        sar_to_halalas("1.005")


def test_percentage_rounding_is_deterministic_half_up() -> None:
    assert percentage_of(10000, Decimal("10")) == 1000
    assert percentage_of(12345, Decimal("15")) == 1852  # 1851.75 -> 1852
    assert percentage_of(5, Decimal("10")) == 1  # 0.5 -> 1 (half up)
    assert percentage_of(4, Decimal("10")) == 0  # 0.4 -> 0
    assert all(percentage_of(99999, Decimal("12.5")) == 12500 for _ in range(100))
    with pytest.raises(ValueError):
        percentage_of(100, Decimal("101"))
    with pytest.raises(ValueError):
        percentage_of(-1, Decimal("10"))


def test_proportional_share() -> None:
    assert proportional_share(11500, 1000, 3333) == 290
    assert proportional_share(11500, 1000, 11500) == 1000


def test_currency_is_never_converted() -> None:
    assert ensure_currency("SAR", "SAR") == "SAR"
    with pytest.raises(CurrencyMismatch):
        ensure_currency("SAR", "USD")
    with pytest.raises(CurrencyMismatch):
        ensure_currency("AED")


@pytest.mark.parametrize("total", [1, 99, 10000, 11500, 123457, 10_000_000])
@pytest.mark.parametrize("rate", ["0", "5", "10", "12.5", "15", "100"])
def test_allocations_always_sum_to_total(total: int, rate: str) -> None:
    commission = percentage_of(total, Decimal(rate))
    allocations = build_allocations(
        total=total,
        commission=commission,
        merchant_id=MERCHANT,
        merchant_recipient_id="rcp_merchant",
        platform_recipient_id="rcp_platform",
        merchant_can_accept_payments=True,
        fee_bearer=FeeBearer.MERCHANT,
    )
    assert sum(a.amount for a in allocations) == total
    assert all(a.amount >= 0 for a in allocations)
    merchant = next(a for a in allocations if a.recipient_type == RecipientType.MERCHANT)
    assert merchant.amount == total - commission


def _spec(
    recipient: str, amount: int, kind: RecipientType = RecipientType.MERCHANT, fee: bool = False
) -> AllocationSpec:
    return AllocationSpec(
        recipient_type=kind, recipient_id=recipient, amount=amount, merchant_id=MERCHANT, is_fee_source=fee
    )


def test_allocation_invariants() -> None:
    good = [_spec("m", 900), _spec("p", 100, RecipientType.PLATFORM, fee=True)]
    validate_allocations(1000, good)
    with pytest.raises(ValidationFailed):
        validate_allocations(1001, good)  # sum mismatch
    with pytest.raises(ValidationFailed):
        validate_allocations(1000, [_spec("m", 1100), _spec("p", -100, RecipientType.PLATFORM)])  # negative
    with pytest.raises(ValidationFailed):
        validate_allocations(1000, [_spec("m", 500), _spec("m", 500)])  # duplicate
    with pytest.raises(ValidationFailed):
        validate_allocations(1000, [_spec("", 900), _spec("p", 100, RecipientType.PLATFORM)])  # missing recipient
    with pytest.raises(ValidationFailed):
        validate_allocations(1000, [_spec("m", 900, fee=True), _spec("p", 100, RecipientType.PLATFORM, fee=True)])
    with pytest.raises(ValidationFailed):
        validate_allocations(0, [])


def test_allocation_rejects_invalid_merchant_or_commission() -> None:
    common = {
        "total": 1000,
        "merchant_id": MERCHANT,
        "platform_recipient_id": "rcp_platform",
        "fee_bearer": FeeBearer.PLATFORM,
    }
    with pytest.raises(ValidationFailed):
        build_allocations(commission=100, merchant_recipient_id="m", merchant_can_accept_payments=False, **common)
    with pytest.raises(ValidationFailed):
        build_allocations(commission=100, merchant_recipient_id=None, merchant_can_accept_payments=True, **common)
    with pytest.raises(ValidationFailed):
        build_allocations(commission=1001, merchant_recipient_id="m", merchant_can_accept_payments=True, **common)


def test_split_instructions_refuse_zero_fee_source() -> None:
    allocations = build_allocations(
        total=1000,
        commission=0,
        merchant_id=MERCHANT,
        merchant_recipient_id="m",
        platform_recipient_id="p",
        merchant_can_accept_payments=True,
        fee_bearer=FeeBearer.PLATFORM,
    )
    with pytest.raises(ValidationFailed):
        to_split_instructions(allocations, reference="ORD-1")


def test_saudi_mobile_normalisation() -> None:
    for raw in ("0551234567", "+966551234567", "966551234567", "055 123 4567"):
        assert normalize_saudi_mobile(raw) == "+966551234567"
    for bad in ("0451234567", "+12025550123", "05512345"):
        with pytest.raises(ValueError):
            normalize_saudi_mobile(bad)


def test_saudi_iban_validation_and_masking() -> None:
    iban = saudi_iban(7)
    assert validate_saudi_iban(iban.lower()) == iban
    tampered = iban[:-1] + ("0" if iban[-1] != "0" else "1")
    with pytest.raises(ValueError):
        validate_saudi_iban(tampered)
    with pytest.raises(ValueError):
        validate_saudi_iban("AE070331234567890123456")
    masked = mask_iban(iban)
    assert masked.startswith(iban[:4]) and masked.endswith(iban[-4:]) and iban[4:-4] not in masked
