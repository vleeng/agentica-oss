from __future__ import annotations

import logging
import re
import warnings
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

# Patrones XML que algunos modelos emiten como texto en lugar de function calls
_XML_TOOL_PATTERNS = re.compile(
    r'<(?:minimax:|)tool_call>.*?</(?:minimax:|)tool_call>'
    r'|<invoke(?:\s[^>]*)?>.*?</invoke>'
    r'|<parameter(?:\s[^>]*)?>.*?</parameter>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_xml_tool_calls(text: str) -> str:
    """Elimina bloques XML de tool calls que algunos modelos emiten como texto plano."""
    cleaned = _XML_TOOL_PATTERNS.sub('', text)
    # Comprimir espacios y saltos de línea múltiples
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


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
                # AgentExecutor: usamos astream_events() para streaming token a token.
                # Capturamos on_chat_model_stream (tokens reales) y
                # on_chain_end de AgentExecutor (output final si el agente se detiene
                # por iteration limit o si todos los tokens eran tool-calls sin content).
                is_react = not hasattr(self._executor.agent, "functions")
                react_buffer = ""
                react_final_found = False
                chain_final_output: str = ""
                # Para agentes con function-calling: buffear tokens pre-tool
                # y solo emitir la respuesta final (después de que tools ejecutaron)
                pre_tool_buffer: list[str] = []
                tool_was_used = False
                in_final_response = False

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*beta.*")
                    event_stream = self._executor.astream_events(
                        {"input": input, "chat_history": chat_history},
                        version="v2",
                    )

                async for event in event_stream:
                    kind = event["event"]

                    if kind == "on_tool_start":
                        tool_was_used = True
                        pre_tool_buffer.clear()   # descartar razonamiento previo

                    elif kind == "on_tool_end":
                        in_final_response = True  # próximos tokens = respuesta final

                    # ── Tokens del LLM ───────────────────────────────────────
                    elif kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            continue  # selección de herramienta, no respuesta final
                        token = getattr(chunk, "content", "") or ""
                        if not token:
                            continue

                        if is_react and not react_final_found:
                            react_buffer += token
                            if "Final Answer:" in react_buffer:
                                react_final_found = True
                                after = react_buffer.split("Final Answer:", 1)[1]
                                if after:
                                    collected_output.append(after)
                                    yield after
                        elif not is_react:
                            if in_final_response:
                                # Post-tool: esta es la respuesta final
                                collected_output.append(token)
                                yield token
                            else:
                                # Pre-tool: buffear (puede ser razonamiento interno)
                                pre_tool_buffer.append(token)
                        else:
                            # ReAct con Final Answer ya encontrado
                            collected_output.append(token)
                            yield token

                    # ── Output final del AgentExecutor ───────────────────────
                    # Captura la respuesta cuando el agente paró por max_iterations
                    # o cuando ningún token de contenido fue emitido
                    elif kind == "on_chain_end" and event.get("name") == "AgentExecutor":
                        raw = event.get("data", {}).get("output", {})
                        if isinstance(raw, dict):
                            chain_final_output = raw.get("output", "") or ""
                        elif isinstance(raw, str):
                            chain_final_output = raw

                # Si no usó tools y la respuesta está en el pre_tool_buffer (respuesta directa)
                if not collected_output and not tool_was_used and pre_tool_buffer:
                    content = "".join(pre_tool_buffer)
                    content = _strip_xml_tool_calls(content)
                    if content:
                        collected_output.append(content)
                        yield content

                # Si el stream no emitió nada pero el agente sí produjo output,
                # lo emitimos ahora (caso: iteration limit, sin "Final Answer:" en react, etc.)
                if not collected_output and chain_final_output:
                    # Filtrar el mensaje genérico de LangChain por iteration limit
                    if "iteration limit" in chain_final_output.lower() or "time limit" in chain_final_output.lower():
                        # Intentar recuperar el último Thought del react_buffer como respuesta
                        if react_buffer:
                            last_thought = react_buffer.rsplit("Thought:", 1)[-1].strip()
                            # Quitar líneas de Action/Observation que quedaron
                            last_thought = last_thought.split("\nAction:")[0].split("\nObservation:")[0].strip()
                            if last_thought:
                                chain_final_output = last_thought
                            else:
                                chain_final_output = "Lo siento, no pude completar la respuesta. Por favor intentá reformular la pregunta."
                        else:
                            chain_final_output = "Lo siento, no pude completar la respuesta. Por favor intentá reformular la pregunta."
                    collected_output.append(chain_final_output)
                    yield chain_final_output
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
