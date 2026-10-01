from fastapi import Request

from app.common.redis import redis_client
from app.core.exceptions import AppError


async def enforce_rate_limit(
    request: Request, namespace: str, limit: int, seconds: int = 60
) -> None:
    identity = request.client.host if request.client else "unknown"
    key = f"orderflow:ratelimit:{namespace}:{identity}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, seconds)
        if count > limit:
            raise AppError("rate_limited", "Too many requests", 429)
    except AppError:
        raise
    except Exception:
        # Dependency degradation should not make the API unavailable; readiness still exposes it.
        return
