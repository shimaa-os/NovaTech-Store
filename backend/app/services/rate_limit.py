from fastapi import HTTPException, Request, status
from redis.asyncio import Redis


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


async def enforce_rate_limit(
    redis: Redis,
    request: Request,
    bucket: str,
    identifier: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    key = f"rate:{bucket}:{client_ip(request)}:{identifier.lower()}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()
    if ttl < 0:
        await redis.expire(key, window_seconds)
        ttl = window_seconds
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(max(1, ttl))},
        )

