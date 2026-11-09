"""Merchant registration, verification workflow and payment onboarding."""

import re
import uuid

import structlog
from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.security import utcnow
from app.core.validators import mask_iban
from app.integrations.payments.base import MerchantAccountInput, PaymentProvider, ProviderMerchantAccount
from app.modules.admin.audit import record_audit
from app.modules.auth.models import RoleName, User
from app.modules.auth.service import create_user
from app.modules.catalog.models import Category
from app.modules.merchants.models import (
    BusinessType,
    DocumentStatus,
    Merchant,
    MerchantAddress,
    MerchantBankAccountReference,
    MerchantDocumentReference,
    MerchantPaymentAccount,
    MerchantProfile,
    MerchantStatus,
    MerchantVerification,
    OnboardingStatus,
    PayoutStatus,
)
from app.modules.merchants.schemas import (
    BankAccountOut,
    DocumentReferenceOut,
    MerchantAddressOut,
    MerchantOut,
    MerchantRegisterRequest,
    OnboardingUpdate,
    PaymentAccountOut,
    PaymentOnboardingRequest,
)
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.stores.models import Store, StoreStatus

log = structlog.get_logger(__name__)

EDITABLE_STATUSES = {MerchantStatus.DRAFT, MerchantStatus.ADDITIONAL_INFO_REQUIRED}
CR_REQUIRED_TYPES = {BusinessType.ESTABLISHMENT, BusinessType.COMPANY}

# Allowed administrative transitions of the verification workflow.
ADMIN_TRANSITIONS: dict[MerchantStatus, set[MerchantStatus]] = {
    MerchantStatus.SUBMITTED: {
        MerchantStatus.UNDER_REVIEW,
        MerchantStatus.APPROVED,
        MerchantStatus.REJECTED,
        MerchantStatus.ADDITIONAL_INFO_REQUIRED,
    },
    MerchantStatus.UNDER_REVIEW: {
        MerchantStatus.APPROVED,
        MerchantStatus.REJECTED,
        MerchantStatus.ADDITIONAL_INFO_REQUIRED,
    },
    MerchantStatus.APPROVED: {MerchantStatus.SUSPENDED},
    MerchantStatus.SUSPENDED: {MerchantStatus.APPROVED},
}


# -- queries ---------------------------------------------------------------------------


async def get_store(session: AsyncSession, merchant_id: uuid.UUID) -> Store | None:
    return (await session.exec(select(Store).where(Store.merchant_id == merchant_id))).first()


async def get_payment_account(
    session: AsyncSession, merchant_id: uuid.UUID, provider: str, *, lock: bool = False
) -> MerchantPaymentAccount | None:
    stmt = select(MerchantPaymentAccount).where(
        MerchantPaymentAccount.merchant_id == merchant_id, MerchantPaymentAccount.provider == provider
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.exec(stmt)).first()


def can_accept_payments(merchant: Merchant, store: Store | None, account: MerchantPaymentAccount | None) -> bool:
    """Payments require platform approval AND provider activation (requirements §2.2)."""
    return (
        merchant.status == MerchantStatus.APPROVED
        and store is not None
        and store.status == StoreStatus.ACTIVE
        and account is not None
        and account.onboarding_status == OnboardingStatus.ACTIVE
        and bool(account.recipient_id)
    )


async def merchant_can_accept_payments(session: AsyncSession, merchant: Merchant, provider: str) -> bool:
    return can_accept_payments(
        merchant, await get_store(session, merchant.id), await get_payment_account(session, merchant.id, provider)
    )


async def merchant_out(session: AsyncSession, merchant: Merchant, provider: str) -> MerchantOut:
    store = await get_store(session, merchant.id)
    addresses = (
        await session.exec(
            select(MerchantAddress)
            .where(MerchantAddress.merchant_id == merchant.id)
            .order_by(col(MerchantAddress.created_at))
        )
    ).all()
    profile = merchant.profile
    return MerchantOut(
        id=merchant.id,
        owner_user_id=merchant.owner_user_id,
        owner_full_name=profile.owner_full_name,
        business_name=merchant.business_name,
        business_type=merchant.business_type,
        category_id=merchant.category_id,
        business_description=profile.business_description,
        contact_email=profile.contact_email,
        contact_phone=profile.contact_phone,
        website=profile.website,
        commercial_registration_number=merchant.commercial_registration_number,
        vat_number=merchant.vat_number,
        status=merchant.status,
        status_reason=merchant.status_reason,
        submitted_at=merchant.submitted_at,
        approved_at=merchant.approved_at,
        created_at=merchant.created_at,
        store_id=store.id if store else None,
        store_slug=store.slug if store else None,
        addresses=[MerchantAddressOut.model_validate(a) for a in addresses],
        can_accept_payments=can_accept_payments(
            merchant, store, await get_payment_account(session, merchant.id, provider)
        ),
    )


# -- registration & onboarding ------------------------------------------------------


async def _validate_category(session: AsyncSession, category_id: uuid.UUID | None) -> None:
    if category_id is not None:
        category = await session.get(Category, category_id)
        if category is None or not category.is_active:
            raise ValidationFailed("Unknown business category.", code="invalid_category")


async def register_merchant(session: AsyncSession, data: MerchantRegisterRequest) -> tuple[User, Merchant]:
    if (await session.exec(select(Store.id).where(Store.slug == data.store_slug))).first():
        raise Conflict("This store address is already taken.", code="store_slug_taken")
    await _validate_category(session, data.category_id)
    user = await create_user(
        session,
        email=data.email,
        password=data.password,
        full_name=data.owner_full_name,
        phone=data.mobile,
        roles=[RoleName.MERCHANT],
        preferred_language=data.preferred_language,
    )
    merchant = Merchant(
        owner_user_id=user.id,
        business_name=data.business_name,
        business_type=data.business_type.value,
        category_id=data.category_id,
        commercial_registration_number=data.commercial_registration_number,
        vat_number=data.vat_number,
        status=MerchantStatus.DRAFT.value,
    )
    session.add(merchant)
    await session.flush()
    session.add(
        MerchantProfile(
            merchant_id=merchant.id,
            owner_full_name=data.owner_full_name,
            contact_email=user.email,
            contact_phone=data.mobile,
            business_description=data.business_description,
        )
    )
    session.add(MerchantAddress(merchant_id=merchant.id, label="Main", is_primary=True, **data.address.model_dump()))
    store = Store(
        merchant_id=merchant.id,
        slug=data.store_slug,
        name=data.store_name,
        description=data.business_description,
        region=data.address.region,
        city=data.city,
        contact_email=user.email,
        contact_phone=data.mobile,
        status=StoreStatus.INACTIVE.value,
    )
    session.add(store)
    if data.category_id:
        from app.modules.stores.models import StoreCategory

        await session.flush()
        session.add(StoreCategory(store_id=store.id, category_id=data.category_id))
    session.add(MerchantVerification(merchant_id=merchant.id, from_status=None, to_status=MerchantStatus.DRAFT.value))
    await session.flush()
    await session.refresh(merchant, ["profile"])
    return user, merchant


async def update_onboarding(session: AsyncSession, merchant: Merchant, data: OnboardingUpdate) -> Merchant:
    if MerchantStatus(merchant.status) not in EDITABLE_STATUSES:
        raise Conflict("The application can only be edited while in draft or when more information is requested.")
    values = data.model_dump(exclude_unset=True)
    if "category_id" in values:
        await _validate_category(session, values["category_id"])
    profile = merchant.profile
    for key in ("business_name", "category_id", "commercial_registration_number", "vat_number"):
        if key in values:
            setattr(merchant, key, values[key])
    if values.get("business_type") is not None:
        merchant.business_type = values["business_type"].value
    for key in ("business_description", "contact_email", "contact_phone"):
        if values.get(key) is not None:
            setattr(profile, key, values[key])
    if "website" in values:
        profile.website = str(values["website"]) if values["website"] else None
    if data.address is not None:
        primary = (
            await session.exec(
                select(MerchantAddress).where(
                    col(MerchantAddress.merchant_id) == merchant.id, col(MerchantAddress.is_primary).is_(True)
                )
            )
        ).first()
        if primary is None:
            session.add(MerchantAddress(merchant_id=merchant.id, is_primary=True, **data.address.model_dump()))
        else:
            for key, value in data.address.model_dump().items():
                setattr(primary, key, value)
    await session.flush()
    return merchant


async def _set_status(
    session: AsyncSession,
    merchant: Merchant,
    to_status: MerchantStatus,
    *,
    actor_user_id: uuid.UUID | None,
    note: str | None,
) -> None:
    from_status = merchant.status
    merchant.status = to_status.value
    merchant.status_reason = note
    session.add(
        MerchantVerification(
            merchant_id=merchant.id,
            from_status=from_status,
            to_status=to_status.value,
            actor_user_id=actor_user_id,
            note=note,
        )
    )


async def submit_application(session: AsyncSession, merchant: Merchant) -> Merchant:
    if MerchantStatus(merchant.status) not in EDITABLE_STATUSES:
        raise Conflict("The application has already been submitted.", code="already_submitted")
    missing: list[str] = []
    profile = merchant.profile
    if not merchant.category_id:
        missing.append("category_id")
    if len(profile.business_description.strip()) < 20:
        missing.append("business_description")
    if BusinessType(merchant.business_type) in CR_REQUIRED_TYPES and not merchant.commercial_registration_number:
        missing.append("commercial_registration_number")
    has_address = (
        await session.exec(select(MerchantAddress.id).where(MerchantAddress.merchant_id == merchant.id))
    ).first()
    if not has_address:
        missing.append("address")
    if missing:
        raise ValidationFailed("The application is incomplete.", code="application_incomplete", details=missing)
    merchant.submitted_at = utcnow()
    await _set_status(session, merchant, MerchantStatus.SUBMITTED, actor_user_id=merchant.owner_user_id, note=None)
    await session.flush()
    return merchant


async def transition(
    session: AsyncSession,
    merchant: Merchant,
    to_status: MerchantStatus,
    *,
    actor_user_id: uuid.UUID,
    reason: str | None,
    ip: str | None = None,
) -> Merchant:
    current = MerchantStatus(merchant.status)
    if to_status not in ADMIN_TRANSITIONS.get(current, set()):
        raise Conflict(f"Cannot change merchant status from {current} to {to_status}.", code="invalid_transition")
    if (
        to_status in {MerchantStatus.REJECTED, MerchantStatus.ADDITIONAL_INFO_REQUIRED, MerchantStatus.SUSPENDED}
        and not reason
    ):
        raise ValidationFailed("A reason is required.", code="reason_required")
    before = {"status": merchant.status}
    await _set_status(session, merchant, to_status, actor_user_id=actor_user_id, note=reason)
    store = await get_store(session, merchant.id)
    data = {"business_name": merchant.business_name, "reason": reason or ""}
    if to_status == MerchantStatus.APPROVED:
        merchant.approved_at = merchant.approved_at or utcnow()
        if store is not None:
            store.status = StoreStatus.ACTIVE.value
        await notify(session, merchant.owner_user_id, NotificationType.MERCHANT_APPROVED, data)
    elif to_status == MerchantStatus.SUSPENDED:
        if store is not None:
            store.status = StoreStatus.SUSPENDED.value
        await notify(session, merchant.owner_user_id, NotificationType.ACCOUNT_SUSPENDED, data)
    elif to_status == MerchantStatus.REJECTED:
        await notify(session, merchant.owner_user_id, NotificationType.MERCHANT_REJECTED, data)
    elif to_status == MerchantStatus.ADDITIONAL_INFO_REQUIRED:
        await notify(session, merchant.owner_user_id, NotificationType.MERCHANT_INFO_REQUIRED, data)
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action=f"merchant.{to_status.value.lower()}",
        entity_type="merchant",
        entity_id=merchant.id,
        before=before,
        after={"status": merchant.status, "reason": reason},
        ip_address=ip,
    )
    await session.flush()
    return merchant


# -- payment onboarding ----------------------------------------------------------------


def _provider_name(merchant: Merchant) -> str:
    """A machine-friendly name (alphanumeric and underscores) for the provider."""
    base = re.sub(r"[^a-z0-9]+", "_", merchant.business_name.lower()).strip("_")[:40] or "merchant"
    return f"{base}_{merchant.id.hex[:8]}"


def _document_key(doc: dict[str, object]) -> tuple[str, str | None]:
    doc_type = doc.get("type") or doc.get("document_type") or doc.get("name") or "document"
    doc_id = doc.get("id")
    return str(doc_type)[:60], (str(doc_id)[:100] if doc_id else None)


async def _sync_document_references(
    session: AsyncSession, account: MerchantPaymentAccount, remote: ProviderMerchantAccount
) -> None:
    """Mirror the provider's document requirements. Only references are kept; the
    files themselves are submitted to and held by the provider."""
    rows = {
        r.document_type: r
        for r in (
            await session.exec(
                select(MerchantDocumentReference).where(
                    MerchantDocumentReference.merchant_id == account.merchant_id,
                    MerchantDocumentReference.provider == account.provider,
                )
            )
        ).all()
    }
    required: set[str] = set()
    for doc in remote.required_documents:
        doc_type, doc_id = _document_key(doc)
        required.add(doc_type)
        row = rows.get(doc_type)
        if row is None:
            row = MerchantDocumentReference(
                merchant_id=account.merchant_id, provider=account.provider, document_type=doc_type
            )
            session.add(row)
            rows[doc_type] = row
        row.status = DocumentStatus.REQUIRED.value
        row.provider_document_id = doc_id or row.provider_document_id
    for doc_type, row in rows.items():
        if doc_type not in required and row.status == DocumentStatus.REQUIRED.value:
            # The provider no longer asks for it: it was supplied through the provider's process.
            row.status = DocumentStatus.SATISFIED.value


async def _apply_provider_state(
    session: AsyncSession, account: MerchantPaymentAccount, remote: ProviderMerchantAccount
) -> None:
    await _sync_document_references(session, account, remote)
    account.provider_account_id = remote.provider_account_id
    account.recipient_id = remote.recipient_id
    account.onboarding_status = remote.onboarding_status.value
    account.verification_status = remote.raw_status
    if remote.payouts_enabled is True:
        account.payout_status = PayoutStatus.ENABLED.value
    elif remote.payouts_enabled is False:
        account.payout_status = PayoutStatus.DISABLED.value
    account.provider_details = {
        **remote.details,
        "required_documents": remote.required_documents,
        "reasons": remote.reasons,
    }
    account.last_synced_at = utcnow()
    account.last_error = None


async def start_payment_onboarding(
    session: AsyncSession,
    merchant: Merchant,
    data: PaymentOnboardingRequest,
    provider: PaymentProvider,
) -> MerchantPaymentAccount:
    if merchant.status != MerchantStatus.APPROVED:
        raise Conflict("Payment onboarding starts after the platform approves your application.", code="not_approved")
    account = await get_payment_account(session, merchant.id, provider.name, lock=True)
    if account is not None and account.provider_account_id:
        raise Conflict("Payment onboarding has already started. Use sync or submit.", code="onboarding_exists")
    if account is None:
        account = MerchantPaymentAccount(
            merchant_id=merchant.id,
            provider=provider.name,
            is_test=provider.is_test,
            onboarding_status=OnboardingStatus.NOT_STARTED.value,
            payout_status=PayoutStatus.UNKNOWN.value,
            provider_details={},
            attempts=0,
        )
        session.add(account)

    # Only a masked reference of the IBAN is stored; the provider verifies the account.
    await session.exec(
        update(MerchantBankAccountReference)
        .where(col(MerchantBankAccountReference.merchant_id) == merchant.id)
        .values(is_active=False)
    )
    iban = data.bank_account.iban
    session.add(
        MerchantBankAccountReference(
            merchant_id=merchant.id,
            beneficiary_name=data.bank_account.beneficiary_name,
            bank_name=data.bank_account.bank_name,
            iban_masked=mask_iban(iban),
            iban_last4=iban[-4:],
            is_active=True,
        )
    )
    merchant.profile.website = str(data.website)
    account.attempts += 1
    owner = await session.get(User, merchant.owner_user_id)
    assert owner is not None
    try:
        remote = await provider.create_merchant_account(
            MerchantAccountInput(
                merchant_id=str(merchant.id),
                business_type=merchant.business_type,
                name=_provider_name(merchant),
                public_name=merchant.business_name,
                email=merchant.profile.contact_email,
                admin_email=owner.email,
                website=str(data.website),
                owners_count=data.owners_count,
                signatory=data.signatory,
                signatory_count=data.signatory_count if data.signatory != "owner" else None,
                activity_license_required=data.activity_license_required,
            )
        )
    except AppError as exc:
        # Persist the failed attempt so it can be retried; do not lose the record.
        account.onboarding_status = OnboardingStatus.FAILED.value
        account.last_error = exc.message
        log.warning("merchant_onboarding_failed", merchant_id=str(merchant.id), error=exc.message)
        await session.flush()
        return account
    await _apply_provider_state(session, account, remote)
    await session.flush()
    return account


async def _require_remote_account(
    session: AsyncSession, merchant: Merchant, provider: PaymentProvider
) -> MerchantPaymentAccount:
    account = await get_payment_account(session, merchant.id, provider.name, lock=True)
    if account is None or not account.provider_account_id:
        raise NotFound("Payment onboarding has not started.", code="onboarding_not_started")
    return account


async def submit_payment_onboarding(
    session: AsyncSession, merchant: Merchant, provider: PaymentProvider
) -> MerchantPaymentAccount:
    account = await _require_remote_account(session, merchant, provider)
    assert account.provider_account_id
    try:
        remote = await provider.submit_merchant_account(account.provider_account_id)
    except AppError as exc:
        account.last_error = exc.message
        await session.flush()
        return account
    await _apply_provider_state(session, account, remote)
    await session.flush()
    return account


async def sync_payment_account(
    session: AsyncSession, account: MerchantPaymentAccount, provider: PaymentProvider
) -> MerchantPaymentAccount:
    assert account.provider_account_id
    try:
        remote = await provider.get_merchant_account(account.provider_account_id)
    except AppError as exc:
        account.last_error = exc.message
        await session.flush()
        return account
    await _apply_provider_state(session, account, remote)
    await session.flush()
    return account


async def sync_payment_onboarding(
    session: AsyncSession, merchant: Merchant, provider: PaymentProvider
) -> MerchantPaymentAccount:
    account = await _require_remote_account(session, merchant, provider)
    return await sync_payment_account(session, account, provider)


async def payment_account_out(
    session: AsyncSession, merchant: Merchant, provider: PaymentProvider
) -> PaymentAccountOut:
    account = await get_payment_account(session, merchant.id, provider.name)
    bank = (
        await session.exec(
            select(MerchantBankAccountReference).where(
                MerchantBankAccountReference.merchant_id == merchant.id,
                col(MerchantBankAccountReference.is_active).is_(True),
            )
        )
    ).first()
    await session.flush()  # documents are reloaded below with populate_existing
    store = await get_store(session, merchant.id)
    details = account.provider_details if account else {}
    return PaymentAccountOut(
        provider=provider.name,
        is_test=account.is_test if account else provider.is_test,
        provider_account_id=account.provider_account_id if account else None,
        recipient_id=account.recipient_id if account else None,
        onboarding_status=account.onboarding_status if account else OnboardingStatus.NOT_STARTED.value,
        verification_status=account.verification_status if account else None,
        payout_status=account.payout_status if account else PayoutStatus.UNKNOWN.value,
        required_documents=list(details.get("required_documents") or []),  # type: ignore[call-overload]
        reasons=list(details.get("reasons") or []),  # type: ignore[call-overload]
        attempts=account.attempts if account else 0,
        last_error=account.last_error if account else None,
        last_synced_at=account.last_synced_at if account else None,
        can_accept_payments=can_accept_payments(merchant, store, account),
        bank_account=BankAccountOut.model_validate(bank) if bank else None,
        documents=[
            DocumentReferenceOut.model_validate(d)
            for d in (
                await session.exec(
                    select(MerchantDocumentReference)
                    .where(
                        MerchantDocumentReference.merchant_id == merchant.id,
                        MerchantDocumentReference.provider == provider.name,
                    )
                    .order_by(MerchantDocumentReference.document_type)
                    .execution_options(populate_existing=True)
                )
            ).all()
        ],
    )
