"""Typed platform settings stored in ``platform_settings`` (one JSON document per key)."""

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator, model_validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import NotFound, ValidationFailed
from app.modules.admin.audit import record_audit
from app.modules.admin.models import PlatformSetting


class MarketplaceSettings(BaseModel):
    name_en: str = "Marketplace"
    name_ar: str = "السوق"
    support_email: EmailStr | None = None
    support_phone: str | None = None
    terms_url: str | None = None


class CurrencySettings(BaseModel):
    # Only SAR is supported; currency conversion is never performed.
    code: Literal["SAR"] = "SAR"


class TaxSettings(BaseModel):
    vat_rate: Decimal = Field(default=Decimal("15.00"), ge=0, le=100)
    vat_applies_to_shipping: bool = True
    # Prices entered by merchants exclude VAT; VAT is added for VAT-registered merchants.
    prices_include_vat: Literal[False] = False


class PaymentSettings(BaseModel):
    # Who bears payment-processing fees. Shown to merchants; never deducted silently.
    fee_bearer: Literal["PLATFORM", "MERCHANT"] = "PLATFORM"


class DeliveryFinanceSettings(BaseModel):
    """How delivery fees are treated financially (snapshotted on each order at checkout).

    ``commission_applies_to`` must be chosen explicitly: ``ITEMS_ONLY`` (default) keeps
    delivery fees out of platform commission entirely; ``ITEMS_AND_DELIVERY`` charges
    ``delivery_commission_rate`` % of merchant-received delivery fees (excl. VAT) as a
    separate, separately reported delivery commission.
    """

    commission_applies_to: Literal["ITEMS_ONLY", "ITEMS_AND_DELIVERY"] = "ITEMS_ONLY"
    delivery_commission_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=3)

    @model_validator(mode="after")
    def _explicit(self) -> "DeliveryFinanceSettings":
        if self.commission_applies_to == "ITEMS_ONLY" and self.delivery_commission_rate != 0:
            raise ValueError("delivery_commission_rate must be 0 when commission applies to items only.")
        if self.commission_applies_to == "ITEMS_AND_DELIVERY" and self.delivery_commission_rate <= 0:
            raise ValueError("Set a delivery_commission_rate above 0 to charge commission on delivery fees.")
        return self


class LanguageSettings(BaseModel):
    enabled: list[Literal["ar", "en"]] = Field(default_factory=lambda: list[Literal["ar", "en"]](["ar", "en"]))
    default: Literal["ar", "en"] = "ar"

    @field_validator("enabled")
    @classmethod
    def _non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one language must be enabled.")
        return value


class Promotion(BaseModel):
    title_en: str
    title_ar: str
    subtitle_en: str = ""
    subtitle_ar: str = ""
    image_url: str | None = None
    link: str | None = None


class Testimonial(BaseModel):
    name: str
    quote_en: str
    quote_ar: str
    rating: int = Field(default=5, ge=1, le=5)


class HomepageSettings(BaseModel):
    hero_title_en: str = "Discover independent Saudi stores"
    hero_title_ar: str = "اكتشف المتاجر السعودية المستقلة"
    hero_subtitle_en: str = ""
    hero_subtitle_ar: str = ""
    featured_store_ids: list[uuid.UUID] = Field(default_factory=list)
    featured_product_ids: list[uuid.UUID] = Field(default_factory=list)
    featured_service_ids: list[uuid.UUID] = Field(default_factory=list)
    promotions: list[Promotion] = Field(default_factory=list)
    testimonials: list[Testimonial] = Field(default_factory=list)


class EmailTemplate(BaseModel):
    subject_en: str
    subject_ar: str
    body_en: str
    body_ar: str


class EmailTemplateSettings(BaseModel):
    templates: dict[str, EmailTemplate] = Field(default_factory=dict)


SETTINGS_SCHEMAS: dict[str, type[BaseModel]] = {
    "marketplace": MarketplaceSettings,
    "currency": CurrencySettings,
    "tax": TaxSettings,
    "payments": PaymentSettings,
    "delivery": DeliveryFinanceSettings,
    "languages": LanguageSettings,
    "homepage": HomepageSettings,
    "email_templates": EmailTemplateSettings,
}


async def get_setting[T: BaseModel](session: AsyncSession, key: str, schema: type[T]) -> T:
    row = (await session.exec(select(PlatformSetting).where(PlatformSetting.key == key))).first()
    return schema.model_validate(row.value if row else {})


async def get_all(session: AsyncSession) -> dict[str, dict[str, Any]]:
    return {
        key: (await get_setting(session, key, schema)).model_dump(mode="json")
        for key, schema in SETTINGS_SCHEMAS.items()
    }


async def update_setting(
    session: AsyncSession, key: str, value: dict[str, Any], *, actor_user_id: uuid.UUID, ip: str | None
) -> dict[str, Any]:
    schema = SETTINGS_SCHEMAS.get(key)
    if schema is None:
        raise NotFound(f"Unknown setting {key!r}.")
    try:
        validated = schema.model_validate(value).model_dump(mode="json")
    except ValidationError as exc:
        raise ValidationFailed(
            "Invalid setting value.", details=exc.errors(include_url=False, include_context=False, include_input=False)
        ) from exc
    row = (await session.exec(select(PlatformSetting).where(PlatformSetting.key == key).with_for_update())).first()
    before = row.value if row else None
    if row is None:
        session.add(PlatformSetting(key=key, value=validated, updated_by_user_id=actor_user_id))
    else:
        row.value = validated
        row.updated_by_user_id = actor_user_id
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="settings.update",
        entity_type="platform_setting",
        entity_id=key,
        before=before,
        after=validated,
        ip_address=ip,
    )
    await session.flush()
    return validated
