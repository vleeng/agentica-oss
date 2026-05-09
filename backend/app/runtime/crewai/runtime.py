from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import HTTPException
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec
from app.components.guardrails.guardrail_engine import check_input, check_output

if TYPE_CHECKING:
    from crewai import Crew
    from app.components.memory.adapters import MemoryAdapter

GUARDRAIL_BLOCKED_MSG = "[Respuesta bloqueada por política de seguridad]"


class CrewAIRuntime(AgentRuntime):
    """
    Wrappea un CrewAI Crew.
    Usado para AgentSpec.mode == 'crew'.
    """

    def __init__(
        self,
        crew: "Crew",
        spec: AgentSpec,
        agent_id: str = "",
        session_factory=None,
        memory_adapter: "MemoryAdapter" | None = None,
    ):
        self._crew = crew
        self.spec = spec
        self._agent_id = agent_id
        self._session_factory = session_factory
        self._memory = memory_adapter
        self._last_results: dict[str, str] = {}

    async def _load_guardrail_rules(self) -> list[dict]:
        if not self._agent_id or not self._session_factory:
            return []
        try:
            async with self._session_factory() as session:
                from app.db.repository import AgentRepository
                return await AgentRepository(session).list_guardrail_rules(self._agent_id)
        except Exception:
            return []

    async def invoke(self, input: str, session_id: str) -> AgentResponse:
        start = time.monotonic()

        rules = await self._load_guardrail_rules()
        gr_in = await check_input(input, rules)
        if gr_in.action == "block":
            raise HTTPException(status_code=400, detail=f"Input bloqueado: {gr_in.reason}")

        contextual_input = input
        if self._memory:
            chat_history = await self._memory.load(session_id)
            contextual_input = _inject_history(input, chat_history)

        result = await asyncio.to_thread(
            self._crew.kickoff,
            inputs={"input": contextual_input, "session_id": session_id},
        )

        output = str(result) if not isinstance(result, str) else result

        gr_out = await check_output(output, rules)
        if gr_out.action == "block":
            output = GUARDRAIL_BLOCKED_MSG

        self._last_results[session_id] = output
        if self._memory:
            await self._memory.save(session_id, input, output)

        return AgentResponse(
            output=output,
            steps=[],
            latency_ms=(time.monotonic() - start) * 1000,
            session_id=session_id,
        )

    async def stream(self, input: str, session_id: str) -> AsyncIterator[str]:
        rules = await self._load_guardrail_rules()
        gr_in = await check_input(input, rules)
        if gr_in.action == "block":
            yield f"[Bloqueado: {gr_in.reason}]"
            return

        response = await self.invoke(input, session_id)

        sentences = _split_into_sentences(response.output)
        for sentence in sentences:
            yield sentence
            await asyncio.sleep(len(sentence) * 0.008)

    def get_state(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "agent_mode": self.spec.mode.value,
            "framework": "crewai",
            "process": self.spec.process.value,
            "num_agents": len(self.spec.agents),
            "memory_type": self.spec.memory.type.value,
            "last_output_preview": (
                self._last_results.get(session_id, "")[:100]
                if session_id in self._last_results else None
            ),
        }

    def reset(self, session_id: str) -> None:
        self._last_results.pop(session_id, None)
        if self._memory:
            self._memory.clear(session_id)


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


def _inject_history(user_input: str, chat_history: list[dict]) -> str:
    if not chat_history:
        return user_input

    recent_turns = chat_history[-12:]
    history_lines: list[str] = []
    for item in recent_turns:
        role = "Usuario" if item.get("role") == "user" else "Asistente"
        content = str(item.get("content", "")).strip()
        if content:
            history_lines.append(f"{role}: {content}")

    if not history_lines:
        return user_input

    return (
        "Contexto reciente de la conversación:\n"
        + "\n".join(history_lines)
        + "\n\nMensaje actual del usuario:\n"
        + user_input
    )
