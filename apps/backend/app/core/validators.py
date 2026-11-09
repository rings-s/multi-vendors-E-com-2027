"""Saudi-specific validators: mobile numbers, IBANs, regions."""

import re
from typing import Annotated

from pydantic import AfterValidator

# Saudi mobile numbers: +9665XXXXXXXX (also accepts 05XXXXXXXX / 9665XXXXXXXX and normalises).
_MOBILE_RE = re.compile(r"^(?:\+?966|0)?(5\d{8})$")
_IBAN_RE = re.compile(r"^SA\d{2}[0-9A-Z]{20}$")

SAUDI_REGIONS: tuple[str, ...] = (
    "riyadh",
    "makkah",
    "madinah",
    "qassim",
    "eastern_province",
    "asir",
    "tabuk",
    "hail",
    "northern_borders",
    "jazan",
    "najran",
    "al_bahah",
    "al_jawf",
)


def normalize_saudi_mobile(value: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", value)
    match = _MOBILE_RE.match(cleaned)
    if not match:
        raise ValueError("Must be a valid Saudi mobile number (+9665XXXXXXXX).")
    return f"+966{match.group(1)}"


def validate_saudi_iban(value: str) -> str:
    iban = re.sub(r"\s", "", value).upper()
    if not _IBAN_RE.match(iban):
        raise ValueError("Must be a valid Saudi IBAN (SA followed by 22 digits/characters).")
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(numeric) % 97 != 1:
        raise ValueError("IBAN checksum is invalid.")
    return iban


def mask_iban(iban: str) -> str:
    return f"{iban[:4]}{'*' * (len(iban) - 8)}{iban[-4:]}"


def validate_region(value: str) -> str:
    if value not in SAUDI_REGIONS:
        raise ValueError(f"Region must be one of: {', '.join(SAUDI_REGIONS)}")
    return value


SaudiMobile = Annotated[str, AfterValidator(normalize_saudi_mobile)]
SaudiIBAN = Annotated[str, AfterValidator(validate_saudi_iban)]
SaudiRegion = Annotated[str, AfterValidator(validate_region)]
