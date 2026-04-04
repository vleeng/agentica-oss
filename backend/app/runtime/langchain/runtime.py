from __future__ import annotations

import time
from typing import TYPE_CHECKING, AsyncIterator

from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec

if TYPE_CHECKING:
    from langchain.agents import AgentExecutor
    from app.components.memory.base import MemoryAdapter


class LangChainRuntime(AgentRuntime):
    """
    Wrappea un LangChain AgentExecutor.
    Usado para AgentSpec.mode == 'single'.
    """

    def __init__(
        self,
        executor: "AgentExecutor",
        memory_adapter: "MemoryAdapter",
        spec: AgentSpec,
    ):
        self._executor = executor
        self._memory = memory_adapter
        self.spec = spec

    async def invoke(self, input: str, session_id: str) -> AgentResponse:
        start = time.monotonic()

        # Carga el historial de la sesión
        chat_history = await self._memory.load(session_id)

        result = await self._executor.ainvoke({
            "input": input,
            "chat_history": chat_history,
        })

        output: str = result.get("output", "")
        steps: list = result.get("intermediate_steps", [])

        # Persiste el turno en memoria
        await self._memory.save(session_id, input, output)

        # Extrae conteo de tokens si el LLM los provee
        tokens_in = 0
        tokens_out = 0
        if cb := result.get("__run", {}).get("callback_manager"):
            tokens_in = getattr(cb, "prompt_tokens", 0)
            tokens_out = getattr(cb, "completion_tokens", 0)

        return AgentResponse(
            output=output,
            steps=[{"tool": str(s[0]), "result": str(s[1])} for s in steps],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=(time.monotonic() - start) * 1000,
            session_id=session_id,
        )

    async def stream(self, input: str, session_id: str) -> AsyncIterator[str]:
        chat_history = await self._memory.load(session_id)
        collected_output = []

        async for chunk in self._executor.astream(
            {"input": input, "chat_history": chat_history}
        ):
            # LangChain puede emitir dicts con distintas keys según el agent_type
            token = ""
            if isinstance(chunk, dict):
                token = chunk.get("output") or chunk.get("token") or ""
            elif isinstance(chunk, str):
                token = chunk

            if token:
                collected_output.append(token)
                yield token

        # Persiste la respuesta completa una vez terminado el stream
        full_output = "".join(collected_output)
        await self._memory.save(session_id, input, full_output)

    def get_state(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "memory_type": self.spec.memory.type.value,
            "agent_mode": self.spec.mode.value,
            "framework": "langchain",
        }

    def reset(self, session_id: str) -> None:
        self._memory.clear(session_id)
