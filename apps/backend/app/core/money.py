"""Money primitives.

Rules (docs/architecture/payment-architecture.md §2.3):

* Amounts are stored and exchanged as integer halalas (1 SAR = 100 halalas).
* Rates and intermediate calculations use ``Decimal``; floats are never used for money.
* Rounding is deterministic: ROUND_HALF_UP to the nearest halala.
* Only SAR is supported; currency conversion is never performed.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

HALALAS_PER_SAR = 100
ONE_HUNDRED = Decimal(100)


class Currency(StrEnum):
    SAR = "SAR"


class CurrencyMismatch(ValueError):
    pass


def ensure_currency(*currencies: str) -> Currency:
    """Ensure every currency given is SAR. Never converts between currencies."""
    unique = set(currencies)
    if unique != {Currency.SAR.value}:
        raise CurrencyMismatch(f"Unsupported or mixed currencies: {sorted(unique)}")
    return Currency.SAR


def sar_to_halalas(value: Decimal | str | int) -> int:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid SAR amount: {value!r}") from exc
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("SAR amounts must have at most two decimal places.")
    return int(amount * HALALAS_PER_SAR)


def halalas_to_sar(value: int) -> Decimal:
    return (Decimal(value) / HALALAS_PER_SAR).quantize(Decimal("0.01"))


def round_halalas(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percentage_of(amount_halalas: int, rate_percent: Decimal) -> int:
    """Return ``rate_percent`` % of ``amount_halalas`` rounded half-up to a halala."""
    if amount_halalas < 0:
        raise ValueError("Amount must not be negative.")
    if rate_percent < 0 or rate_percent > ONE_HUNDRED:
        raise ValueError("Rate must be between 0 and 100 percent.")
    return round_halalas(Decimal(amount_halalas) * rate_percent / ONE_HUNDRED)


def proportional_share(total: int, part: int, of_amount: int) -> int:
    """Return ``of_amount * part / total`` rounded half-up (deterministic)."""
    if total <= 0:
        raise ValueError("Total must be positive.")
    return round_halalas(Decimal(of_amount) * Decimal(part) / Decimal(total))
