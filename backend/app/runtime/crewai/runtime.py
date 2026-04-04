from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, AsyncIterator

from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec

if TYPE_CHECKING:
    from crewai import Crew


class CrewAIRuntime(AgentRuntime):
    """
    Wrappea un CrewAI Crew.
    Usado para AgentSpec.mode == 'crew'.

    Nota sobre streaming: CrewAI ejecuta de forma síncrona internamente.
    El stream() emula streaming dividiendo la respuesta en oraciones,
    con un delay configurable para dar efecto typewriter.
    En Sprint 4 se evaluará integración con CrewAI callbacks para streaming real.
    """

    def __init__(self, crew: "Crew", spec: AgentSpec):
        self._crew = crew
        self.spec = spec
        self._last_results: dict[str, str] = {}  # session_id → último output

    async def invoke(self, input: str, session_id: str) -> AgentResponse:
        start = time.monotonic()

        # CrewAI es síncrono — lo corremos en thread pool para no bloquear el event loop
        result = await asyncio.to_thread(
            self._crew.kickoff,
            inputs={"input": input, "session_id": session_id},
        )

        # CrewAI retorna string o CrewOutput según versión
        output = str(result) if not isinstance(result, str) else result
        self._last_results[session_id] = output

        return AgentResponse(
            output=output,
            steps=[],                              # CrewAI no expone steps detallados por ahora
            latency_ms=(time.monotonic() - start) * 1000,
            session_id=session_id,
        )

    async def stream(self, input: str, session_id: str) -> AsyncIterator[str]:
        response = await self.invoke(input, session_id)

        # Divide por oraciones para efecto typewriter coherente
        sentences = _split_into_sentences(response.output)
        for sentence in sentences:
            yield sentence
            # Delay proporcional al largo de la oración — más natural que delay fijo
            await asyncio.sleep(len(sentence) * 0.008)

    def get_state(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "agent_mode": self.spec.mode.value,
            "framework": "crewai",
            "process": self.spec.process.value,
            "num_agents": len(self.spec.agents),
            "last_output_preview": (
                self._last_results.get(session_id, "")[:100]
                if session_id in self._last_results else None
            ),
        }

    def reset(self, session_id: str) -> None:
        self._last_results.pop(session_id, None)


def _split_into_sentences(text: str) -> list[str]:
    """
    Divide texto en oraciones/fragmentos para streaming emulado.
    Respeta saltos de línea y puntuación.
    """
    # Divide por . ! ? seguido de espacio o fin de línea, y por \n\n
    parts = re.split(r"(?<=[.!?])\s+|(?<=\n)\n", text)
    result = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            result.append(stripped + " ")
    return result if result else [text]
