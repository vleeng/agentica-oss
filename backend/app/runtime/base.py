from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable

from app.schemas.agent import AgentResponse, AgentSpec


# ── Interfaz base — todo el sistema habla solo con esto ─────────────────────

class AgentRuntime(ABC):
    """
    Interfaz unificada de ejecución.
    LangChain, CrewAI y cualquier futuro framework viven detrás de esta abstracción.
    El resto del sistema (FastAPI endpoints, canales, eval engine) solo importa esta clase.
    """

    spec: AgentSpec

    @abstractmethod
    async def invoke(self, input: str, session_id: str) -> AgentResponse:
        """Invocación síncrona (request-response). Retorna la respuesta completa."""
        ...

    @abstractmethod
    async def stream(self, input: str, session_id: str) -> AsyncIterator[str]:
        """Streaming token a token. Para WebSocket y web chat."""
        ...

    @abstractmethod
    def get_state(self, session_id: str) -> dict:
        """Estado actual de la conversación (memoria, variables de contexto)."""
        ...

    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Limpia el estado de una sesión."""
        ...

    def get_spec(self) -> AgentSpec:
        return self.spec

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], Any] | None) -> None:
        """Hook opcional para notificar progreso al caller."""
        return None
