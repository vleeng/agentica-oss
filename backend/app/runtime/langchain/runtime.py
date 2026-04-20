from __future__ import annotations

import time
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import HTTPException
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec
from app.components.guardrails.guardrail_engine import check_input, check_output

if TYPE_CHECKING:
    from langchain.agents import AgentExecutor
    from app.components.memory.base import MemoryAdapter

GUARDRAIL_BLOCKED_MSG = "[Respuesta bloqueada por política de seguridad]"


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
        agent_id: str = "",
        session_factory=None,
    ):
        self._executor = executor
        self._memory = memory_adapter
        self.spec = spec
        self._agent_id = agent_id
        self._session_factory = session_factory

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

        # Pre-invoke: guardrails de entrada
        rules = await self._load_guardrail_rules()
        gr_in = await check_input(input, rules)
        if gr_in.action == "block":
            raise HTTPException(status_code=400, detail=f"Input bloqueado: {gr_in.reason}")

        # Carga el historial de la sesión
        chat_history = await self._memory.load(session_id)

        result = await self._executor.ainvoke({
            "input": input,
            "chat_history": chat_history,
        })

        output: str = result.get("output", "")
        steps: list = result.get("intermediate_steps", [])

        # Post-invoke: guardrails de salida
        gr_out = await check_output(output, rules)
        if gr_out.action == "block":
            output = GUARDRAIL_BLOCKED_MSG

        # Persiste el turno en memoria
        await self._memory.save(session_id, input, output)

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
        # Pre-stream: guardrails de entrada
        rules = await self._load_guardrail_rules()
        gr_in = await check_input(input, rules)
        if gr_in.action == "block":
            yield f"[Bloqueado: {gr_in.reason}]"
            return

        chat_history = await self._memory.load(session_id)
        collected_output = []

        async for chunk in self._executor.astream(
            {"input": input, "chat_history": chat_history}
        ):
            token = ""
            if isinstance(chunk, dict):
                token = chunk.get("output") or chunk.get("token") or ""
            elif isinstance(chunk, str):
                token = chunk

            if token:
                collected_output.append(token)
                yield token

        full_output = "".join(collected_output)

        # Post-stream: guardrails de salida
        gr_out = await check_output(full_output, rules)
        if gr_out.action == "block":
            full_output = GUARDRAIL_BLOCKED_MSG

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
