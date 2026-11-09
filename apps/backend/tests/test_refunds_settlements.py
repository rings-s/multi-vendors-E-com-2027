"""Refunds, chargebacks, settlements and reconciliation."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DBAPIError

from tests import db
from tests.helpers import (
    API,
    Actor,
    Client,
    active_merchant,
    create_admin,
    create_product,
    paid_order,
    register_customer,
)


async def _setup(client: Client, price: int = 10000) -> tuple[Actor, Actor, Actor, dict, dict]:  # type: ignore[type-arg]
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant, price=price, stock=10)
    customer = await register_customer(client)
    order, mo = await paid_order(client, customer, product)
    return admin, merchant, customer, order, mo


async def test_full_refund_reverses_each_allocation_exactly(client: Client) -> None:
    _admin, merchant, customer, order, mo = await _setup(client)
    refund = await client.post(
        f"{API}/merchant/orders/{mo['id']}/refunds", merchant, json={"reason": "Customer returned item"}, expect=201
    )
    assert refund["status"] == "SUCCEEDED"
    assert refund["amount"] == 11500
    assert refund["platform_portion"] == 1000 and refund["merchant_portion"] == 10500
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    payment = await client.get(f"{API}/payments/{mo['payment']['id']}", customer)
    assert payment["status"] == "REFUNDED" and payment["refunded_amount"] == 11500
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    assert order["merchant_orders"][0]["status"] == "REFUNDED"
    postings = await db.ledger_postings(refund["id"])
    assert sorted(postings[0]["entries"]) == sorted([("DEBIT", 10500), ("DEBIT", 1000), ("CREDIT", 11500)])
    await db.assert_ledger_consistent()


async def test_partial_refunds_are_proportional_and_cannot_exceed_refundable(client: Client) -> None:
    admin, merchant, customer, _, mo = await _setup(client)
    url = f"{API}/admin/payments/{mo['payment']['id']}/refunds"
    first = await client.post(url, admin, json={"amount": 3333, "reason": "Partial goodwill refund"}, expect=201)
    # Platform portion = round_half_up(3333 * 1000 / 11500) = 290
    assert first["platform_portion"] == 290 and first["merchant_portion"] == 3043
    payment = await client.get(f"{API}/payments/{mo['payment']['id']}", customer)
    assert payment["status"] == "PARTIALLY_REFUNDED"

    too_much = await client.request("POST", url, admin, json={"amount": 8168, "reason": "Too much"})
    assert too_much.status_code == 422
    assert too_much.json()["error"]["code"] == "refund_exceeds_refundable"
    assert too_much.json()["error"]["details"]["refundable"] == 8167

    rest = await client.post(url, admin, json={"reason": "Refund remaining balance"}, expect=201)
    assert rest["amount"] == 8167
    # Cumulative reversal equals the original allocations exactly — no rounding drift.
    assert first["platform_portion"] + rest["platform_portion"] == 1000
    assert first["merchant_portion"] + rest["merchant_portion"] == 10500
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0

    nothing_left = await client.request("POST", url, admin, json={"amount": 1, "reason": "Nothing left"})
    assert nothing_left.status_code in (409, 422)
    await db.assert_ledger_consistent()


async def test_customer_refund_request_requires_merchant_decision(client: Client) -> None:
    _admin, merchant, customer, order, mo = await _setup(client)
    request = await client.post(
        f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/refund-requests",
        customer,
        json={"amount": 5000, "reason": "Item arrived damaged"},
        expect=None,
    )
    assert request["status"] == "REQUESTED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500  # nothing reversed yet

    pending = await client.get(f"{API}/merchant/refunds", merchant, params={"status": "REQUESTED"})
    assert request["id"] in {r["id"] for r in pending["items"]}
    decided = await client.post(f"{API}/merchant/refunds/{request['id']}/decision", merchant, json={"approve": True})
    assert decided["status"] == "SUCCEEDED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) < 10500

    # A second request can be rejected.
    second = await client.post(
        f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/refund-requests",
        customer,
        json={"amount": 1000, "reason": "Changed my mind"},
        expect=None,
    )
    rejected = await client.post(
        f"{API}/merchant/refunds/{second['id']}/decision", merchant, json={"approve": False, "note": "Used item"}
    )
    assert rejected["status"] == "REJECTED"
    types = {n["type"] for n in (await client.get(f"{API}/notifications", customer))["items"]}
    assert "refund_status" in types


async def test_merchant_cancellation_of_paid_order_refunds_customer(client: Client) -> None:
    _admin, merchant, customer, order, mo = await _setup(client)
    await client.post(f"{API}/merchant/orders/{mo['id']}/reject", merchant, json={"reason": "Out of stock locally"})
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    mo = order["merchant_orders"][0]
    assert mo["status"] == "REJECTED"
    assert mo["payment"]["status"] == "REFUNDED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    await db.assert_ledger_consistent()


async def test_fulfillment_flow(client: Client) -> None:
    _admin, merchant, customer, order, mo = await _setup(client)
    url = f"{API}/merchant/orders/{mo['id']}/fulfillment"
    await client.post(url, merchant, json={"status": "ACCEPTED"})
    await client.post(url, merchant, json={"status": "PROCESSING"})
    await client.post(url, merchant, json={"status": "SHIPPED", "carrier": "SMSA", "tracking_number": "SMSA123"})
    # Invalid backwards transition.
    response = await client.request("POST", url, merchant, json={"status": "ACCEPTED"})
    assert response.status_code == 409
    await client.post(url, merchant, json={"status": "DELIVERED"})
    order = await client.get(f"{API}/orders/{order['id']}", customer)
    mo = order["merchant_orders"][0]
    assert mo["status"] == "DELIVERED"
    assert mo["shipments"][0]["tracking_number"] == "SMSA123"
    history = await client.get(f"{API}/orders/{order['id']}/history", customer)
    assert "DELIVERED" in [h["to_status"] for h in history if h["merchant_order_id"] == mo["id"]]
    receipt = await client.request(
        "GET", f"{API}/orders/{order['id']}/merchant-orders/{mo['id']}/receipt", customer, expect=200
    )
    assert mo["number"] in receipt.text


async def _recipient(client: Client, merchant: Actor) -> str:
    account = await client.get(f"{API}/merchants/payment-account", merchant)
    return account["recipient_id"]


async def test_settlement_completes_only_with_provider_confirmation(client: Client) -> None:
    _admin, merchant, _customer, _, _mo = await _setup(client)
    merchant_id = merchant.extra["merchant_id"]
    # Payment success is not settlement.
    settlements = await client.get(f"{API}/merchant/settlements", merchant)
    assert settlements["total"] == 0
    summary = (await client.get(f"{API}/merchant/earnings", merchant))["summary"]
    assert summary["pending_settlement"] == 10500 and summary["completed_settlements"] == 0

    # The provider reports a completed bank transfer (signed webhook + provider lookup).
    result = await client.post(
        f"{API}/mock-provider/settlements", json={"recipient_id": await _recipient(client, merchant), "amount": 10500}
    )
    assert result["outcome"] == "processed"
    settlements = await client.get(f"{API}/merchant/settlements", merchant)
    settlement = settlements["items"][0]
    assert settlement["status"] == "COMPLETED"
    assert settlement["confirmation_source"] == "PROVIDER_WEBHOOK"
    assert settlement["completed_at"] is not None
    assert await db.merchant_payable(merchant_id) == 0
    summary = (await client.get(f"{API}/merchant/earnings", merchant))["summary"]
    assert summary["pending_settlement"] == 0 and summary["completed_settlements"] == 10500
    assert summary["net_earnings"] == 10500
    types = {n["type"] for n in (await client.get(f"{API}/notifications", merchant))["items"]}
    assert "settlement_completed" in types
    await db.assert_ledger_consistent()


async def test_failed_settlement_keeps_balance_pending(client: Client) -> None:
    _admin, merchant, _customer, _, _mo = await _setup(client)
    await client.post(
        f"{API}/mock-provider/settlements",
        json={"recipient_id": await _recipient(client, merchant), "amount": 10500, "failed": True},
    )
    settlement = (await client.get(f"{API}/merchant/settlements", merchant))["items"][0]
    assert settlement["status"] == "FAILED" and settlement["failure_reason"]
    assert settlement["completed_at"] is None
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500
    summary = (await client.get(f"{API}/merchant/earnings", merchant))["summary"]
    assert summary["failed_settlements"] == 1


async def test_reconciled_settlement_requires_super_admin_and_provider_record(client: Client) -> None:
    from tests.test_payments import mock_provider

    admin, merchant, _customer, _, _mo = await _setup(client)
    regular_admin = await create_admin(client, super_admin=False)
    # A transfer exists in the provider's records but its webhook never arrived.
    remote = await mock_provider().create_settlement(await _recipient(client, merchant), 10500)
    body = {
        "merchant_id": merchant.extra["merchant_id"],
        "amount": 10500,
        "provider_settlement_id": remote.provider_settlement_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "evidence_reference": "Provider statement 2026-11",
    }
    forbidden = await client.request("POST", f"{API}/admin/settlements/reconciled", regular_admin, json=body)
    assert forbidden.status_code == 403
    missing = await client.request(
        "POST", f"{API}/admin/settlements/reconciled", admin, json={**body, "evidence_reference": ""}
    )
    assert missing.status_code == 422
    # A settlement id the provider does not know cannot be marked complete.
    unknown = await client.request(
        "POST", f"{API}/admin/settlements/reconciled", admin, json={**body, "provider_settlement_id": "stmt-unknown"}
    )
    assert unknown.status_code == 404
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500

    settlement = await client.post(f"{API}/admin/settlements/reconciled", admin, json=body, expect=201)
    assert settlement["status"] == "COMPLETED"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    logs = await client.get(f"{API}/admin/audit-logs", admin, params={"entity_id": settlement["id"]})
    assert logs["total"] == 1


async def test_chargeback_lost_reverses_and_won_restores(client: Client) -> None:
    admin, merchant, _customer, _, mo = await _setup(client)
    payment_id = mo["payment"]["id"]
    reference = f"cb-{uuid.uuid4().hex[:8]}"
    await client.post(
        f"{API}/mock-provider/payments/{payment_id}/chargebacks", json={"amount": 11500, "reference": reference}
    )
    payment = await client.get(f"{API}/admin/payments/{payment_id}", admin)
    assert payment["status"] == "DISPUTED"
    # Disputed funds are held: the merchant payable is reduced while the dispute is open.
    held = await db.merchant_payable(merchant.extra["merchant_id"])
    assert held <= 10500

    await client.post(
        f"{API}/mock-provider/payments/{payment_id}/chargebacks",
        json={"amount": 11500, "reference": reference, "status": "WON"},
    )
    payment = await client.get(f"{API}/admin/payments/{payment_id}", admin)
    assert payment["status"] == "PAID"
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 10500
    chargebacks = await client.get(f"{API}/admin/chargebacks", admin)
    assert any(c["payment_id"] == payment_id and c["status"] == "WON" for c in chargebacks["items"])
    await db.assert_ledger_consistent()


async def test_chargeback_lost_reduces_merchant_earnings(client: Client) -> None:
    _admin, merchant, _customer, _, mo = await _setup(client)
    payment_id = mo["payment"]["id"]
    reference = f"cb-{uuid.uuid4().hex[:8]}"
    for status in ("OPEN", "LOST"):
        await client.post(
            f"{API}/mock-provider/payments/{payment_id}/chargebacks",
            json={"amount": 11500, "reference": reference, "status": status},
        )
    assert await db.merchant_payable(merchant.extra["merchant_id"]) == 0
    summary = (await client.get(f"{API}/merchant/earnings", merchant))["summary"]
    assert summary["chargebacks"] == 11500
    await db.assert_ledger_consistent()


async def test_reconciliation_matches_provider_records(client: Client) -> None:
    admin, _merchant, _customer, _, mo = await _setup(client)
    run = await client.post(f"{API}/admin/reconciliation", admin, json={}, expect=201)
    assert run["status"] == "COMPLETED"
    mismatches = [d for d in run["details"] if d.get("payment_id") == mo["payment"]["id"]]
    assert mismatches == []
    runs = await client.get(f"{API}/admin/reconciliation", admin)
    assert runs["total"] >= 1


async def test_ledger_entries_are_immutable() -> None:
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute("UPDATE ledger_entries SET amount = amount + 1")
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute("DELETE FROM ledger_transactions")
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute("DELETE FROM audit_logs")


async def test_unbalanced_ledger_transaction_is_rejected_by_database(client: Client) -> None:
    from app.database.session import get_sessionmaker
    from app.modules.ledger import service as ledger
    from app.modules.ledger.models import AccountType, Direction, LedgerTransactionType

    with pytest.raises(Exception, match=r"(?i)balanc"):
        async with get_sessionmaker()() as session, session.begin():
            await ledger.post(
                session,
                transaction_type=LedgerTransactionType.REVERSAL,
                source_type="test",
                source_id=uuid.uuid4(),
                merchant_id=None,
                description="unbalanced",
                is_test=True,
                lines=[
                    ledger.Line(AccountType.PROVIDER_CLEARING, Direction.DEBIT, 100),
                    ledger.Line(AccountType.PLATFORM_COMMISSION, Direction.CREDIT, 99),
                ],
            )
