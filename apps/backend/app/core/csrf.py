"""CSRF protection (double-submit cookie) for cookie-authenticated requests.

State-changing requests that authenticate with cookies must send the
``X-CSRF-Token`` header matching the ``csrf_token`` cookie. Requests authenticated
with an ``Authorization: Bearer`` header are not vulnerable to CSRF and are exempt.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.core.security import constant_time_equals

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
EXEMPT_PREFIXES = (
    "/api/v1/webhooks/",
    "/api/v1/mock-provider/",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/merchants/register",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/password-reset/",
)
AUTH_COOKIES = ("access_token", "refresh_token")


def install_csrf(app: FastAPI) -> None:
    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if (
            request.method not in SAFE_METHODS
            and not request.url.path.startswith(EXEMPT_PREFIXES)
            and not request.headers.get("authorization", "").lower().startswith("bearer ")
            and any(name in request.cookies for name in AUTH_COOKIES)
        ):
            cookie = request.cookies.get("csrf_token", "")
            header = request.headers.get("x-csrf-token", "")
            if not cookie or not header or not constant_time_equals(cookie, header):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {"code": "csrf_failed", "message": "CSRF token missing or invalid.", "details": None}
                    },
                )
        return await call_next(request)
