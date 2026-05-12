from __future__ import annotations

import asyncio
import json
import re
import time
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import HTTPException

from app.components.guardrails.guardrail_engine import check_input, check_output
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentResponse, AgentSpec

if TYPE_CHECKING:
    from crewai import Crew
    from app.components.memory.adapters import MemoryAdapter

GUARDRAIL_BLOCKED_MSG = "[Respuesta bloqueada por politica de seguridad]"


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
        task_plan: list[dict] | None = None,
        decision_plan: list[dict] | None = None,
        review_llm=None,
    ):
        self._crew = crew
        self.spec = spec
        self._agent_id = agent_id
        self._session_factory = session_factory
        self._memory = memory_adapter
        self._last_results: dict[str, str] = {}
        self._task_plan = task_plan or []
        self._decision_plan = decision_plan or []
        self._review_llm = review_llm
        self._max_review_loops = 1

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

        output, steps = await self._run_blueprint(contextual_input, session_id)

        gr_out = await check_output(output, rules)
        if gr_out.action == "block":
            output = GUARDRAIL_BLOCKED_MSG

        self._last_results[session_id] = output
        if self._memory:
            await self._memory.save(session_id, input, output)

        return AgentResponse(
            output=output,
            steps=steps,
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
            "graph_task_count": len(self._task_plan),
            "decision_count": len(self._decision_plan),
            "last_output_preview": (
                self._last_results.get(session_id, "")[:100]
                if session_id in self._last_results
                else None
            ),
        }

    def reset(self, session_id: str) -> None:
        self._last_results.pop(session_id, None)
        if self._memory:
            self._memory.clear(session_id)

    async def _run_blueprint(self, contextual_input: str, session_id: str) -> tuple[str, list[dict]]:
        attempt_input = contextual_input
        last_result = ""
        last_steps: list[dict] = []

        for attempt in range(self._max_review_loops + 1):
            compact_input = _compact_runtime_input(attempt_input)
            result = await asyncio.to_thread(
                self._crew.kickoff,
                inputs={
                    "input": attempt_input,
                    "input_compact": compact_input,
                    "session_id": session_id,
                },
            )
            last_result = str(result) if not isinstance(result, str) else result
            last_steps = self._collect_steps()
            last_steps = await self._evaluate_decisions(last_steps, attempt_input)

            decision = self._find_rejection_decision(last_steps)
            if not decision:
                return self._resolve_visible_output(last_result, last_steps), last_steps

            if attempt >= self._max_review_loops:
                return self._resolve_visible_output(last_result, last_steps), last_steps

            attempt_input = _augment_input_with_review_feedback(
                original_input=contextual_input,
                reason=decision.get("reason") or "La revision pidio mas trabajo.",
                retry_from=decision.get("retry_from"),
            )

        return self._resolve_visible_output(last_result, last_steps), last_steps

    def _collect_steps(self) -> list[dict]:
        steps: list[dict] = []
        crew_tasks = list(getattr(self._crew, "tasks", []) or [])

        for index, task in enumerate(crew_tasks):
            plan = self._task_plan[index] if index < len(self._task_plan) else {}
            task_output = getattr(task, "output", None)
            raw_output = ""
            if task_output is not None:
                raw_output = str(getattr(task_output, "raw", "") or "")

            step = {
                "node_id": plan.get("node_id"),
                "node_type": plan.get("node_type", "agent"),
                "label": plan.get("label") or getattr(task, "description", f"task_{index + 1}"),
                "agent_name": plan.get("agent_name"),
                "output": raw_output,
                "retry_targets": plan.get("retry_targets", []),
            }
            if step["node_type"] == "decision":
                step["decision"] = _parse_decision_output(raw_output)
            steps.append(step)

        return steps

    async def _evaluate_decisions(self, steps: list[dict], contextual_input: str) -> list[dict]:
        if not self._decision_plan or self._review_llm is None:
            return steps

        evaluated_steps = list(steps)
        for plan in self._decision_plan:
            prompt = _build_runtime_decision_input(
                plan=plan,
                steps=evaluated_steps,
                user_input=contextual_input,
            )
            raw_output = await asyncio.to_thread(self._review_llm.call, prompt)
            decision = _parse_decision_output(raw_output)
            evaluated_steps.append(
                {
                    "node_id": plan.get("node_id"),
                    "node_type": "decision",
                    "label": plan.get("label") or plan.get("node_id"),
                    "agent_name": plan.get("agent_name"),
                    "output": raw_output,
                    "retry_targets": plan.get("retry_targets", []),
                    "decision": decision,
                }
            )
        return evaluated_steps

    @staticmethod
    def _find_rejection_decision(steps: list[dict]) -> dict | None:
        for step in steps:
            if step.get("node_type") != "decision":
                continue
            decision = step.get("decision")
            if not decision:
                continue
            if decision.get("approved") is False:
                return decision
        return None

    @staticmethod
    def _resolve_visible_output(last_result: str, steps: list[dict]) -> str:
        for step in reversed(steps):
            if step.get("node_type") == "decision":
                decision = step.get("decision") or {}
                final_answer = str(decision.get("final_answer") or "").strip()
                if decision.get("approved") is True and final_answer:
                    return final_answer
                continue

            output = str(step.get("output") or "").strip()
            if output:
                return output

        return last_result


def _split_into_sentences(text: str) -> list[str]:
    """
    Divide texto en oraciones/fragmentos para streaming emulado.
    Respeta saltos de linea y puntuacion.
    """
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
        "Contexto reciente de la conversacion:\n"
        + "\n".join(history_lines)
        + "\n\nMensaje actual del usuario:\n"
        + user_input
    )


def _compact_runtime_input(user_input: str, limit: int = 4500) -> str:
    text = str(user_input or "").strip()
    if len(text) <= limit:
        return text
    head = text[:3000].rstrip()
    tail = text[-1200:].lstrip()
    return (
        head
        + "\n\n[... contenido intermedio resumido para acelerar el crew ...]\n\n"
        + tail
    )


def _parse_decision_output(raw_output: str) -> dict | None:
    if not raw_output:
        return None

    candidate = raw_output.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    approved = data.get("approved")
    if isinstance(approved, str):
        approved = approved.strip().lower() == "true"

    retry_from = data.get("retry_from")
    if retry_from is not None:
        retry_from = str(retry_from).strip() or None

    return {
        "approved": approved,
        "reason": str(data.get("reason") or "").strip(),
        "retry_from": retry_from,
        "final_answer": str(data.get("final_answer") or "").strip(),
    }


def _build_runtime_decision_input(plan: dict, steps: list[dict], user_input: str) -> str:
    relevant_outputs: list[str] = []
    upstream_ids = set(plan.get("upstream_node_ids") or [])

    for step in steps:
        if step.get("node_type") == "decision":
            continue
        if upstream_ids and step.get("node_id") not in upstream_ids:
            continue
        label = str(step.get("label") or step.get("node_id") or "paso")
        output = str(step.get("output") or "").strip()
        if output:
            relevant_outputs.append(f"[{label}]\n{output}")

    if not relevant_outputs:
        for step in steps:
            if step.get("node_type") == "decision":
                continue
            label = str(step.get("label") or step.get("node_id") or "paso")
            output = str(step.get("output") or "").strip()
            if output:
                relevant_outputs.append(f"[{label}]\n{output}")

    return (
        f"{plan.get('prompt', '').strip()}\n\n"
        f"Input original del usuario:\n{user_input}\n\n"
        "Resultados previos del flujo:\n"
        + ("\n\n".join(relevant_outputs) if relevant_outputs else "Sin resultados previos disponibles.")
    )


def _augment_input_with_review_feedback(original_input: str, reason: str, retry_from: str | None) -> str:
    retry_line = (
        f"Volve a trabajar desde el paso '{retry_from}'."
        if retry_from
        else "Revisa y mejora el flujo antes de responder."
    )
    return (
        f"{original_input}\n\n"
        "[Feedback de revision interna]\n"
        f"- Motivo: {reason}\n"
        f"- Instruccion: {retry_line}\n"
        "- Rehace el trabajo necesario y devolve una respuesta final lista para el usuario."
    )
