from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import get_settings
from app.schemas.wizard_advisor import (
    WizardAdvisorItem,
    WizardAdvisorRequest,
    WizardAdvisorResponse,
)
from app.services.llm_client import TextGenerationClient

settings = get_settings()


class WizardAdvisorService:
    def __init__(self, client: TextGenerationClient | None = None):
        self._client = client or TextGenerationClient()

    async def analyze(self, request: WizardAdvisorRequest) -> WizardAdvisorResponse:
        fallback = self._rule_based_review(request)
        try:
            raw = await self._client.complete(
                prompt=self._build_prompt(request, fallback),
                max_tokens=1400,
                temperature=settings.builder_temperature,
            )
            parsed = self._extract_json(raw)
            return WizardAdvisorResponse(**parsed, source="ai")
        except Exception as exc:
            fallback.source = "rules"
            fallback.summary = f"{fallback.summary} Advisor IA no disponible: {exc}"
            return fallback

    def _build_prompt(self, request: WizardAdvisorRequest, fallback: WizardAdvisorResponse) -> str:
        payload = {
            "step": request.step,
            "step_key": request.step_key,
            "final_review": request.final_review,
            "wizard_state": request.wizard_state,
            "available_tools": request.available_tools,
            "tool_readiness": request.tool_readiness,
            "available_models": request.available_models,
            "rules_baseline": fallback.model_dump(),
        }
        return f"""
Sos el asistente de diseño de Agentica. Revisás un wizard de creación de agentes IA
para asegurar objetivos alcanzables, alcance claro, tools coherentes y riesgos controlados.

Respondé únicamente JSON válido, sin markdown ni texto adicional.

Reglas:
- No inventes tools, MCPs, modelos ni capacidades que no estén en el contexto.
- Si hay acciones sensibles, recomendá confirmación humana.
- Si proponés cambios, usá proposed_patch como patch parcial de wizard_state.
- Escribí en español claro y operativo.
- score va de 0 a 100.
- status debe ser "ready", "requires_review" o "high_risk".
- severity debe ser "info", "warning" o "critical".

Schema exacto:
{{
  "score": 80,
  "status": "requires_review",
  "summary": "string",
  "suggestions": [{{"title": "string", "detail": "string", "severity": "info"}}],
  "risks": [{{"title": "string", "detail": "string", "severity": "warning"}}],
  "questions": [{{"title": "string", "detail": "string", "severity": "info"}}],
  "proposed_patch": {{}}
}}

Contexto:
{json.dumps(payload, ensure_ascii=False, default=str)}
""".strip()

    def _extract_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _rule_based_review(self, request: WizardAdvisorRequest) -> WizardAdvisorResponse:
        state = request.wizard_state
        goal = str(state.get("goal") or "").strip()
        name = str(state.get("name") or "").strip()
        description = str(state.get("description") or "").strip()
        mode = state.get("mode")
        tools = state.get("tools") or []
        constraints = [str(item) for item in state.get("constraints") or [] if str(item).strip()]
        channels = state.get("channels") or []
        rag = state.get("rag") or {}
        agents = state.get("agents") or []
        model_params = state.get("model_params") or {}

        suggestions: list[WizardAdvisorItem] = []
        risks: list[WizardAdvisorItem] = []
        questions: list[WizardAdvisorItem] = []
        proposed_patch: dict[str, Any] = {}
        score = 86

        if not name:
            score -= 6
            questions.append(WizardAdvisorItem(
                title="Falta nombre operativo",
                detail="Definí un nombre claro para ubicar el agente en dashboard, logs y API keys.",
                severity="info",
            ))

        if len(goal) < 30:
            score -= 22
            questions.append(WizardAdvisorItem(
                title="Objetivo poco específico",
                detail="El objetivo debería indicar resultado esperado, contexto y criterio de éxito.",
                severity="warning",
            ))

        broad_terms = ["todo", "cualquier", "automaticamente", "automáticamente", "conseguir clientes", "vender"]
        if any(term in goal.lower() for term in broad_terms):
            score -= 16
            risks.append(WizardAdvisorItem(
                title="Alcance amplio",
                detail="El objetivo parece demasiado abierto. Conviene acotarlo a una automatización verificable.",
                severity="warning",
            ))

        if not description and request.step >= 1:
            suggestions.append(WizardAdvisorItem(
                title="Agregar contexto",
                detail="Una descripción breve ayuda a generar mejor prompt, flujo y casos de prueba.",
                severity="info",
            ))

        selected_tool_names = {
            str(tool.get("name"))
            for tool in tools
            if isinstance(tool, dict) and tool.get("name")
        }
        sensitive_tools = {"send_email", "rest_api_call", "sql_query"}
        if selected_tool_names & sensitive_tools:
            has_approval = any("confirm" in item.lower() or "aprob" in item.lower() for item in constraints)
            if not has_approval:
                score -= 18
                risks.append(WizardAdvisorItem(
                    title="Acción sensible sin aprobación",
                    detail="Las tools con efectos externos deberían pedir confirmación humana o tener política explícita.",
                    severity="critical",
                ))
                proposed_patch["constraints"] = constraints + [
                    "Pedir confirmación humana antes de enviar mensajes, modificar datos o ejecutar acciones externas."
                ]

        readiness = {str(item.get("name")): item for item in request.tool_readiness}
        pending_tools = [
            name
            for name in selected_tool_names
            if readiness.get(name, {}).get("state") == "needs_config"
        ]
        if pending_tools:
            score -= min(20, 8 * len(pending_tools))
            risks.append(WizardAdvisorItem(
                title="Tools con configuración pendiente",
                detail=f"Antes de producción hay que resolver setup de: {', '.join(sorted(pending_tools))}.",
                severity="warning",
            ))

        if mode == "crew" and len(agents) < 2:
            score -= 18
            questions.append(WizardAdvisorItem(
                title="Equipo incompleto",
                detail="Un equipo de agentes necesita roles diferenciados para justificar CrewAI.",
                severity="warning",
            ))

        if mode == "single" and len(selected_tool_names) > 4:
            suggestions.append(WizardAdvisorItem(
                title="Evaluar modo equipo",
                detail="La cantidad de tools sugiere revisar si conviene dividir responsabilidades por roles.",
                severity="info",
            ))

        if rag.get("enabled") and not rag.get("sources"):
            suggestions.append(WizardAdvisorItem(
                title="RAG sin fuentes",
                detail="RAG está habilitado; cargá fuentes o vinculá una KB antes de esperar respuestas documentales.",
                severity="info",
            ))

        if not channels:
            score -= 8
            questions.append(WizardAdvisorItem(
                title="Canal faltante",
                detail="Seleccioná al menos un canal para orientar el diseño operativo.",
                severity="warning",
            ))

        if not model_params.get("model"):
            score -= 15
            risks.append(WizardAdvisorItem(
                title="Modelo faltante",
                detail="La Bóveda IA debe exponer un modelo para generar y ejecutar el agente.",
                severity="critical",
            ))

        if request.final_review and not constraints:
            suggestions.append(WizardAdvisorItem(
                title="Agregar restricción mínima",
                detail="Antes de generar diseño conviene declarar al menos un límite de alcance o seguridad.",
                severity="info",
            ))

        score = max(0, min(100, score))
        status = "ready"
        if score < 50 or any(item.severity == "critical" for item in risks):
            status = "high_risk"
        elif score < 80 or risks or questions:
            status = "requires_review"

        summary = {
            "ready": "El diseño se ve coherente para avanzar.",
            "requires_review": "El diseño puede avanzar, pero conviene revisar algunos puntos.",
            "high_risk": "Hay riesgos o faltantes importantes antes de generar el diseño.",
        }[status]

        return WizardAdvisorResponse(
            score=score,
            status=status,
            summary=summary,
            suggestions=suggestions,
            risks=risks,
            questions=questions,
            proposed_patch=proposed_patch,
            source="rules",
        )
