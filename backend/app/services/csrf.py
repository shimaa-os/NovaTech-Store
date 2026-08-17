from __future__ import annotations

import hmac
import time
from hashlib import sha256

from fastapi import HTTPException, Request, Response, status

from ..config import get_settings
from ..security import random_token

TOKEN_TTL_SECONDS = 2 * 60 * 60


def _sign(nonce: str, expires: int) -> str:
    settings = get_settings()
    payload = f"{nonce}.{expires}".encode()
    return hmac.new(settings.csrf_secret.encode(), payload, sha256).hexdigest()


def create_csrf_token(response: Response) -> str:
    settings = get_settings()
    expires = int(time.time()) + TOKEN_TTL_SECONDS
    nonce = random_token(24)
    token = f"{nonce}.{expires}.{_sign(nonce, expires)}"
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        max_age=TOKEN_TTL_SECONDS,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return token


def verify_csrf_token(token: str | None) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    nonce, expires_text, signature = parts
    try:
        expires = int(expires_text)
    except ValueError:
        return False
    if expires < int(time.time()):
        return False
    expected = _sign(nonce, expires)
    return hmac.compare_digest(expected, signature)


async def enforce_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not request.url.path.startswith("/api/"):
        return
    settings = get_settings()
    origin = request.headers.get("origin")
    if origin != settings.app_origin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid request origin")
    header_token = request.headers.get("x-csrf-token")
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not header_token or not cookie_token or not hmac.compare_digest(header_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if not verify_csrf_token(header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
