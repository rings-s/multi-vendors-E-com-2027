import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings
from app.modules.catalog.models import CategoryKind, ServiceAvailability, ServiceLocationType

Halalas = Annotated[int, Field(gt=0, le=10_000_000_00, description="Amount in halalas (1 SAR = 100).")]


def _media_url(value: str) -> str:
    prefix = get_settings().media_url_prefix
    if not (value.startswith(f"{prefix}/") or value.startswith("https://")):
        raise ValueError("Image URLs must come from the upload endpoint or use HTTPS.")
    return value


MediaUrl = Annotated[str, Field(max_length=500), AfterValidator(_media_url)]


class CategoryIn(BaseModel):
    parent_id: uuid.UUID | None = None
    slug: str = Field(pattern=r"^[a-z0-9-]{2,80}$")
    name_en: str = Field(min_length=2, max_length=120)
    name_ar: str = Field(min_length=2, max_length=120)
    kind: CategoryKind = CategoryKind.BOTH
    is_active: bool = True
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    parent_id: uuid.UUID | None = None
    name_en: str | None = Field(default=None, min_length=2, max_length=120)
    name_ar: str | None = Field(default=None, min_length=2, max_length=120)
    kind: CategoryKind | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_id: uuid.UUID | None
    slug: str
    name_en: str
    name_ar: str
    kind: str
    is_active: bool
    sort_order: int


class ImageIn(BaseModel):
    url: MediaUrl
    alt: str = Field(default="", max_length=200)


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    alt: str
    sort_order: int


def _check_discount(price: int | None, discounted: int | None) -> None:
    if discounted is not None and price is not None and discounted >= price:
        raise ValueError("discounted_price must be lower than price.")


class VariantIn(BaseModel):
    id: uuid.UUID | None = None
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    options: dict[str, str] = Field(default_factory=dict)
    price: Halalas | None = None
    discounted_price: Halalas | None = None
    is_active: bool = True
    stock_quantity: int = Field(default=0, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _discount(self) -> "VariantIn":
        _check_discount(self.price, self.discounted_price)
        return self


class ProductIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=20000)
    sku: str = Field(min_length=1, max_length=64)
    price: Halalas
    discounted_price: Halalas | None = None
    category_id: uuid.UUID | None = None
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"
    is_available: bool = True
    requires_shipping: bool = True
    weight_grams: int | None = Field(default=None, ge=0)
    stock_quantity: int = Field(default=0, ge=0, le=1_000_000)
    images: list[ImageIn] = Field(default_factory=list, max_length=12)
    variants: list[VariantIn] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _validate(self) -> "ProductIn":
        _check_discount(self.price, self.discounted_price)
        skus = [v.sku for v in self.variants]
        if len(skus) != len(set(skus)):
            raise ValueError("Variant SKUs must be unique.")
        return self


class ProductUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    price: Halalas | None = None
    discounted_price: Halalas | None = None
    clear_discount: bool = False
    category_id: uuid.UUID | None = None
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] | None = None
    is_available: bool | None = None
    requires_shipping: bool | None = None
    weight_grams: int | None = Field(default=None, ge=0)
    images: list[ImageIn] | None = Field(default=None, max_length=12)
    variants: list[VariantIn] | None = Field(default=None, max_length=100)


class VariantOut(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    options: dict[str, str]
    price: int
    discounted_price: int | None
    is_active: bool
    available_quantity: int


class StoreSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    city: str
    logo_url: str | None
    rating_avg: float
    rating_count: int


class ProductOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    store: StoreSummary
    category_id: uuid.UUID | None
    title: str
    slug: str
    description: str
    sku: str
    price: int
    discounted_price: int | None
    currency: Literal["SAR"] = "SAR"
    status: str
    is_available: bool
    requires_shipping: bool
    weight_grams: int | None
    in_stock: bool
    available_quantity: int
    images: list[ImageOut]
    variants: list[VariantOut]
    is_featured: bool
    moderation_note: str | None = None
    created_at: datetime
    updated_at: datetime


class ServiceIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=20000)
    price: Halalas
    discounted_price: Halalas | None = None
    duration_minutes: int = Field(gt=0, le=60 * 24 * 30)
    category_id: uuid.UUID | None = None
    availability: ServiceAvailability = ServiceAvailability.AVAILABLE
    location_type: ServiceLocationType = ServiceLocationType.AT_STORE
    location: str = Field(default="", max_length=300)
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"
    images: list[ImageIn] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def _discount(self) -> "ServiceIn":
        _check_discount(self.price, self.discounted_price)
        return self


class ServiceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    price: Halalas | None = None
    discounted_price: Halalas | None = None
    clear_discount: bool = False
    duration_minutes: int | None = Field(default=None, gt=0, le=60 * 24 * 30)
    category_id: uuid.UUID | None = None
    availability: ServiceAvailability | None = None
    location_type: ServiceLocationType | None = None
    location: str | None = Field(default=None, max_length=300)
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] | None = None
    images: list[ImageIn] | None = Field(default=None, max_length=12)


class ServiceOut(BaseModel):
    id: uuid.UUID
    merchant_id: uuid.UUID
    store: StoreSummary
    category_id: uuid.UUID | None
    title: str
    slug: str
    description: str
    price: int
    discounted_price: int | None
    currency: Literal["SAR"] = "SAR"
    duration_minutes: int
    availability: str
    location_type: str
    location: str
    status: str
    images: list[ImageOut]
    is_featured: bool
    moderation_note: str | None = None
    created_at: datetime
    updated_at: datetime


class InventoryOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_title: str
    variant_id: uuid.UUID | None
    variant_name: str | None
    sku: str
    quantity_on_hand: int
    quantity_reserved: int
    available: int


class InventoryAdjust(BaseModel):
    quantity_on_hand: int | None = Field(default=None, ge=0, le=1_000_000)
    delta: int | None = Field(default=None, ge=-1_000_000, le=1_000_000)

    @model_validator(mode="after")
    def _one(self) -> "InventoryAdjust":
        if (self.quantity_on_hand is None) == (self.delta is None):
            raise ValueError("Provide exactly one of quantity_on_hand or delta.")
        return self


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=3000)


class ReviewOut(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    rating: int
    comment: str
    customer_name: str
    status: str
    created_at: datetime


class ModerationAction(BaseModel):
    action: Literal["block", "unblock", "feature", "unfeature"]
    note: str | None = Field(default=None, max_length=2000)
