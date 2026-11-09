"""Mock provider endpoints (development and tests only; never mounted in production).

They simulate what a real provider does outside our system: the hosted payment
page, merchant review decisions, bank settlements and chargebacks. Every action
emits a signed webhook that goes through the normal webhook pipeline.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.core.errors import NotFound
from app.database.session import DbSession
from app.integrations.payments.factory import get_payment_provider
from app.integrations.payments.mock import MockPaymentProvider
from app.integrations.payments.mock_models import MockRecordKind
from app.modules.payments import webhooks

router = APIRouter(prefix="/mock-provider", tags=["mock-provider (test only)"])


def _mock() -> MockPaymentProvider:
    provider = get_payment_provider()
    if not isinstance(provider, MockPaymentProvider):
        raise NotFound("Mock provider is not active.")
    return provider


async def _emit(db: DbSession, provider: MockPaymentProvider, event_type: str, data: dict[str, object]) -> str:
    result = await webhooks.handle_webhook(db, provider, provider.build_webhook(event_type, data))
    return result.outcome


@router.get("/payments/{payment_id}/checkout", response_class=HTMLResponse)
async def hosted_checkout(payment_id: str) -> HTMLResponse:
    provider = _mock()
    data = await provider.read(MockRecordKind.PAYMENT, payment_id)
    amount = f"{data['amount'] / 100:.2f}"
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Mock payment</title></head>
<body style="font-family:system-ui;max-width:480px;margin:3rem auto">
<p style="background:#fde68a;padding:.5rem"><strong>TEST MODE — mock provider, no real money.</strong></p>
<h1>Pay {amount} SAR</h1>
<form method="post" action="/api/v1/mock-provider/payments/{payment_id}/complete">
<button name="outcome" value="paid">Approve payment</button>
<button name="outcome" value="failed">Decline payment</button>
</form></body></html>"""
    )


@router.post("/payments/{payment_id}/complete")
async def complete_hosted_payment(
    payment_id: str, outcome: Annotated[Literal["paid", "failed"], Form()], db: DbSession
) -> RedirectResponse:
    provider = _mock()
    remote = await provider.complete_hosted_payment(payment_id, outcome)
    await _emit(db, provider, f"payment.{remote.raw_status}", {"id": payment_id})
    callback = str(remote.raw.get("callback_url") or "/")
    return RedirectResponse(f"{callback}&status={remote.raw_status}" if "?" in callback else callback, status_code=303)


class MerchantStatusIn(BaseModel):
    status: Literal["pending", "under_review", "missing_docs", "active", "rejected", "disabled"]
    reasons: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)


@router.post("/merchants/{account_id}/status")
async def set_merchant_status(account_id: str, body: MerchantStatusIn, db: DbSession) -> dict[str, str]:
    provider = _mock()
    await provider.set_merchant_status(account_id, body.status, body.reasons, body.required_documents)
    return {"outcome": await _emit(db, provider, "merchant.updated", {"id": account_id})}


class SettlementIn(BaseModel):
    recipient_id: str
    amount: int = Field(gt=0)
    failed: bool = False


@router.post("/settlements")
async def create_settlement(body: SettlementIn, db: DbSession) -> dict[str, str]:
    provider = _mock()
    settlement = await provider.create_settlement(body.recipient_id, body.amount, failed=body.failed)
    outcome = await _emit(db, provider, "settlement.updated", {"id": settlement.provider_settlement_id})
    return {"outcome": outcome, "provider_settlement_id": settlement.provider_settlement_id}


class ChargebackIn(BaseModel):
    amount: int = Field(gt=0)
    status: Literal["OPEN", "WON", "LOST"] = "OPEN"
    reference: str | None = None


@router.post("/payments/{payment_id}/chargebacks")
async def chargeback(payment_id: str, body: ChargebackIn, db: DbSession) -> dict[str, str]:
    provider = _mock()
    cb = await provider.upsert_chargeback(payment_id, body.amount, body.status, body.reference)
    outcome = await _emit(db, provider, "chargeback.updated", {"id": cb.provider_reference})
    return {"outcome": outcome, "reference": cb.provider_reference}
