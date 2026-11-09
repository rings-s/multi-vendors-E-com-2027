"""Authentication, sessions, CSRF and role-based authorization."""

import re
import uuid

import pytest

from tests.helpers import API, PASSWORD, Actor, Client, create_admin, register_customer, register_merchant


async def test_register_login_and_me(client: Client) -> None:
    customer = await register_customer(client)
    assert customer.user["roles"] == ["CUSTOMER"]
    assert customer.user["email_verified"] is False
    data = await client.post(f"{API}/auth/login", json={"email": customer.extra["email"], "password": PASSWORD})
    me = await client.get(f"{API}/auth/me", Actor(token=data["access_token"], user={}))
    assert me["id"] == customer.user["id"]


async def test_duplicate_email_rejected(client: Client) -> None:
    customer = await register_customer(client)
    response = await client.request(
        "POST",
        f"{API}/auth/register",
        json={"email": customer.extra["email"].upper(), "password": PASSWORD, "full_name": "Someone"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_wrong_password_and_weak_password(client: Client) -> None:
    customer = await register_customer(client)
    response = await client.request(
        "POST", f"{API}/auth/login", json={"email": customer.extra["email"], "password": "wrong-password-123"}
    )
    assert response.status_code == 401
    response = await client.request(
        "POST", f"{API}/auth/register", json={"email": "x@example.com", "password": "short", "full_name": "X Y"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


async def test_requires_authentication(client: Client) -> None:
    response = await client.request("GET", f"{API}/auth/me")
    assert response.status_code == 401
    response = await client.request("GET", f"{API}/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


async def _native_login(client: Client, email: str) -> dict[str, str]:
    return await client.post(
        f"{API}/auth/login", json={"email": email, "password": PASSWORD}, headers={"X-Client-Type": "native"}
    )


async def test_refresh_token_rotation_and_reuse_detection(client: Client) -> None:
    customer = await register_customer(client)
    first = await _native_login(client, customer.extra["email"])
    assert first["refresh_token"]
    rotated = await client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated["access_token"]
    # Reusing the old refresh token revokes the whole session.
    response = await client.request("POST", f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "refresh_token_reuse"
    response = await client.request("GET", f"{API}/auth/me", Actor(token=rotated["access_token"], user={}))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_revoked"


async def test_logout_invalidates_session(client: Client) -> None:
    customer = await register_customer(client)
    await client.post(f"{API}/auth/logout", customer)
    response = await client.request("GET", f"{API}/auth/me", customer)
    assert response.status_code == 401


async def test_logout_all_ends_every_session(client: Client) -> None:
    customer = await register_customer(client)
    other = await _native_login(client, customer.extra["email"])
    sessions = await client.get(f"{API}/auth/sessions", customer)
    assert len(sessions) == 2
    await client.post(f"{API}/auth/logout-all", customer)
    response = await client.request("GET", f"{API}/auth/me", Actor(token=other["access_token"], user={}))
    assert response.status_code == 401


async def test_cookie_requests_require_csrf_token(client: Client) -> None:
    customer = await register_customer(client)
    http = client.http
    http.cookies.clear()
    login = await http.post(f"{API}/auth/login", json={"email": customer.extra["email"], "password": PASSWORD})
    assert login.status_code == 200
    assert "access_token" in http.cookies and "csrf_token" in http.cookies
    # Safe request with the cookie works.
    assert (await http.get(f"{API}/auth/me")).status_code == 200
    # State-changing request without the header is rejected.
    rejected = await http.patch(f"{API}/users/me", json={"full_name": "Changed Name"})
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "csrf_failed"
    accepted = await http.patch(
        f"{API}/users/me", json={"full_name": "Changed Name"}, headers={"X-CSRF-Token": http.cookies["csrf_token"]}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["full_name"] == "Changed Name"
    http.cookies.clear()


async def test_password_reset_flow(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    async def fake_send(to: str, subject: str, body: str) -> bool:
        sent.append(body)
        return True

    monkeypatch.setattr("app.modules.auth.service.send_email", fake_send)
    customer = await register_customer(client)
    sent.clear()  # registration sends a verification email
    await client.post(f"{API}/auth/password-reset/request", json={"email": customer.extra["email"]})
    # Unknown emails get the same response and no email.
    await client.post(f"{API}/auth/password-reset/request", json={"email": f"nobody-{uuid.uuid4().hex}@example.com"})
    assert len(sent) == 1
    token = re.search(r"token=([\w\-]+)", sent[0])
    assert token
    new_password = "a-brand-new-password-42"
    await client.post(
        f"{API}/auth/password-reset/confirm", json={"token": token.group(1), "new_password": new_password}
    )
    # Existing sessions are ended and the old password no longer works.
    assert (await client.request("GET", f"{API}/auth/me", customer)).status_code == 401
    old = await client.request(
        "POST", f"{API}/auth/login", json={"email": customer.extra["email"], "password": PASSWORD}
    )
    assert old.status_code == 401
    await client.post(f"{API}/auth/login", json={"email": customer.extra["email"], "password": new_password})
    # The token is single-use.
    reused = await client.request(
        "POST", f"{API}/auth/password-reset/confirm", json={"token": token.group(1), "new_password": new_password}
    )
    assert reused.status_code in (400, 401, 422)


async def test_email_verification(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    async def fake_send(to: str, subject: str, body: str) -> bool:
        sent.append(body)
        return True

    monkeypatch.setattr("app.modules.auth.service.send_email", fake_send)
    customer = await register_customer(client)
    await client.post(f"{API}/auth/verify-email/resend", customer)
    token = re.search(r"token=([\w\-]+)", sent[-1])
    assert token
    await client.post(f"{API}/auth/verify-email", json={"token": token.group(1)})
    me = await client.get(f"{API}/auth/me", customer)
    assert me["email_verified"] is True


async def test_role_based_access_control(client: Client) -> None:
    customer = await register_customer(client)
    merchant = await register_merchant(client)
    admin = await create_admin(client, super_admin=False)

    # Customers cannot use merchant or admin APIs.
    assert (await client.request("GET", f"{API}/merchant/dashboard", customer)).status_code == 403
    assert (await client.request("GET", f"{API}/admin/overview", customer)).status_code == 403
    # Merchants cannot use admin APIs or the customer cart.
    assert (await client.request("GET", f"{API}/admin/merchants", merchant)).status_code == 403
    assert (await client.request("GET", f"{API}/cart", merchant)).status_code == 403
    # Admins can view, but financial configuration is reserved for SUPER_ADMIN.
    assert (await client.request("GET", f"{API}/admin/overview", admin)).status_code == 200
    response = await client.request(
        "POST", f"{API}/admin/commissions", admin, json={"scope": "GLOBAL", "rate_type": "PERCENTAGE", "rate": "5"}
    )
    assert response.status_code == 403
    response = await client.request("PUT", f"{API}/admin/users/{customer.user['id']}/roles", admin, json={})
    assert response.status_code in (403, 422)


async def test_disabled_account_cannot_authenticate(client: Client) -> None:
    customer = await register_customer(client)
    admin = await create_admin(client)
    await client.post(
        f"{API}/admin/users/{customer.user['id']}/active",
        admin,
        json={"is_active": False, "reason": "Fraud investigation"},
    )
    assert (await client.request("GET", f"{API}/auth/me", customer)).status_code == 401
    response = await client.request(
        "POST", f"{API}/auth/login", json={"email": customer.extra["email"], "password": PASSWORD}
    )
    assert response.status_code in (401, 403)


async def test_cli_creates_super_admin(client: Client) -> None:
    from app.cli import create_admin as cli_create_admin

    email = f"ops-{uuid.uuid4().hex[:8]}@example.com"
    await cli_create_admin(email, "Ops Lead", PASSWORD, super_admin=True)
    data = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert data["user"]["roles"] == ["SUPER_ADMIN"]
    assert data["user"]["email_verified"] is True
    admin = Actor(token=data["access_token"], user=data["user"])
    assert (await client.request("GET", f"{API}/admin/settings", admin)).status_code == 200
