from __future__ import annotations

import time
import logging
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Límites por defecto (requests / ventana de tiempo en segundos)
RATE_LIMITS = {
    # (max_requests, window_seconds, descripción)
    "invoke":      (60,  60,   "60 invocaciones por minuto"),
    "build":       (10,  60,   "10 builds por minuto"),
    "spec":        (20,  60,   "20 specs por minuto"),
    "eval":        (5,   60,   "5 evaluaciones por minuto"),
    "login":       (10,  60,   "10 intentos de login por minuto"),
    "register":    (5,   60,   "5 registros por minuto"),
    "global":      (300, 60,   "300 requests por minuto globales"),
}


class RateLimiter:
    """
    Sliding window rate limiter usando Redis sorted sets.
    Si Redis no está disponible, falla abierto (permite el request).

    Clave Redis: ratelimit:{scope}:{identifier}
    Valor: sorted set de timestamps de requests
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def check(
        self,
        identifier: str,
        scope: str = "global",
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> dict:
        """
        Verifica si el identifier superó el límite para el scope.
        Retorna { allowed: bool, remaining: int, reset_in: int }.
        Lanza HTTPException 429 si se supera el límite.
        """
        if not self._redis:
            return {"allowed": True, "remaining": 999, "reset_in": 60}

        limit_config = RATE_LIMITS.get(scope, RATE_LIMITS["global"])
        max_req = max_requests or limit_config[0]
        window  = window_seconds or limit_config[1]

        key = f"ratelimit:{scope}:{identifier}"
        now = time.time()
        window_start = now - window

        try:
            pipe = self._redis.pipeline()
            # Eliminar timestamps fuera de la ventana
            await pipe.zremrangebyscore(key, 0, window_start)
            # Contar requests en la ventana
            await pipe.zcard(key)
            # Agregar el request actual
            await pipe.zadd(key, {str(now): now})
            # Expirar la clave después de la ventana
            await pipe.expire(key, window + 1)
            results = await pipe.execute()

            count = results[1]   # zcard antes de agregar el actual
            remaining = max(0, max_req - count - 1)

            if count >= max_req:
                # Calcular cuándo se libera el slot más antiguo
                oldest = await self._redis.zrange(key, 0, 0, withscores=True)
                reset_in = int(window - (now - oldest[0][1])) if oldest else window

                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit superado: {limit_config[2]}. Reintentá en {reset_in}s.",
                    headers={
                        "X-RateLimit-Limit":     str(max_req),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset":     str(int(now) + reset_in),
                        "Retry-After":           str(reset_in),
                    },
                )

            return {
                "allowed":   True,
                "remaining": remaining,
                "reset_in":  window,
            }

        except HTTPException:
            raise
        except Exception as e:
            # Fail open — si Redis falla, no bloqueamos el request
            logger.warning(f"[RateLimit] Redis error: {e} — failing open")
            return {"allowed": True, "remaining": 999, "reset_in": 60}

    async def get_status(self, identifier: str, scope: str = "global") -> dict:
        """Retorna el estado actual del rate limit sin consumir un slot."""
        if not self._redis:
            return {"count": 0, "limit": RATE_LIMITS.get(scope, RATE_LIMITS["global"])[0]}

        limit_config = RATE_LIMITS.get(scope, RATE_LIMITS["global"])
        max_req = limit_config[0]
        window  = limit_config[1]
        key     = f"ratelimit:{scope}:{identifier}"
        now     = time.time()

        try:
            await self._redis.zremrangebyscore(key, 0, now - window)
            count = await self._redis.zcard(key)
            return {
                "count":     count,
                "limit":     max_req,
                "remaining": max(0, max_req - count),
                "window_s":  window,
            }
        except Exception:
            return {"count": 0, "limit": max_req}


# Singleton global — inicializado en main.py junto con Redis
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter is None:
        return RateLimiter(redis_client=None)   # Fail open si no inicializado
    return _rate_limiter


def init_rate_limiter(redis_client=None) -> RateLimiter:
    global _rate_limiter
    _rate_limiter = RateLimiter(redis_client=redis_client)
    return _rate_limiter
