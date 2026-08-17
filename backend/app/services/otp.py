import json
import secrets
import time

from redis import Redis as SyncRedis
from redis.asyncio import Redis
from rq import Queue

from ..config import get_settings
from ..security import keyed_digest
from .email_jobs import send_otp_email


def _key(email: str) -> str:
    return f"registration:{email.lower()}"


def _enqueue_email(email: str, otp: str) -> None:
    settings = get_settings()
    if settings.environment == "test":
        return
    queue = Queue("email", connection=SyncRedis.from_url(settings.redis_url))
    safe_settings = settings.model_dump(
        include={
            "environment", "email_from", "smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_starttls"
        },
        mode="json",
    )
    queue.enqueue(send_otp_email, safe_settings, email, otp, job_timeout=30, result_ttl=0)


async def create_pending_registration(
    redis: Redis, *, email: str, username: str, password_hash: str
) -> str:
    settings = get_settings()
    otp = f"{secrets.randbelow(900_000) + 100_000:06d}"
    payload = {
        "email": email.lower(),
        "username": username.lower(),
        "password_hash": password_hash,
        "otp_digest": keyed_digest(settings.otp_secret, f"{email.lower()}:{otp}"),
        "attempts": 0,
        "created_at": int(time.time()),
        "last_sent_at": int(time.time()),
    }
    await redis.set(_key(email), json.dumps(payload), ex=settings.otp_ttl_seconds)
    _enqueue_email(email, otp)
    return otp


async def resend_pending_registration(redis: Redis, email: str) -> str | None:
    settings = get_settings()
    value = await redis.get(_key(email))
    if not value:
        return None
    payload = json.loads(value)
    if int(time.time()) - int(payload.get("last_sent_at", 0)) < settings.otp_resend_cooldown_seconds:
        return "cooldown"
    otp = f"{secrets.randbelow(900_000) + 100_000:06d}"
    payload["otp_digest"] = keyed_digest(settings.otp_secret, f"{email.lower()}:{otp}")
    payload["attempts"] = 0
    payload["last_sent_at"] = int(time.time())
    ttl = await redis.ttl(_key(email))
    await redis.set(_key(email), json.dumps(payload), ex=max(1, ttl))
    _enqueue_email(email, otp)
    return otp


async def verify_pending_registration(redis: Redis, email: str, otp: str) -> dict | None:
    settings = get_settings()
    key = _key(email)
    value = await redis.get(key)
    if not value:
        return None
    payload = json.loads(value)
    payload["attempts"] = int(payload.get("attempts", 0)) + 1
    if payload["attempts"] > settings.otp_max_attempts:
        await redis.delete(key)
        return None
    expected = keyed_digest(settings.otp_secret, f"{email.lower()}:{otp}")
    if not secrets.compare_digest(payload.get("otp_digest", ""), expected):
        ttl = await redis.ttl(key)
        await redis.set(key, json.dumps(payload), ex=max(1, ttl))
        return None
    await redis.delete(key)
    return payload

