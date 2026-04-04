from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# ── Interfaz base ─────────────────────────────────────────────────────────────

class MemoryAdapter(ABC):
    """
    Abstracción de memoria para AgentRuntime.
    Cada session_id tiene su propio historial independiente.
    """

    @abstractmethod
    async def load(self, session_id: str) -> list[dict]:
        """Retorna el historial [{role, content}] de la sesión."""
        ...

    @abstractmethod
    async def save(self, session_id: str, user_input: str, assistant_output: str) -> None:
        """Persiste un turno completo (user + assistant)."""
        ...

    @abstractmethod
    def clear(self, session_id: str) -> None:
        """Borra el historial de la sesión."""
        ...


# ── In-memory (solo para testing / sandbox) ──────────────────────────────────

class InMemoryAdapter(MemoryAdapter):
    def __init__(self, max_messages: int = 50):
        self._store: dict[str, list[dict]] = {}
        self._max = max_messages

    async def load(self, session_id: str) -> list[dict]:
        return self._store.get(session_id, [])

    async def save(self, session_id: str, user_input: str, assistant_output: str) -> None:
        history = self._store.setdefault(session_id, [])
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": assistant_output})
        # Mantener ventana de contexto
        if len(history) > self._max * 2:
            self._store[session_id] = history[-(self._max * 2):]

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)


# ── Redis (short-term, TTL configurable) ─────────────────────────────────────

class RedisAdapter(MemoryAdapter):
    """
    Guarda el historial serializado como JSON en Redis.
    Ideal para sesiones activas de chat — se borra automáticamente por TTL.
    """

    def __init__(self, redis_client: Any, ttl_seconds: int = 3600, max_messages: int = 50):
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._max = max_messages

    def _key(self, session_id: str) -> str:
        return f"memory:{session_id}"

    async def load(self, session_id: str) -> list[dict]:
        import json
        raw = await self._redis.get(self._key(session_id))
        if not raw:
            return []
        return json.loads(raw)

    async def save(self, session_id: str, user_input: str, assistant_output: str) -> None:
        import json
        history = await self.load(session_id)
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": assistant_output})
        if len(history) > self._max * 2:
            history = history[-(self._max * 2):]
        await self._redis.setex(
            self._key(session_id),
            self._ttl,
            json.dumps(history, ensure_ascii=False),
        )

    def clear(self, session_id: str) -> None:
        # Fire-and-forget — no async en el método base para compatibilidad
        import asyncio
        asyncio.create_task(self._redis.delete(self._key(session_id)))


# ── PostgreSQL (long-term, persiste entre sesiones) ───────────────────────────

class PostgreSQLAdapter(MemoryAdapter):
    """
    Persiste el historial en la tabla memory_store del schema del tenant.
    Adecuado para agentes con memoria larga (soporte, ventas, asistentes personales).
    """

    def __init__(self, session_factory: Any, agent_id: str, max_messages: int = 100):
        self._session_factory = session_factory
        self._agent_id = agent_id
        self._max = max_messages

    async def load(self, session_id: str) -> list[dict]:
        from sqlalchemy import text
        async with self._session_factory() as db:
            result = await db.execute(
                text("""
                    SELECT key, value FROM memory_store
                    WHERE agent_id = :agent_id AND session_id = :session_id
                    AND key = 'history'
                """),
                {"agent_id": self._agent_id, "session_id": session_id},
            )
            row = result.fetchone()
            if not row:
                return []
            return row.value.get("messages", [])

    async def save(self, session_id: str, user_input: str, assistant_output: str) -> None:
        from sqlalchemy import text
        import json

        history = await self.load(session_id)
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": assistant_output})
        if len(history) > self._max * 2:
            history = history[-(self._max * 2):]

        async with self._session_factory() as db:
            await db.execute(
                text("""
                    INSERT INTO memory_store (agent_id, session_id, key, value)
                    VALUES (:agent_id, :session_id, 'history', :value::jsonb)
                    ON CONFLICT (agent_id, session_id, key)
                    DO UPDATE SET value = EXCLUDED.value
                """),
                {
                    "agent_id": self._agent_id,
                    "session_id": session_id,
                    "value": json.dumps({"messages": history}, ensure_ascii=False),
                },
            )
            await db.commit()

    def clear(self, session_id: str) -> None:
        import asyncio
        async def _clear():
            from sqlalchemy import text
            async with self._session_factory() as db:
                await db.execute(
                    text("DELETE FROM memory_store WHERE agent_id=:a AND session_id=:s"),
                    {"a": self._agent_id, "s": session_id},
                )
                await db.commit()
        asyncio.create_task(_clear())
