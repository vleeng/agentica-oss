from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import HTTPException
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec
from app.components.guardrails.guardrail_engine import check_input, check_output

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain.agents import AgentExecutor
    from app.components.memory.base import MemoryAdapter

GUARDRAIL_BLOCKED_MSG = "[Respuesta bloqueada por política de seguridad]"


class LangChainRuntime(AgentRuntime):
    """
    Wrappea un LangChain AgentExecutor O un chain simple (prompt | llm | parser).
    Usado para AgentSpec.mode == 'single'.
    """

    def __init__(
        self,
        executor,                 # AgentExecutor | Runnable chain
        memory_adapter: "MemoryAdapter",
        spec: AgentSpec,
        agent_id: str = "",
        session_factory=None,
        is_simple_chain: bool = False,
    ):
        self._executor = executor
        self._memory = memory_adapter
        self.spec = spec
        self._agent_id = agent_id
        self._session_factory = session_factory
        self._is_simple_chain = is_simple_chain

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

        if self._is_simple_chain:
            # Chain simple: retorna string directamente
            output = await self._executor.ainvoke({
                "input": input,
                "chat_history": chat_history,
            })
            if not isinstance(output, str):
                output = str(output)
            steps: list = []
        else:
            result = await self._executor.ainvoke({
                "input": input,
                "chat_history": chat_history,
            })
            output = result.get("output", "")
            steps = result.get("intermediate_steps", [])

        # Post-invoke: guardrails de salida
        gr_out = await check_output(output, rules)
        if gr_out.action == "block":
            output = GUARDRAIL_BLOCKED_MSG

        # Persiste el turno en memoria
        await self._memory.save(session_id, input, output)

        return AgentResponse(
            output=output,
            steps=[{"tool": str(s[0]), "result": str(s[1])} for s in steps],
            tokens_in=0,
            tokens_out=0,
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

        try:
            if self._is_simple_chain:
                # Chain simple: LCEL propaga el streaming token a token desde el LLM
                async for chunk in self._executor.astream(
                    {"input": input, "chat_history": chat_history}
                ):
                    token = chunk if isinstance(chunk, str) else ""
                    if token:
                        collected_output.append(token)
                        yield token
            else:
                # AgentExecutor: astream() solo emite el output final completo.
                # astream_events() sí expone tokens individuales del LLM en tiempo real.
                #
                # Para openai_functions: los tool-call chunks tienen content="" y
                # tool_call_chunks=[...], así que solo el texto de la respuesta final pasa.
                #
                # Para react: el LLM produce "Thought:/Action:/Final Answer:" como texto.
                # Acumulamos y solo emitimos lo que viene después de "Final Answer:".
                is_react = not hasattr(self._executor.agent, "functions")
                react_buffer = ""
                react_final_found = False

                async for event in self._executor.astream_events(
                    {"input": input, "chat_history": chat_history},
                    version="v2",
                ):
                    if event["event"] != "on_chat_model_stream":
                        continue
                    chunk = event["data"]["chunk"]
                    # Saltar chunks que son llamadas a herramientas (no texto de respuesta)
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        continue
                    token = getattr(chunk, "content", "") or ""
                    if not token:
                        continue

                    if is_react and not react_final_found:
                        # Acumular hasta encontrar "Final Answer:"
                        react_buffer += token
                        marker = "Final Answer:"
                        if marker in react_buffer:
                            react_final_found = True
                            after = react_buffer.split(marker, 1)[1]
                            if after:
                                collected_output.append(after)
                                yield after
                        # Si no encontramos el marcador, no emitimos nada aún
                    else:
                        collected_output.append(token)
                        yield token
        except Exception as e:
            logger.exception(f"[STREAM] Error during stream for session {session_id}: {e}")
            raise

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
