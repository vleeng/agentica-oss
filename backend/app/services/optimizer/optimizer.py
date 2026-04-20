from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.schemas.agent import AgentDesign
from app.schemas.eval import EvalReport
from app.services.llm_client import TextGenerationClient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class OptimizationPatch:
    """
    Conjunto de cambios recomendados al AgentDesign tras la evaluación.
    Cada campo es None si no se recomienda cambio en esa dimensión.
    """
    system_prompt:    str | None = None
    temperature:      float | None = None
    max_tokens:       int | None = None
    tools_to_add:     list[str] = field(default_factory=list)
    tools_to_remove:  list[str] = field(default_factory=list)
    reasoning:        str = ""
    confidence:       float = 0.0   # 0-1, qué tan confiado está el optimizer


class OptimizerService:
    """
    Recibe un EvalReport + el AgentDesign original y produce un OptimizationPatch.
    Usa Claude Sonnet para generar mejoras al system prompt.
    Las demás optimizaciones son determinísticas basadas en las métricas.
    """

    def __init__(self):
        self._client = TextGenerationClient()

    async def optimize(
        self,
        design: AgentDesign,
        report: EvalReport,
    ) -> tuple[AgentDesign, OptimizationPatch]:
        """
        Retorna el AgentDesign actualizado con el patch aplicado,
        más el patch mismo para registro/auditoría.
        """
        if report.pass_threshold:
            logger.info(f"[OPTIMIZER] agent_id={design.agent_id} ya pasó el umbral — sin cambios")
            return design, OptimizationPatch(
                reasoning="El agente superó el umbral de evaluación. No se requieren ajustes.",
                confidence=1.0,
            )

        patch = OptimizationPatch()
        patch.reasoning = report.notes

        # ── 1. Ajuste determinístico de parámetros ────────────────────────────

        # Temperatura: si hay hallucination alta, bajar temperatura
        if report.hallucination_score > 0.3:
            new_temp = max(0.0, design.spec.model_params.temperature - 0.15)
            patch.temperature = round(new_temp, 2)
            logger.info(f"[OPTIMIZER] Bajando temperatura a {new_temp}")

        # Max tokens: si la latencia p95 es muy alta, reducir
        if report.p95_latency_ms > 8000 and design.spec.model_params.max_tokens > 1024:
            new_max = design.spec.model_params.max_tokens - 512
            patch.max_tokens = max(512, new_max)
            logger.info(f"[OPTIMIZER] Reduciendo max_tokens a {patch.max_tokens}")

        # Tools: si task_completion es bajo y no hay tools, sugerir web_search
        if report.task_completion_rate < 0.6 and not design.spec.tools:
            patch.tools_to_add = ["web_search"]
            logger.info("[OPTIMIZER] Sugiriendo agregar web_search para mejorar completitud")

        # ── 2. Optimización del system prompt via LLM ─────────────────────────

        if report.task_completion_rate < 0.8 or report.hallucination_score > 0.2:
            patch.system_prompt = await self._optimize_system_prompt(design, report)
            patch.confidence = 0.75
        else:
            patch.confidence = 0.5

        # ── 3. Aplicar patch al design ────────────────────────────────────────

        updated_design = self._apply_patch(design, patch)

        logger.info(
            f"[OPTIMIZER] Patch generado para agent_id={design.agent_id}: "
            f"prompt={'sí' if patch.system_prompt else 'no'}, "
            f"temp={patch.temperature}, "
            f"max_tokens={patch.max_tokens}"
        )
        return updated_design, patch

    async def _optimize_system_prompt(
        self, design: AgentDesign, report: EvalReport
    ) -> str:
        prompt = f"""Mejorá el siguiente system prompt de un agente IA basándote en los problemas detectados.

SYSTEM PROMPT ACTUAL:
{design.system_prompt}

PROBLEMAS DETECTADOS:
{report.notes}

MÉTRICAS:
- Completitud de tareas: {report.task_completion_rate:.0%}
- Precisión de herramientas: {report.tool_accuracy:.0%}
- Hallucination score: {report.hallucination_score:.2f}

OBJETIVO DEL AGENTE: {design.spec.goal}
HERRAMIENTAS DISPONIBLES: {[t.name for t in design.spec.tools]}
RESTRICCIONES: {design.spec.constraints}

Generá un system prompt mejorado que:
1. Sea más específico sobre cómo usar las herramientas disponibles
2. Incluya instrucciones claras para manejar casos que no puede resolver
3. Mantenga el tono y objetivo original
4. Sea en el mismo idioma que el prompt original

Respondé SOLO con el nuevo system prompt, sin explicaciones."""

        return await self._client.complete(prompt, max_tokens=600, temperature=0.2)

    def _apply_patch(self, design: AgentDesign, patch: OptimizationPatch) -> AgentDesign:
        """Aplica el patch al design y retorna una copia actualizada."""
        updated_spec = design.spec.model_copy(deep=True)

        if patch.temperature is not None:
            updated_spec.model_params = updated_spec.model_params.model_copy(
                update={"temperature": patch.temperature}
            )
        if patch.max_tokens is not None:
            updated_spec.model_params = updated_spec.model_params.model_copy(
                update={"max_tokens": patch.max_tokens}
            )
        if patch.tools_to_add:
            from app.schemas.agent import ToolRef
            existing = {t.name for t in updated_spec.tools}
            for name in patch.tools_to_add:
                if name not in existing:
                    updated_spec.tools.append(ToolRef(name=name, source="library", config={}))

        if patch.tools_to_remove:
            updated_spec.tools = [
                t for t in updated_spec.tools if t.name not in patch.tools_to_remove
            ]

        return design.model_copy(
            update={
                "spec": updated_spec,
                "system_prompt": patch.system_prompt or design.system_prompt,
                "version": design.version + 1,
            }
        )
