"""/api/v1/merchants, /api/v1/merchants/onboarding, /api/v1/merchants/payment-account"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlmodel import col, select

from app.api.deps import CurrentMerchant, rate_limit
from app.database.session import DbSession
from app.integrations.payments.factory import ProviderDep
from app.modules.auth.router import _login_response
from app.modules.auth.schemas import TokenResponse
from app.modules.merchants import service
from app.modules.merchants.models import MerchantVerification
from app.modules.merchants.schemas import (
    MerchantOut,
    MerchantRegisterRequest,
    OnboardingUpdate,
    PaymentAccountOut,
    PaymentOnboardingRequest,
    VerificationEventOut,
)

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit("auth"))])
async def register_merchant(
    body: MerchantRegisterRequest, request: Request, response: Response, db: DbSession
) -> TokenResponse:
    user, _ = await service.register_merchant(db, body)
    return await _login_response(db, user, request, response)


@router.get("/me")
async def get_me(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> MerchantOut:
    return await service.merchant_out(db, ctx.merchant, provider.name)


@router.get("/onboarding")
async def get_onboarding(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> MerchantOut:
    return await service.merchant_out(db, ctx.merchant, provider.name)


@router.patch("/onboarding")
async def update_onboarding(
    body: OnboardingUpdate, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> MerchantOut:
    merchant = await service.update_onboarding(db, ctx.merchant, body)
    return await service.merchant_out(db, merchant, provider.name)


@router.post("/onboarding/submit")
async def submit_onboarding(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> MerchantOut:
    merchant = await service.submit_application(db, ctx.merchant)
    return await service.merchant_out(db, merchant, provider.name)


@router.get("/onboarding/history")
async def onboarding_history(ctx: CurrentMerchant, db: DbSession) -> list[VerificationEventOut]:
    rows = await db.exec(
        select(MerchantVerification)
        .where(MerchantVerification.merchant_id == ctx.merchant_id)
        .order_by(col(MerchantVerification.created_at))
    )
    return [VerificationEventOut.model_validate(r) for r in rows.all()]


@router.get("/payment-account")
async def get_payment_account(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> PaymentAccountOut:
    return await service.payment_account_out(db, ctx.merchant, provider)


@router.post("/payment-account")
async def start_payment_onboarding(
    body: PaymentOnboardingRequest, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> PaymentAccountOut:
    await service.start_payment_onboarding(db, ctx.merchant, body, provider)
    return await service.payment_account_out(db, ctx.merchant, provider)


@router.post("/payment-account/submit")
async def submit_payment_onboarding(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> PaymentAccountOut:
    await service.submit_payment_onboarding(db, ctx.merchant, provider)
    return await service.payment_account_out(db, ctx.merchant, provider)


@router.post("/payment-account/sync")
async def sync_payment_onboarding(ctx: CurrentMerchant, db: DbSession, provider: ProviderDep) -> PaymentAccountOut:
    await service.sync_payment_onboarding(db, ctx.merchant, provider)
    return await service.payment_account_out(db, ctx.merchant, provider)
