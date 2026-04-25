from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# TTL de los designs cacheados en Redis: 24 horas
DESIGN_TTL = 60 * 60 * 24


class RuntimeStore:
    """
    Reemplaza el dict _active_runtimes en memoria de agents.py.

    Estrategia de dos niveles:
      - Level 1 (in-memory): runtime ya construido (AgentRuntime object)
                             — no serializable, vive en el proceso actual
      - Level 2 (Redis):     AgentDesign serializado como JSON
                             — persiste entre reinicios del servidor

    Al buscar un runtime:
      1. Si está en memoria → retornarlo directo (fast path)
      2. Si el design está en Redis pero el runtime no → reconstruir runtime
      3. Si no está en ninguno → 404
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        # RuntimeStore._memory — un entry por agent_id activo.
        # En producción con >50 agentes concurrentes, considerar evicción LRU (Sprint 7).
        self._memory: dict[str, tuple] = {}   # { agent_id: (runtime, design) }

    # ── Escritura ─────────────────────────────────────────────────────────────

    async def save_design(self, agent_id: str, design) -> None:
        """Persiste el design en Redis y lo cachea en memoria (sin runtime aún)."""
        existing_runtime = None
        if agent_id in self._memory:
            existing_runtime, _ = self._memory[agent_id]

        self._memory[agent_id] = (existing_runtime, design)

        if self._redis:
            try:
                await self._redis.setex(
                    f"design:{agent_id}",
                    DESIGN_TTL,
                    design.model_dump_json(),
                )
            except Exception as e:
                logger.warning(f"[RuntimeStore] No se pudo persistir design en Redis: {e}")

    async def save_runtime(self, agent_id: str, runtime, design) -> None:
        """Guarda el runtime construido en memoria y actualiza el design en Redis."""
        self._memory[agent_id] = (runtime, design)
        await self.save_design(agent_id, design)

    # ── Lectura ───────────────────────────────────────────────────────────────

    async def get(self, agent_id: str) -> Optional[tuple]:
        """
        Retorna (runtime, design) o None.
        Si el runtime no está en memoria pero el design está en Redis,
        reconstruye el runtime automáticamente.
        """
        # Fast path: en memoria con runtime
        if agent_id in self._memory:
            runtime, design = self._memory[agent_id]
            if runtime is not None:
                return runtime, design
            # Design en memoria pero sin runtime — retornar None para runtime
            return None, design

        # Fallback: buscar design en Redis
        if self._redis:
            raw = None
            try:
                raw = await self._redis.get(f"design:{agent_id}")
            except Exception as e:
                logger.error(f"[RuntimeStore] Error al leer Redis: {e}")

            if raw:
                try:
                    from app.schemas.agent import AgentDesign
                    design = AgentDesign.model_validate_json(raw)
                except Exception as e:
                    logger.error(f"[RuntimeStore] Error al deserializar design: {e}")
                    return None

                # Intentar reconstruir runtime — si falla, igual retornamos el design
                try:
                    runtime = await self._rebuild_runtime(design)
                    self._memory[agent_id] = (runtime, design)
                    return runtime, design
                except Exception as e:
                    logger.error(f"[RuntimeStore] Error al reconstruir runtime: {e}")
                    self._memory[agent_id] = (None, design)
                    return None, design

        return None

    async def _rebuild_runtime(self, design):
        """Reconstruye el AgentRuntime desde un design deserializado."""
        from app.runtime.factory import RuntimeFactory
        logger.info(f"[RuntimeStore] Reconstruyendo runtime para agent_id={design.agent_id}")
        factory = RuntimeFactory(redis_client=self._redis)
        return await factory.build(design)

    # ── Eliminación ───────────────────────────────────────────────────────────

    async def delete(self, agent_id: str) -> None:
        self._memory.pop(agent_id, None)
        if self._redis:
            await self._redis.delete(f"design:{agent_id}")

    # ── Listado ───────────────────────────────────────────────────────────────

    def list_loaded(self) -> list[str]:
        """Retorna los agent_ids cargados en memoria en este proceso."""
        return list(self._memory.keys())

    @property
    def redis_client(self):
        return self._redis

    async def list_all(self) -> list[str]:
        """Retorna todos los agent_ids persistidos en Redis."""
        if not self._redis:
            return self.list_loaded()
        try:
            keys = await self._redis.keys("design:*")
            return [k.removeprefix("design:") for k in keys]
        except Exception:
            return self.list_loaded()


# Singleton global — inicializado en el lifespan de FastAPI
_store: Optional[RuntimeStore] = None


def get_runtime_store() -> RuntimeStore:
    if _store is None:
        raise RuntimeError("RuntimeStore no inicializado — llamar init_runtime_store() primero")
    return _store


def init_runtime_store(redis_client=None) -> RuntimeStore:
    global _store
    _store = RuntimeStore(redis_client=redis_client)
    return _store
