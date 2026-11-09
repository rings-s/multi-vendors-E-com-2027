"""Generic data admin: CRUD on every table, permissions, constraints and audit."""

import uuid
from typing import Any

from app.modules.ledger.models import LedgerEntry  # noqa: F401  (model registered)
from tests.helpers import (
    API,
    PASSWORD,
    Client,
    active_merchant,
    create_admin,
    create_product,
    paid_order,
    register_customer,
)

DATA = f"{API}/admin/data"


async def test_every_table_is_registered_and_listable(client: Client) -> None:
    admin = await create_admin(client)
    models = await client.get(f"{DATA}/models", admin)
    keys = {m["key"] for m in models}
    from sqlmodel import SQLModel

    assert keys == set(SQLModel.metadata.tables)
    for key in sorted(keys):
        schema = await client.get(f"{DATA}/models/{key}", admin)
        assert schema["pk"] and schema["fields"]
        page = await client.get(f"{DATA}/{key}", admin, params={"page_size": 5})
        assert page["total"] >= len(page["items"])
        for item in page["items"]:
            detail = await client.get(f"{DATA}/{key}/{item['pk']}", admin)
            assert detail["pk"] == item["pk"]


async def test_full_crud_with_audit_and_cache(client: Client) -> None:
    admin = await create_admin(client)
    slug = f"data-{uuid.uuid4().hex[:8]}"
    created = await client.post(
        f"{DATA}/categories",
        admin,
        json={"slug": slug, "name_en": "Data cat", "name_ar": "تصنيف", "kind": "PRODUCT"},
        expect=201,
    )
    pk = created["pk"]
    assert created["values"]["is_active"] is True  # model default applied
    assert created["label"] == "Data cat"
    # Visible through the public (cached) endpoint immediately.
    public = await client.get(f"{API}/categories")
    assert any(c["slug"] == slug for c in public)

    found = await client.get(f"{DATA}/categories", admin, params={"q": slug})
    assert [i["pk"] for i in found["items"]] == [pk]
    filtered = await client.get(f"{DATA}/categories", admin, params={"kind": "PRODUCT", "slug__icontains": slug})
    assert filtered["total"] == 1

    updated = await client.patch(f"{DATA}/categories/{pk}", admin, json={"name_en": "Renamed", "is_active": False})
    assert updated["values"]["name_en"] == "Renamed"
    assert updated["values"]["slug"] == slug

    preview = await client.post(f"{DATA}/categories/delete-preview", admin, json={"pks": [pk]})
    assert preview["objects"][0]["label"] == "Renamed"
    assert preview["protected"] == []
    await client.delete(f"{DATA}/categories/{pk}", admin)
    await client.get(f"{DATA}/categories/{pk}", admin, expect=404)

    logs = await client.get(f"{API}/admin/audit-logs", admin, params={"entity_type": "categories", "entity_id": pk})
    assert sorted(entry["action"] for entry in logs["items"]) == ["data.create", "data.delete", "data.update"]
    update_log = next(entry for entry in logs["items"] if entry["action"] == "data.update")
    assert update_log["before"] == {
        "name_en": "Data cat",
        "is_active": True,
        "updated_at": update_log["before"]["updated_at"],
    }


async def test_validation_errors_are_field_level(client: Client) -> None:
    admin = await create_admin(client)
    missing = await client.request("POST", f"{DATA}/categories", admin, json={"kind": "NOPE", "sort_order": "x"})
    assert missing.status_code == 422
    fields = {tuple(d["loc"]) for d in missing.json()["error"]["details"]}
    assert {("body", "kind"), ("body", "sort_order"), ("body", "slug"), ("body", "name_en")} <= fields

    slug = f"dup-{uuid.uuid4().hex[:8]}"
    body = {"slug": slug, "name_en": "A", "name_ar": "ب"}
    await client.post(f"{DATA}/categories", admin, json=body, expect=201)
    duplicate = await client.request("POST", f"{DATA}/categories", admin, json=body)
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["details"][0]["loc"] == ["body", "slug"]

    bad_fk = await client.request(
        "POST", f"{DATA}/categories", admin, json={**body, "slug": slug + "x", "parent_id": str(uuid.uuid4())}
    )
    assert bad_fk.status_code == 422
    assert bad_fk.json()["error"]["details"][0]["loc"] == ["body", "parent_id"]


async def test_users_password_is_write_only_and_hashed(client: Client) -> None:
    admin = await create_admin(client)
    email = f"data-user-{uuid.uuid4().hex[:8]}@example.com"
    created = await client.post(
        f"{DATA}/users", admin, json={"email": email, "full_name": "Data User", "password": PASSWORD}, expect=201
    )
    assert "password_hash" not in created["values"]
    await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})

    new_password = "another-long-password-42"
    await client.patch(f"{DATA}/users/{created['pk']}", admin, json={"password": new_password})
    old = await client.request("POST", f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert old.status_code == 401
    await client.post(f"{API}/auth/login", json={"email": email, "password": new_password})

    # Grant a role through the link table (composite primary key).
    roles = await client.get(f"{DATA}/roles", admin, params={"q": "MERCHANT"})
    role_pk = roles["items"][0]["pk"]
    link = await client.post(
        f"{DATA}/user_roles", admin, json={"user_id": created["pk"], "role_id": role_pk}, expect=201
    )
    assert link["pk"] == f"{created['pk']},{role_pk}"
    assert email in link["label"] and "MERCHANT" in link["label"]
    await client.delete(f"{DATA}/user_roles/{link['pk']}", admin)

    self_delete = await client.request("DELETE", f"{DATA}/users/{admin.user['id']}", admin)
    assert self_delete.status_code == 403


async def test_relations_and_protected_deletes(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    order, _ = await paid_order(client, customer, product)

    detail = await client.get(f"{DATA}/orders/{order['id']}", admin)
    related = {(r["model"], r["field"]) for r in detail["related"]}
    assert ("merchant_orders", "order_id") in related
    assert detail["fk_labels"]["customer_user_id"][customer.user["id"]] == customer.user["email"]

    preview = await client.post(f"{DATA}/orders/delete-preview", admin, json={"pks": [order["id"]]})
    assert any(p["model"] == "merchant_orders" for p in preview["protected"])
    blocked = await client.request("DELETE", f"{DATA}/orders/{order['id']}", admin)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "protected_relation"

    # Lookups for foreign-key pickers.
    users = await client.get(f"{DATA}/users/lookup", admin, params={"q": customer.user["email"]})
    assert users == [{"pk": customer.user["id"], "label": customer.user["email"]}]


async def test_permissions(client: Client) -> None:
    regular = await create_admin(client, super_admin=False)
    await client.get(f"{DATA}/models", regular)
    await client.get(f"{DATA}/categories", regular)
    denied = await client.request(
        "POST", f"{DATA}/categories", regular, json={"slug": "x", "name_en": "x", "name_ar": "x"}
    )
    assert denied.status_code == 403
    customer = await register_customer(client)
    assert (await client.request("GET", f"{DATA}/models", customer)).status_code == 403
    assert (await client.request("GET", f"{DATA}/nope", regular)).status_code == 404


async def test_bulk_delete_is_atomic(client: Client) -> None:
    admin = await create_admin(client)
    pks = []
    for _ in range(3):
        slug = f"bulk-{uuid.uuid4().hex[:8]}"
        row = await client.post(
            f"{DATA}/categories", admin, json={"slug": slug, "name_en": slug, "name_ar": slug}, expect=201
        )
        pks.append(row["pk"])
    missing = await client.request(
        "POST", f"{DATA}/categories/bulk-delete", admin, json={"pks": [*pks, str(uuid.uuid4())]}
    )
    assert missing.status_code == 404
    assert (await client.get(f"{DATA}/categories", admin, params={"id__in": ",".join(pks)}))["total"] == 3
    result = await client.post(f"{DATA}/categories/bulk-delete", admin, json={"pks": pks})
    assert result == {"deleted": 3}


async def test_references_from_append_only_tables_protect_deletes(client: Client) -> None:
    admin = await create_admin(client)
    other = await create_admin(client)
    # `other` writes through the admin, so the immutable audit log references it.
    slug = f"audit-{uuid.uuid4().hex[:8]}"
    await client.post(f"{DATA}/categories", other, json={"slug": slug, "name_en": slug, "name_ar": slug}, expect=201)
    preview = await client.post(f"{DATA}/users/delete-preview", admin, json={"pks": [other.user["id"]]})
    assert any(p["model"] == "audit_logs" for p in preview["protected"])
    assert not any(u["model"] == "audit_logs" for u in preview["unlinks"])
    blocked = await client.request("DELETE", f"{DATA}/users/{other.user['id']}", admin)
    assert blocked.status_code == 409
    # Deactivating is the supported alternative.
    updated = await client.patch(f"{DATA}/users/{other.user['id']}", admin, json={"is_active": False})
    assert updated["values"]["is_active"] is False


APPEND_ONLY_TABLES = (
    "ledger_entries",
    "ledger_transactions",
    "audit_logs",
    "merchant_verifications",
    "delivery_events",
)


async def test_every_table_supports_add_change_and_delete(client: Client) -> None:
    admin = await create_admin(client)
    models = await client.get(f"{DATA}/models", admin)
    for model in models:
        assert model["can_add"] and model["can_change"] and model["can_delete"], model["key"]
        assert model["user_can_manage"] and model["user_can_override"]
        assert model["immutable"] is (model["key"] in APPEND_ONLY_TABLES)


async def test_link_tables_can_change_their_key(client: Client) -> None:
    admin = await create_admin(client)
    user = await register_customer(client)
    roles = {r["label"]: r["pk"] for r in (await client.get(f"{DATA}/roles", admin))["items"]}
    link = await client.post(
        f"{DATA}/user_roles", admin, json={"user_id": user.user["id"], "role_id": roles["MERCHANT"]}, expect=201
    )
    moved = await client.patch(f"{DATA}/user_roles/{link['pk']}", admin, json={"role_id": roles["ADMIN"]})
    assert moved["pk"] == f"{user.user['id']},{roles['ADMIN']}"
    await client.get(f"{DATA}/user_roles/{link['pk']}", admin, expect=404)
    await client.delete(f"{DATA}/user_roles/{moved['pk']}", admin)


async def test_system_generated_tables_can_be_added(client: Client) -> None:
    admin = await create_admin(client)
    user = await register_customer(client)
    session = await client.post(f"{DATA}/user_sessions", admin, json={"user_id": user.user["id"]}, expect=201)
    token = await client.post(
        f"{DATA}/refresh_tokens",
        admin,
        json={"session_id": session["pk"], "expires_at": "2030-01-01T00:00:00Z"},
        expect=201,
    )
    assert "token_hash" not in token["values"]  # generated, never disclosed
    action = await client.post(
        f"{DATA}/user_action_tokens",
        admin,
        json={"user_id": user.user["id"], "purpose": "PASSWORD_RESET", "expires_at": "2030-01-01T00:00:00Z"},
        expect=201,
    )
    await client.patch(f"{DATA}/user_action_tokens/{action['pk']}", admin, json={"used_at": "2026-11-09T10:00:00Z"})
    await client.delete(f"{DATA}/user_sessions/{session['pk']}", admin)  # cascades to its refresh tokens
    await client.get(f"{DATA}/refresh_tokens/{token['pk']}", admin, expect=404)


async def _ledger_accounts(client: Client, admin: Any) -> tuple[str, str]:
    accounts = await client.get(f"{DATA}/ledger_accounts", admin, params={"merchant_id__isnull": "true"})
    by_type = {a["values"]["account_type"]: a["pk"] for a in accounts["items"]}
    if "PROCESSING_FEES" not in by_type or "PROVIDER_CLEARING" not in by_type:
        for kind in ("PROCESSING_FEES", "PROVIDER_CLEARING"):
            if kind not in by_type:
                row = await client.post(f"{DATA}/ledger_accounts", admin, json={"account_type": kind}, expect=201)
                by_type[kind] = row["pk"]
    return by_type["PROCESSING_FEES"], by_type["PROVIDER_CLEARING"]


async def test_ledger_postings_are_added_with_inline_entries_and_must_balance(client: Client) -> None:
    admin = await create_admin(client)
    fees, clearing = await _ledger_accounts(client, admin)
    ref = f"manual-{uuid.uuid4().hex[:8]}"
    header = {
        "reference": ref,
        "transaction_type": "REVERSAL",
        "source_type": "admin",
        "source_id": str(uuid.uuid4()),
        "is_test": True,
    }

    def entries(debit: int, credit: int) -> list[dict[str, Any]]:
        return [
            {"account_id": fees, "direction": "DEBIT", "amount": debit, "description": "manual"},
            {"account_id": clearing, "direction": "CREDIT", "amount": credit, "description": "manual"},
        ]

    unbalanced = await client.request(
        "POST", f"{DATA}/ledger_transactions", admin, json={**header, "_inlines": {"ledger_entries": entries(500, 400)}}
    )
    assert unbalanced.status_code == 422
    assert unbalanced.json()["error"]["code"] == "ledger_unbalanced"

    bad_row = await client.request(
        "POST",
        f"{DATA}/ledger_transactions",
        admin,
        json={**header, "_inlines": {"ledger_entries": [{"account_id": fees, "direction": "UP", "amount": 1}]}},
    )
    assert bad_row.status_code == 422
    assert bad_row.json()["error"]["details"][0]["loc"] == ["body", "_inlines", "ledger_entries", 0, "direction"]

    created = await client.post(
        f"{DATA}/ledger_transactions",
        admin,
        json={**header, "_inlines": {"ledger_entries": entries(500, 500)}},
        expect=201,
    )
    tx = created["pk"]
    rows = (await client.get(f"{DATA}/ledger_entries", admin, params={"transaction_id": tx}))["items"]
    assert len(rows) == 2

    # A lone entry can never balance, so entries are added through their transaction.
    lone = await client.request(
        "POST", f"{DATA}/ledger_entries", admin, json={"transaction_id": tx, **entries(1, 1)[0]}
    )
    assert lone.status_code == 422
    assert lone.json()["error"]["code"] == "ledger_unbalanced"

    # Changing one side alone unbalances the posting (even with an override)...
    reason = {"x-override-reason": "Correct a mistyped manual posting"}
    debit = next(r for r in rows if r["values"]["direction"] == "DEBIT")
    credit = next(r for r in rows if r["values"]["direction"] == "CREDIT")
    one_side = await client.request(
        "PATCH", f"{DATA}/ledger_entries/{debit['pk']}", admin, json={"amount": 600}, headers=reason
    )
    assert one_side.json()["error"]["code"] == "ledger_unbalanced"
    # ...both sides together through the inline keep it balanced.
    both = {"_inlines": {"ledger_entries": [{"_pk": debit["pk"], "amount": 600}, {"_pk": credit["pk"], "amount": 600}]}}
    no_reason = await client.request("PATCH", f"{DATA}/ledger_transactions/{tx}", admin, json=both)
    assert no_reason.json()["error"]["code"] == "override_reason_required"
    await client.patch(f"{DATA}/ledger_transactions/{tx}", admin, json=both, headers=reason)
    amounts = {
        r["values"]["amount"]
        for r in (await client.get(f"{DATA}/ledger_entries", admin, params={"transaction_id": tx}))["items"]
    }
    assert amounts == {600}

    # Deleting: the entries first (both at once keeps the balance), then the transaction.
    await client.post(
        f"{DATA}/ledger_entries/bulk-delete", admin, json={"pks": [debit["pk"], credit["pk"]]}, headers=reason
    )
    await client.delete(f"{DATA}/ledger_transactions/{tx}", admin, headers=reason)
    logs = await client.get(
        f"{API}/admin/audit-logs", admin, params={"entity_type": "ledger_transactions", "entity_id": tx}
    )
    delete_log = next(e for e in logs["items"] if e["action"] == "data.override.delete")
    assert delete_log["after"] == {"_override_reason": reason["x-override-reason"]}


async def test_append_only_overrides_need_permission_and_reason(client: Client) -> None:
    admin = await create_admin(client)
    merchant = await active_merchant(client, admin)
    product = await create_product(client, merchant)
    customer = await register_customer(client)
    _, mo = await paid_order(client, customer, product)
    reason = {"x-override-reason": "Remove a duplicated timeline entry"}

    # Add works on every append-only table, without an override.
    verification = await client.post(
        f"{DATA}/merchant_verifications",
        admin,
        json={"merchant_id": merchant.extra["merchant_id"], "to_status": "APPROVED", "note": "manual"},
        expect=201,
    )
    audit = await client.post(
        f"{DATA}/audit_logs", admin, json={"action": "manual.note", "entity_type": "orders"}, expect=201
    )
    deliveries = await client.get(f"{DATA}/deliveries", admin, params={"merchant_order_id": mo["id"]})
    event = await client.post(
        f"{DATA}/delivery_events",
        admin,
        json={"delivery_id": deliveries["items"][0]["pk"], "to_status": "CONFIRMED", "source": "PLATFORM"},
        expect=201,
    )

    # Without the override permission: 403. Without a reason: 422.
    regular = await create_admin(client, super_admin=False)
    for model, row in (("merchant_verifications", verification), ("audit_logs", audit), ("delivery_events", event)):
        assert (await client.request("PATCH", f"{DATA}/{model}/{row['pk']}", regular, json={})).status_code == 403
        missing = await client.request(
            "PATCH",
            f"{DATA}/{model}/{row['pk']}",
            admin,
            json={"note": "x"} if model != "audit_logs" else {"action": "x"},
        )
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "override_reason_required"

    changed = await client.patch(
        f"{DATA}/merchant_verifications/{verification['pk']}", admin, json={"note": "corrected"}, headers=reason
    )
    assert changed["values"]["note"] == "corrected"
    await client.delete(f"{DATA}/delivery_events/{event['pk']}", admin, headers=reason)
    await client.delete(f"{DATA}/audit_logs/{audit['pk']}", admin, headers=reason)
    await client.get(f"{DATA}/audit_logs/{audit['pk']}", admin, expect=404)

    # The override is audited with its reason...
    logs = await client.get(
        f"{API}/admin/audit-logs",
        admin,
        params={"entity_type": "merchant_verifications", "entity_id": verification["pk"]},
    )
    entry = next(e for e in logs["items"] if e["action"] == "data.override.update")
    assert entry["after"] == {"note": "corrected", "_override_reason": reason["x-override-reason"]}

    # ...and the immutability trigger is back in force afterwards.
    from sqlalchemy import text

    from app.database.session import get_sessionmaker

    async with get_sessionmaker()() as session:
        enabled = (
            await session.execute(
                text("SELECT tgname, tgenabled FROM pg_trigger WHERE tgname LIKE '%\\_immutable' ORDER BY tgname")
            )
        ).all()
        assert len(enabled) == 5 and all(state in ("O", b"O") for _, state in enabled)
        try:
            await session.execute(
                text("UPDATE merchant_verifications SET note = 'direct' WHERE id = :id"), {"id": verification["pk"]}
            )
            raise AssertionError("trigger did not fire")
        except Exception as exc:
            assert "immutable" in str(exc)
        await session.rollback()
