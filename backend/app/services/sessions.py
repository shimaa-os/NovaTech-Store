import hashlib
import json
import time
import uuid
from dataclasses import dataclass

from fastapi import Request, Response
from redis.asyncio import Redis

from ..config import get_settings
from ..security import random_token


@dataclass(frozen=True)
class SessionIdentity:
    user_id: uuid.UUID
    role: str
    issued_at: int


def _session_key(raw_token: str) -> str:
    return f"session:{hashlib.sha256(raw_token.encode()).hexdigest()}"


async def create_session(redis: Redis, response: Response, user_id: uuid.UUID, role: str) -> None:
    settings = get_settings()
    raw_token = random_token()
    key = _session_key(raw_token)
    issued_at = int(time.time())
    payload = json.dumps({"user_id": str(user_id), "role": role, "issued_at": issued_at})
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(key, payload, ex=settings.session_idle_seconds)
        pipe.sadd(f"user-sessions:{user_id}", key)
        pipe.expire(f"user-sessions:{user_id}", settings.session_absolute_seconds)
        await pipe.execute()
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=settings.session_absolute_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


async def read_session(redis: Redis, request: Request) -> SessionIdentity | None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        return None
    key = _session_key(raw_token)
    value = await redis.get(key)
    if not value:
        return None
    try:
        payload = json.loads(value)
        issued_at = int(payload["issued_at"])
        identity = SessionIdentity(uuid.UUID(payload["user_id"]), str(payload["role"]), issued_at)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        await redis.delete(key)
        return None
    if int(time.time()) - issued_at > settings.session_absolute_seconds:
        await redis.delete(key)
        return None
    await redis.expire(key, settings.session_idle_seconds)
    return identity


async def delete_current_session(redis: Redis, request: Request, response: Response) -> None:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token:
        await redis.delete(_session_key(raw_token))
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.cookie_secure, samesite="lax")


async def revoke_user_sessions(redis: Redis, user_id: uuid.UUID) -> None:
    index_key = f"user-sessions:{user_id}"
    keys = await redis.execute_command("SMEMBERS", index_key)
    if keys:
        await redis.delete(*keys)
    await redis.delete(index_key)
