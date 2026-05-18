from __future__ import annotations

import inspect
import json
import logging
import re
import time
import warnings
from collections import defaultdict
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable

from fastapi import HTTPException
from langchain.tools import BaseTool

from app.components.guardrails.guardrail_engine import check_input, check_output
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain.agents import AgentExecutor
    from app.components.memory.base import MemoryAdapter

GUARDRAIL_BLOCKED_MSG = "[Respuesta bloqueada por politica de seguridad]"

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
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _coerce_message_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            item_type = getattr(item, "type", None) if not isinstance(item, dict) else item.get("type")
            if item_type in {"text", "output_text"}:
                text = getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


class LangChainRuntime(AgentRuntime):
    """
    Wrappea un LangChain AgentExecutor, una chain simple o un runtime de grafo.
    Usado para AgentSpec.mode == 'single'.
    """

    def __init__(
        self,
        executor,                 # AgentExecutor | Runnable chain | None
        memory_adapter: "MemoryAdapter",
        spec: AgentSpec,
        agent_id: str = "",
        session_factory=None,
        is_simple_chain: bool = False,
        graph_blueprint: dict[str, Any] | None = None,
        llm=None,
        system_prompt: str = "",
        tools_by_name: dict[str, BaseTool] | None = None,
        graph_enabled: bool = False,
    ):
        self._executor = executor
        self._memory = memory_adapter
        self.spec = spec
        self._agent_id = agent_id
        self._session_factory = session_factory
        self._is_simple_chain = is_simple_chain
        self._graph_blueprint = graph_blueprint or {}
        self._llm = llm
        self._system_prompt = system_prompt
        self._tools_by_name = tools_by_name or {}
        self._graph_enabled = graph_enabled
        self._last_steps: list[dict[str, Any]] = []
        self._progress_callback: Callable[[dict[str, Any]], Any] | None = None

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], Any] | None) -> None:
        self._progress_callback = callback

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

        chat_history = await self._memory.load(session_id)

        if self._graph_enabled:
            await self._emit_progress("preparing", "Preparando flujo LangChain")
            output, steps = await self._invoke_graph(input=input, chat_history=chat_history)
        else:
            output, steps = await self._invoke_standard(input=input, chat_history=chat_history)

        gr_out = await check_output(output, rules)
        if gr_out.action == "block":
            output = GUARDRAIL_BLOCKED_MSG

        await self._memory.save(session_id, input, output)
        self._last_steps = steps

        return AgentResponse(
            output=output,
            steps=steps,
            tokens_in=0,
            tokens_out=0,
            latency_ms=(time.monotonic() - start) * 1000,
            session_id=session_id,
        )

    async def stream(self, input: str, session_id: str) -> AsyncIterator[str]:
        rules = await self._load_guardrail_rules()
        gr_in = await check_input(input, rules)
        if gr_in.action == "block":
            yield f"[Bloqueado: {gr_in.reason}]"
            return

        if self._graph_enabled:
            response = await self.invoke(input, session_id)
            for sentence in _split_into_sentences(response.output):
                yield sentence
            return

        chat_history = await self._memory.load(session_id)
        collected_output = []

        try:
            if self._is_simple_chain:
                async for chunk in self._executor.astream(
                    {"input": input, "chat_history": chat_history}
                ):
                    token = chunk if isinstance(chunk, str) else ""
                    if token:
                        collected_output.append(token)
                        yield token
            else:
                await self._emit_progress("status", "Pensando la mejor forma de resolverlo")
                is_react = not hasattr(self._executor.agent, "functions")
                react_buffer = ""
                react_final_found = False
                chain_final_output: str = ""
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
                        pre_tool_buffer.clear()
                        tool_name = str(event.get("name") or "herramienta")
                        tool_input = event.get("data", {}).get("input")
                        if tool_name == "knowledge_base":
                            query = _extract_tool_query(tool_input)
                            detail = _summarize_query(query)
                            message = f"Buscando en conocimientos{detail}"
                        else:
                            message = f"Usando herramienta: {tool_name}"
                        await self._emit_progress(
                            "status",
                            message,
                            actor=tool_name,
                            kind="tool",
                            query=_extract_tool_query(tool_input),
                        )

                    elif kind == "on_tool_end":
                        in_final_response = True
                        tool_name = str(event.get("name") or "herramienta")
                        tool_output = str(event.get("data", {}).get("output") or "").strip()
                        if tool_name == "knowledge_base":
                            titles = _extract_rag_titles(tool_output)
                            await self._emit_progress(
                                "status",
                                _summarize_rag_result(titles, tool_output),
                                actor=tool_name,
                                kind="rag_result",
                                titles=titles,
                            )
                        await self._emit_progress("status", "Armando la respuesta final", kind="answer")

                    elif kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            continue
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
                                if not collected_output:
                                    await self._emit_progress("status", "Redactando la respuesta", kind="answer")
                                collected_output.append(token)
                                yield token
                            else:
                                pre_tool_buffer.append(token)
                        else:
                            if not collected_output:
                                await self._emit_progress("status", "Redactando la respuesta", kind="answer")
                            collected_output.append(token)
                            yield token

                    elif kind == "on_chain_end" and event.get("name") == "AgentExecutor":
                        raw = event.get("data", {}).get("output", {})
                        if isinstance(raw, dict):
                            chain_final_output = raw.get("output", "") or ""
                        elif isinstance(raw, str):
                            chain_final_output = raw

                if not collected_output and not tool_was_used and pre_tool_buffer:
                    content = "".join(pre_tool_buffer)
                    content = _strip_xml_tool_calls(content)
                    if content:
                        collected_output.append(content)
                        yield content

                if not collected_output and chain_final_output:
                    if "iteration limit" in chain_final_output.lower() or "time limit" in chain_final_output.lower():
                        if react_buffer:
                            last_thought = react_buffer.rsplit("Thought:", 1)[-1].strip()
                            last_thought = last_thought.split("\nAction:")[0].split("\nObservation:")[0].strip()
                            if last_thought:
                                chain_final_output = last_thought
                            else:
                                chain_final_output = "Lo siento, no pude completar la respuesta. Por favor intenta reformular la pregunta."
                        else:
                            chain_final_output = "Lo siento, no pude completar la respuesta. Por favor intenta reformular la pregunta."
                    collected_output.append(chain_final_output)
                    yield chain_final_output
        except Exception as e:
            logger.exception(f"[STREAM] Error during stream for session {session_id}: {e}")
            raise

        full_output = "".join(collected_output)

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
            "graph_enabled": self._graph_enabled,
            "graph_node_count": len(self._graph_blueprint.get("nodes", [])) if isinstance(self._graph_blueprint, dict) else 0,
            "last_step_count": len(self._last_steps),
        }

    def reset(self, session_id: str) -> None:
        self._memory.clear(session_id)

    async def _invoke_standard(self, input: str, chat_history: list[dict]) -> tuple[str, list[dict]]:
        if self._is_simple_chain:
            output = await self._executor.ainvoke({
                "input": input,
                "chat_history": chat_history,
            })
            if not isinstance(output, str):
                output = str(output)
            steps: list[dict] = []
        else:
            result = await self._executor.ainvoke({
                "input": input,
                "chat_history": chat_history,
            })
            output = result.get("output", "")
            steps = [{"tool": str(s[0]), "result": str(s[1])} for s in result.get("intermediate_steps", [])]
        return output, steps

    async def _invoke_graph(self, *, input: str, chat_history: list[dict]) -> tuple[str, list[dict]]:
        blueprint = self._graph_blueprint if isinstance(self._graph_blueprint, dict) else {}
        nodes = blueprint.get("nodes", []) or []
        edges = blueprint.get("edges", []) or []
        if not nodes:
            logger.warning("[LangChainGraph] agent_id=%s graph enabled but blueprint is empty", self._agent_id)
            return await self._invoke_standard(input, chat_history)

        nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
        outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            src = str(edge.get("from") or "").strip()
            dst = str(edge.get("to") or "").strip()
            if src and dst and src in nodes_by_id and dst in nodes_by_id:
                outgoing[src].append(edge)

        start_node = next((node for node in nodes if node.get("type") == "start"), nodes[0])
        current_id = str(start_node.get("id"))
        logger.debug(
            "[LangChainGraph] agent_id=%s start_node=%s outgoing_from_start=%s node_count=%s edge_count=%s",
            self._agent_id,
            current_id,
            [str(edge.get("to") or "").strip() for edge in outgoing.get(current_id, [])],
            len(nodes),
            len(edges),
        )
        steps: list[dict[str, Any]] = []
        current_output = ""
        state: dict[str, Any] = {
            "user_input": input,
            "chat_history": chat_history,
            "step_outputs": [],
            "selected_tools": [],
            "rag_context_cache": {},
        }
        max_iterations = max(8, len(nodes) * 3)
        iterations = 0

        while current_id and iterations < max_iterations:
            iterations += 1
            node = nodes_by_id.get(current_id)
            if not node:
                break

            node_type = _normalize_node_type(node.get("type") or "agent")
            label = str(node.get("label") or current_id)
            logger.debug(
                "[LangChainGraph] agent_id=%s iter=%s node_id=%s node_type=%s label=%s next_candidates=%s",
                self._agent_id,
                iterations,
                current_id,
                node_type,
                label,
                [str(edge.get("to") or "").strip() for edge in outgoing.get(current_id, [])],
            )
            await self._emit_progress("trace", label, actor="LangChain Flow", kind=node_type)

            if node_type == "start":
                await self._emit_progress("status", "Entrando al flujo LangChain")
                current_id = self._first_outgoing(current_id, outgoing)
                continue

            if node_type == "end":
                await self._emit_progress("completed", "Flujo LangChain completado")
                break

            if node_type == "agent":
                await self._emit_progress("status", f"Ejecutando paso: {label}")
                current_output = await self._run_agent_node(node=node, state=state)
            elif node_type == "tool":
                current_output = await self._run_tool_node(node=node, state=state)
            elif node_type == "decision":
                await self._emit_progress("status", f"Resolviendo decision: {label}")
                decision = await self._run_decision_node(
                    node=node,
                    state=state,
                    outgoing_edges=outgoing.get(current_id, []),
                    nodes_by_id=nodes_by_id,
                )
                current_output = str(decision.get("reason") or "").strip()
                steps.append(
                    {
                        "node_id": current_id,
                        "node_type": "decision",
                        "label": label,
                        "output": current_output,
                        "decision": decision,
                    }
                )
                state["step_outputs"].append(
                    {
                        "node_id": current_id,
                        "label": label,
                        "type": node_type,
                        "output": current_output,
                    }
                )
                if decision.get("final_answer"):
                    current_output = str(decision["final_answer"]).strip()
                current_id = decision.get("next_node_id") or self._first_outgoing(current_id, outgoing)
                continue
            else:
                current_output = ""

            step = {
                "node_id": current_id,
                "node_type": node_type,
                "label": label,
                "output": current_output,
            }
            if node_type == "tool":
                step["tool_name"] = self._resolve_tool_name(node)
            steps.append(step)
            state["step_outputs"].append(
                {
                    "node_id": current_id,
                    "label": label,
                    "type": node_type,
                    "output": current_output,
                }
            )

            next_edges = outgoing.get(current_id, [])
            if len(next_edges) <= 1:
                current_id = next_edges[0].get("to") if next_edges else None
            else:
                selected = await self._select_branch(node=node, state=state, outgoing_edges=next_edges, nodes_by_id=nodes_by_id)
                current_id = selected or next_edges[0].get("to")

        if iterations >= max_iterations:
            await self._emit_progress("fallback", "El flujo alcanzo su limite de iteraciones; entregando el ultimo resultado util")

        final_output = await self._resolve_graph_output(current_output, state)
        return final_output, steps

    async def _run_agent_node(self, *, node: dict[str, Any], state: dict[str, Any]) -> str:
        rag_context = await self._get_graph_rag_context(
            state=state,
            query=self._build_rag_query(node=node, state=state),
        )
        logger.debug(
            "[LangChainGraph] agent_id=%s agent_node=%s rag_context=%s chars",
            self._agent_id,
            str(node.get("id") or node.get("label") or "agent"),
            len(rag_context or ""),
        )
        prompt = "\n\n".join(
            [
                self._system_prompt.strip(),
                f"Paso actual del flujo: {node.get('label', node.get('id', 'paso'))}",
                f"Descripcion del paso: {str(node.get('description') or '').strip() or 'Sin descripcion adicional.'}",
                "Trabaja sobre este paso del flujo. Si es intermedio, no hace falta responder al usuario final todavia.",
                "Apoyate en el contexto acumulado del flujo y produce una salida clara para este paso.",
                rag_context,
                _render_graph_context(state),
            ]
        ).strip()
        result = await self._llm.ainvoke(prompt)
        output = _strip_xml_tool_calls(_coerce_message_text(result)).strip()
        await self._emit_progress(
            "trace",
            _trim_trace(output),
            actor=str(node.get("label") or "Paso"),
            kind="answer",
        )
        summary = _summarize_step_output(output)
        if summary:
            await self._emit_progress(
                "status",
                f"Pensando: {summary}",
                actor=str(node.get("label") or "Paso"),
                kind="thought",
            )
        return output

    async def _run_tool_node(self, *, node: dict[str, Any], state: dict[str, Any]) -> str:
        tool_name = self._resolve_tool_name(node)
        tool = self._tools_by_name.get(tool_name)
        if not tool:
            logger.warning(
                "[LangChainGraph] agent_id=%s tool node missing runtime tool tool_name=%s label=%s available=%s",
                self._agent_id,
                tool_name,
                str(node.get("label") or ""),
                sorted(self._tools_by_name.keys()),
            )
            return f"[tool no disponible: {tool_name or 'sin tool_name'}]"

        payload = await self._build_tool_payload(tool=tool, node=node, state=state)
        logger.debug(
            "[LangChainGraph] agent_id=%s running tool=%s payload=%s",
            self._agent_id,
            tool_name,
            _trim_trace(str(payload)),
        )
        query = _extract_tool_query(payload)
        if tool_name == "knowledge_base":
            message = f"Buscando en conocimientos{_summarize_query(query)}"
        else:
            label = str(node.get("label") or tool_name).strip() or tool_name
            message = f"Usando {label}{_summarize_query(query, max_length=56)}"
        await self._emit_progress(
            "status",
            message,
            actor="knowledge_base" if tool_name == "knowledge_base" else str(node.get("label") or tool_name),
            kind="tool",
            query=query,
        )
        try:
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(payload)
            else:
                result = tool.invoke(payload)
        except Exception as exc:
            logger.exception("[LangChainGraph] tool %s failed: %s", tool_name, exc)
            return f"[error de tool {tool_name}: {exc}]"

        output = str(result or "").strip()
        logger.debug(
            "[LangChainGraph] agent_id=%s tool=%s output_chars=%s",
            self._agent_id,
            tool_name,
            len(output),
        )
        if tool_name == "knowledge_base":
            titles = _extract_rag_titles(output)
            snippets = _extract_rag_snippets(output)
            state["knowledge_base_context"] = output
            state["knowledge_base_query"] = query
            await self._emit_progress(
                "status",
                _summarize_rag_result(titles, output),
                actor="knowledge_base",
                kind="rag_result",
                titles=titles,
            )
            if snippets:
                await self._emit_progress(
                    "status",
                    f"Hallazgos: {' | '.join(snippets[:2])}",
                    actor="knowledge_base",
                    kind="rag_preview",
                )
        elif tool_name == "web_search":
            web_results = _extract_web_results(output)
            if web_results:
                state["web_search_results"] = web_results
                titles = [result["title"] for result in web_results if result.get("title")]
                await self._emit_progress(
                    "status",
                    _summarize_web_result(web_results),
                    actor="web_search",
                    kind="web_result",
                    titles=titles,
                )
                previews = [result["url"] for result in web_results if result.get("url")]
                if previews:
                    await self._emit_progress(
                        "status",
                        f"Fuentes web: {' | '.join(previews[:2])}",
                        actor="web_search",
                        kind="web_sources",
                    )
        await self._emit_progress(
            "trace",
            _trim_trace(output),
            actor=str(node.get("label") or tool_name),
            kind="answer",
        )
        return output

    async def _run_decision_node(
        self,
        *,
        node: dict[str, Any],
        state: dict[str, Any],
        outgoing_edges: list[dict[str, Any]],
        nodes_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if len(outgoing_edges) == 1:
            edge = outgoing_edges[0]
            return {
                "next_node_id": edge.get("to"),
                "reason": str(edge.get("condition") or "Ruta unica"),
                "final_answer": "",
            }

        branches = [
            {
                "next_node_id": edge.get("to"),
                "label": str(nodes_by_id.get(str(edge.get("to")), {}).get("label") or edge.get("to")),
                "condition": edge.get("condition"),
            }
            for edge in outgoing_edges
        ]
        prompt = "\n\n".join(
            [
                self._system_prompt.strip(),
                f"Nodo de decision: {node.get('label', node.get('id', 'decision'))}",
                f"Descripcion: {str(node.get('description') or '').strip() or 'Elegir el siguiente paso.'}",
                "Elige el siguiente nodo segun el contexto del flujo.",
                "Responde solo con JSON valido usando este formato:",
                '{"next_node_id":"...", "reason":"...", "final_answer":""}',
                "Ramas disponibles:",
                json.dumps(branches, ensure_ascii=False, indent=2),
                _render_graph_context(state),
            ]
        ).strip()
        raw = await self._llm.ainvoke(prompt)
        parsed = self._parse_branch_response(_coerce_message_text(raw), branches)
        await self._emit_progress(
            "trace",
            f"Decision: {parsed.get('reason') or parsed.get('next_node_id')}",
            actor=str(node.get("label") or "Decision"),
            kind="decision",
        )
        await self._emit_progress(
            "status",
            f"Pensando: {parsed.get('reason') or 'eligiendo el siguiente paso'}",
            actor=str(node.get("label") or "Decision"),
            kind="decision",
        )
        return parsed

    async def _select_branch(
        self,
        *,
        node: dict[str, Any],
        state: dict[str, Any],
        outgoing_edges: list[dict[str, Any]],
        nodes_by_id: dict[str, dict[str, Any]],
    ) -> str | None:
        decision = await self._run_decision_node(
            node=node,
            state=state,
            outgoing_edges=outgoing_edges,
            nodes_by_id=nodes_by_id,
        )
        return decision.get("next_node_id")

    async def _build_tool_payload(self, *, tool: BaseTool, node: dict[str, Any], state: dict[str, Any]) -> Any:
        args_schema = getattr(tool, "args_schema", None)
        context_text = _render_graph_context(state)
        fallback_query = _default_tool_input(state)

        if not args_schema:
            return fallback_query

        try:
            schema = args_schema.model_json_schema()
        except Exception:
            schema = {}

        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        field_names = list(properties.keys())
        if len(field_names) == 1:
            return {field_names[0]: fallback_query}
        if "query" in properties:
            payload = {"query": fallback_query}
            if "max_results" in properties:
                payload["max_results"] = 5
            return payload
        if "expression" in properties:
            return {"expression": fallback_query}

        prompt = "\n\n".join(
            [
                "Prepara exclusivamente el JSON de argumentos para ejecutar una herramienta.",
                f"Herramienta: {tool.name}",
                f"Descripcion: {getattr(tool, 'description', '')}",
                f"Paso del flujo: {node.get('label', node.get('id', 'tool'))}",
                f"Descripcion del paso: {str(node.get('description') or '').strip() or 'Sin descripcion.'}",
                "Esquema esperado (JSON Schema simplificado):",
                json.dumps(schema, ensure_ascii=False, indent=2),
                "Contexto disponible:",
                context_text,
                "Responde solo con JSON valido, sin markdown.",
            ]
        ).strip()
        raw = await self._llm.ainvoke(prompt)
        text = _coerce_message_text(raw).strip()
        try:
            parsed = json.loads(_extract_json_block(text))
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
        return fallback_query

    def _resolve_tool_name(self, node: dict[str, Any]) -> str:
        data = node.get("data") or {}
        tool_name = str(data.get("tool_name") or "").strip()
        if tool_name:
            return tool_name
        label = str(node.get("label") or "").strip()
        if label in self._tools_by_name:
            return label
        normalized_label = _normalize_tool_key(label)
        if normalized_label in self._tools_by_name:
            return normalized_label
        for available_name in self._tools_by_name:
            if _normalize_tool_key(available_name) == normalized_label:
                return available_name
        return label

    def _parse_branch_response(self, raw_text: str, branches: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            parsed = json.loads(_extract_json_block(raw_text))
        except Exception:
            parsed = {}

        next_node_id = str(parsed.get("next_node_id") or "").strip()
        valid_ids = {str(branch.get("next_node_id")) for branch in branches}
        if next_node_id not in valid_ids:
            next_node_id = str(branches[0].get("next_node_id"))
        return {
            "next_node_id": next_node_id,
            "reason": str(parsed.get("reason") or "").strip() or "Ruta seleccionada por el flujo.",
            "final_answer": str(parsed.get("final_answer") or "").strip(),
        }

    async def _resolve_graph_output(self, current_output: str, state: dict[str, Any]) -> str:
        outputs = list(state.get("step_outputs") or [])
        selected_step: dict[str, Any] | None = None
        selected_output = ""

        for step in reversed(outputs):
            output = str(step.get("output") or "").strip()
            if not output:
                continue
            if selected_step is None:
                selected_step = step
                selected_output = output
            if not _is_low_signal_output(output):
                selected_step = step
                selected_output = output
                break

        if not selected_output:
            selected_output = str(current_output or "").strip()

        if (
            self._llm is not None
            and selected_step is not None
            and self._should_synthesize_graph_output(selected_step, selected_output)
        ):
            synthesized = await self._synthesize_graph_output(state)
            if synthesized and not _is_low_signal_output(synthesized):
                return _append_web_citations(synthesized, state)

        if self._llm is not None and (
            not selected_output
            or _looks_like_internal_graph_output(selected_output)
        ):
            fallback = await self._direct_graph_fallback(state)
            if fallback and not _is_low_signal_output(fallback):
                return _append_web_citations(fallback, state)

        if selected_output:
            return _append_web_citations(selected_output, state)
        if self._llm is not None:
            fallback = await self._direct_graph_fallback(state)
            if fallback and not _is_low_signal_output(fallback):
                return _append_web_citations(fallback, state)
        return "No se genero una salida visible para este flujo."

    def _should_synthesize_graph_output(self, step: dict[str, Any], output: str) -> bool:
        step_type = str(step.get("type") or step.get("node_type") or "").strip().lower()
        if _is_low_signal_output(output):
            return True
        if step_type in {"tool", "decision"}:
            return True
        if step_type == "agent":
            normalized = output.strip().lower()
            if normalized.startswith("decision:") or normalized.startswith("[") or "fuente:" in normalized:
                return True
        return False

    async def _synthesize_graph_output(self, state: dict[str, Any]) -> str:
        rag_context = await self._get_graph_rag_context(
            state=state,
            query=self._build_rag_query(state=state),
        )
        prompt = "\n\n".join(
            [
                self._system_prompt.strip(),
                "Tu tarea ahora es redactar la respuesta final para el usuario usando el trabajo ya realizado por el flujo.",
                "No describas el flujo interno, no menciones nodos, decisiones ni herramientas salvo que sea realmente necesario para responder.",
                "Si hubo resultados de busqueda o herramientas, sintetizalos en una respuesta natural, util y directa.",
                _render_web_source_instruction(state),
                "Si faltan datos externos o una herramienta no estuvo disponible, responde igual con la mejor ayuda posible sin inventar hechos.",
                "Entrega solo la respuesta final lista para mostrar en el chat.",
                rag_context,
                _render_graph_context(state),
            ]
        ).strip()
        try:
            result = await self._llm.ainvoke(prompt)
        except Exception as exc:
            logger.exception("[LangChainGraph] final synthesis failed: %s", exc)
            return ""
        return _strip_xml_tool_calls(_coerce_message_text(result)).strip()

    async def _direct_graph_fallback(self, state: dict[str, Any]) -> str:
        rag_context = await self._get_graph_rag_context(
            state=state,
            query=self._build_rag_query(state=state),
        )
        prompt = "\n\n".join(
            [
                self._system_prompt.strip(),
                "Responde directamente al ultimo mensaje del usuario con una respuesta breve, clara y util.",
                "No menciones el flujo interno, herramientas, decisiones ni errores tecnicos.",
                "Si el usuario solo saluda, responde al saludo e invita a pedir una receta o ayuda concreta.",
                _render_web_source_instruction(state),
                "Si faltan datos para cumplir el objetivo, pide la aclaracion minima necesaria.",
                "Entrega solo la respuesta final lista para mostrar en el chat.",
                rag_context,
                _render_graph_context(state),
            ]
        ).strip()
        try:
            result = await self._llm.ainvoke(prompt)
        except Exception as exc:
            logger.exception("[LangChainGraph] direct fallback failed: %s", exc)
            return ""
        return _strip_xml_tool_calls(_coerce_message_text(result)).strip()

    def _build_rag_query(self, *, state: dict[str, Any], node: dict[str, Any] | None = None) -> str:
        parts = [str(state.get("user_input") or "").strip()]
        if node is not None:
            label = str(node.get("label") or node.get("id") or "").strip()
            description = str(node.get("description") or "").strip()
            if label:
                parts.append(f"Paso del flujo: {label}")
            if description:
                parts.append(f"Descripcion del paso: {description}")
        return "\n".join(part for part in parts if part).strip()

    async def _get_graph_rag_context(self, *, state: dict[str, Any], query: str) -> str:
        if not self._rag_available() or not self._agent_id:
            logger.debug(
                "[LangChainGraph] agent_id=%s rag skipped available=%s query_present=%s",
                self._agent_id,
                self._rag_available(),
                bool(query.strip()),
            )
            return ""

        normalized_query = query.strip()
        if not normalized_query:
            return ""

        cache = state.setdefault("rag_context_cache", {})
        if normalized_query in cache:
            return cache[normalized_query]

        cached_tool_context = str(state.get("knowledge_base_context") or "").strip()
        cached_tool_query = str(state.get("knowledge_base_query") or "").strip()
        user_input = str(state.get("user_input") or "").strip()
        if (
            cached_tool_context
            and user_input
            and _normalize_rag_key(cached_tool_query or user_input) == _normalize_rag_key(user_input)
            and normalized_query.startswith(user_input)
        ):
            cache[normalized_query] = cached_tool_context
            return cached_tool_context

        try:
            from app.components.rag.knowledge_builder import KnowledgeBuilderService

            kb = KnowledgeBuilderService()
            accessible_kb_ids = await self._assigned_kb_ids(state)
            logger.debug(
                "[LangChainGraph] agent_id=%s retrieving rag query=%s assigned_kbs=%s include_agent_source=%s",
                self._agent_id,
                _trim_trace(normalized_query),
                accessible_kb_ids,
                False,
            )
            if not accessible_kb_ids:
                cache[normalized_query] = ""
                return ""
            context = await kb.retrieve_as_context(
                self._agent_id,
                normalized_query,
                self.spec.rag.top_k,
                extra_owner_ids=accessible_kb_ids,
                include_agent_source=False,
            )
        except Exception as exc:
            logger.warning("[LangChainGraph] RAG context unavailable for agent %s: %s", self._agent_id, exc)
            context = ""

        logger.debug(
            "[LangChainGraph] agent_id=%s rag retrieved chars=%s",
            self._agent_id,
            len(context or ""),
        )
        cache[normalized_query] = context or ""
        return cache[normalized_query]

    def _rag_available(self) -> bool:
        rag = getattr(self.spec, "rag", None)
        if rag and getattr(rag, "enabled", False):
            return True
        blueprint = self._graph_blueprint if isinstance(self._graph_blueprint, dict) else {}
        nodes = blueprint.get("nodes", []) or []
        for node in nodes:
            if _normalize_node_type(node.get("type")) != "tool":
                continue
            data = node.get("data") or {}
            tool_name = str(data.get("tool_name") or "").strip().lower()
            if tool_name == "knowledge_base":
                return True
            label = str(node.get("label") or "").strip().lower().replace(" ", "_")
            if label in {"knowledge_base", "base_de_conocimientos"}:
                return True
        return False

    async def _assigned_kb_ids(self, state: dict[str, Any]) -> list[str]:
        cached = state.get("assigned_kb_ids")
        if isinstance(cached, list):
            return cached
        if not self._session_factory or not self._agent_id:
            state["assigned_kb_ids"] = []
            return []
        try:
            from app.db.repository import AgentRepository

            async with self._session_factory() as session:
                repo = AgentRepository(session)
                rows = await repo.get_agent_knowledge_bases(self._agent_id)
        except Exception as exc:
            logger.debug("[LangChainGraph] Could not load assigned KBs for %s: %s", self._agent_id, exc)
            state["assigned_kb_ids"] = []
            return []

        kb_ids = [str(row.get("id") or "").strip() for row in rows if str(row.get("id") or "").strip()]
        state["assigned_kb_ids"] = kb_ids
        return kb_ids

    def _first_outgoing(self, node_id: str, outgoing: dict[str, list[dict[str, Any]]]) -> str | None:
        edge = next(iter(outgoing.get(node_id, [])), None)
        return str(edge.get("to")) if edge else None

    async def _emit_progress(self, phase: str, message: str, **extra: Any) -> None:
        callback = self._progress_callback
        if callback is None:
            return
        payload = {"framework": "langchain", "phase": phase, "message": message, **extra}
        try:
            result = callback(payload)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.debug("[LangChain][Progress] callback failed: %s", exc)


def _render_graph_context(state: dict[str, Any]) -> str:
    history = state.get("chat_history") or []
    recent_history = history[-8:]
    history_lines: list[str] = []
    for item in recent_history:
        role = "Usuario" if item.get("role") == "user" else "Asistente"
        content = str(item.get("content") or "").strip()
        if content:
            history_lines.append(f"{role}: {content}")

    outputs = state.get("step_outputs") or []
    output_lines: list[str] = []
    for step in outputs[-6:]:
        label = str(step.get("label") or step.get("node_id") or "paso")
        output = str(step.get("output") or "").strip()
        if output:
            output_lines.append(f"[{label}]\n{output}")

    parts = [
        "Mensaje actual del usuario:",
        str(state.get("user_input") or "").strip(),
    ]
    if history_lines:
        parts.extend(["", "Historial reciente:", "\n".join(history_lines)])
    if output_lines:
        parts.extend(["", "Salidas previas del flujo:", "\n\n".join(output_lines)])
    return "\n".join(part for part in parts if part is not None).strip()


def _render_web_source_instruction(state: dict[str, Any]) -> str:
    web_results = state.get("web_search_results") or []
    if not isinstance(web_results, list) or not web_results:
        return ""
    return (
        "Como se usaron resultados web, al final de la respuesta inclui una seccion titulada "
        "'Fuentes web' con las URLs realmente usadas, una por linea o en lista."
    )


def _default_tool_input(state: dict[str, Any]) -> str:
    outputs = state.get("step_outputs") or []
    for step in reversed(outputs):
        output = str(step.get("output") or "").strip()
        if output:
            return output
    return str(state.get("user_input") or "").strip()


def _extract_tool_query(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("query", "input", "text", "expression"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
        return ""
    return str(value or "").strip()


def _normalize_node_type(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    if "." in text:
        text = text.split(".")[-1]
    return text.lower()


def _summarize_query(query: str, max_length: int = 72) -> str:
    text = " ".join(str(query or "").split()).strip()
    if not text:
        return ""
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    return f": {text}"


def _extract_rag_titles(output: str) -> list[str]:
    titles: list[str] = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if "(fuente:" not in line.lower():
            continue
        try:
            source = line.split("fuente:", 1)[1].split(")", 1)[0].strip()
        except Exception:
            continue
        if not source:
            continue
        source = source.replace("\\", "/").rstrip("/")
        title = source.split("/")[-1] or source
        if title not in titles:
            titles.append(title)
    return titles


def _summarize_rag_result(titles: list[str], output: str) -> str:
    if titles:
        preview = ", ".join(titles[:3])
        if len(titles) > 3:
            preview += f" y {len(titles) - 3} mas"
        return f"Encontre en conocimientos: {preview}"
    lowered = str(output or "").strip().lower()
    if "no se encontro" in lowered or "no encontr" in lowered:
        return "No encontre informacion relevante en conocimientos"
    snippets = _extract_rag_snippets(output)
    if snippets:
        preview = " | ".join(snippets[:2])
        return f"Encontre en conocimientos: {preview}"
    return "Revise los conocimientos disponibles"


def _extract_rag_snippets(output: str) -> list[str]:
    snippets: list[str] = []
    capture_next = False
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "(fuente:" in line.lower():
            capture_next = True
            continue
        if capture_next:
            snippet = " ".join(line.split()).strip()
            if len(snippet) > 90:
                snippet = snippet[:87].rstrip() + "..."
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            capture_next = False
    return snippets


def _extract_web_results(output: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    title = ""
    content_lines: list[str] = []
    url = ""

    def flush() -> None:
        nonlocal title, content_lines, url
        if not (title or url):
            title = ""
            content_lines = []
            url = ""
            return
        results.append(
            {
                "title": title.strip(),
                "content": " ".join(line.strip() for line in content_lines if line.strip()).strip(),
                "url": url.strip(),
            }
        )
        title = ""
        content_lines = []
        url = ""

    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("**") and line.endswith("**") and len(line) > 4:
            flush()
            title = line.strip("* ").strip()
            continue
        if line.lower().startswith("fuente:"):
            url = line.split(":", 1)[1].strip()
            flush()
            continue
        content_lines.append(line)

    flush()
    return [result for result in results if result.get("title") or result.get("url")]


def _summarize_web_result(results: list[dict[str, str]]) -> str:
    titles = [result["title"] for result in results if result.get("title")]
    if titles:
        preview = " | ".join(titles[:2])
        if len(titles) > 2:
            preview += f" | y {len(titles) - 2} más"
        return f"Encontré en web: {preview}"
    urls = [result["url"] for result in results if result.get("url")]
    if urls:
        return f"Encontré en web: {urls[0]}"
    return "Encontré resultados en web"


def _format_web_sources(state: dict[str, Any]) -> str:
    web_results = state.get("web_search_results") or []
    if not isinstance(web_results, list) or not web_results:
        return ""
    lines = ["Fuentes web:"]
    for result in web_results[:5]:
        title = str(result.get("title") or "").strip()
        url = str(result.get("url") or "").strip()
        if title and url:
            lines.append(f"- {title}: {url}")
        elif url:
            lines.append(f"- {url}")
    return "\n".join(lines) if len(lines) > 1 else ""


def _append_web_citations(text: str, state: dict[str, Any]) -> str:
    response = str(text or "").strip()
    if not response:
        return response
    sources_block = _format_web_sources(state)
    if not sources_block:
        return response
    lowered = response.lower()
    if "fuentes web:" in lowered or "http://" in lowered or "https://" in lowered:
        return response
    return f"{response}\n\n{sources_block}"


def _summarize_step_output(output: str) -> str:
    text = " ".join(str(output or "").split()).strip()
    if not text:
        return ""
    if len(text) > 180:
        return ""
    lowered = text.lower()
    if any(marker in lowered for marker in ["## ", "### ", "ingredientes", "preparacion", "respuesta final:", "final answer:"]):
        return ""
    if text.startswith(("[", "-", "*")):
        return ""
    return text


def _extract_json_block(text: str) -> str:
    candidate = str(text or "").strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    return match.group(0) if match else candidate


def _trim_trace(text: str, limit: int = 900) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _normalize_tool_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _normalize_rag_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _is_low_signal_output(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return True
    low_signal_markers = (
        "no se genero una salida visible",
        "sin resultados.",
        "sin resultados",
        "respuesta bloqueada por politica de seguridad",
        "[tool no disponible:",
        "[error de tool",
    )
    return any(marker in normalized for marker in low_signal_markers)


def _looks_like_internal_graph_output(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return True
    internal_markers = (
        "decision:",
        "ruta seleccionada",
        "para continuar segun el flujo",
        "se requiere informacion adicional",
        "fuente:",
        "**",
        "[web_search",
    )
    return any(marker in normalized for marker in internal_markers)


def _split_into_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|(?<=\n)\n", text)
    result = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            result.append(stripped + " ")
    return result if result else [text]
