from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID, uuid4

from app.runtime.factory import RuntimeFactory
from app.schemas.agent import AgentDesign
from app.schemas.eval import EvalReport, FeedbackItem

logger = logging.getLogger(__name__)

# Umbral por defecto para considerar un agente listo para producción
DEFAULT_PASS_THRESHOLD = 0.75


class EvalEngineService:
    """
    Ejecuta los test cases de un AgentDesign contra el runtime del agente
    en un entorno sandbox (sin acceso a producción).

    Métricas calculadas:
    - task_completion_rate: fracción de casos donde el agente produjo output no vacío
    - tool_accuracy: fracción de casos donde usó las tools esperadas
    - avg/p95 latency
    - estimated_cost_usd: tokens × precio estimado
    - hallucination_score: heurística basada en inconsistencias detectadas
    - overall_score: promedio ponderado de las métricas anteriores
    """

    WEIGHTS = {
        "task_completion": 0.40,
        "tool_accuracy":   0.25,
        "latency":         0.15,   # penaliza si p95 > 5s
        "cost":            0.10,   # penaliza si cost_per_call > $0.05
        "hallucination":   0.10,   # penaliza si score > 0.3
    }

    # Precio estimado por token (USD) — aproximado Sonnet
    COST_PER_TOKEN_IN  = 3e-6
    COST_PER_TOKEN_OUT = 15e-6

    def __init__(self, redis_client=None, session_factory=None):
        self._redis = redis_client
        self._session_factory = session_factory

    async def run(
        self,
        design: AgentDesign,
        human_feedback: list[FeedbackItem] | None = None,
        max_cases: int = 5,
    ) -> EvalReport:
        run_id = uuid4()
        factory = RuntimeFactory(
            redis_client=self._redis,
            session_factory=self._session_factory,
        )
        runtime = await factory.build(design)

        test_cases = design.test_cases[:max_cases]
        if not test_cases:
            logger.warning(f"[EVAL] Sin test cases para agent_id={design.agent_id}")
            return self._empty_report(design.agent_id, run_id)

        results = await asyncio.gather(
            *[self._run_single_case(runtime, tc, str(design.agent_id)) for tc in test_cases],
            return_exceptions=True,
        )

        case_results = [r for r in results if isinstance(r, dict)]
        errors       = [r for r in results if isinstance(r, Exception)]
        if errors:
            logger.warning(f"[EVAL] {len(errors)} casos fallaron con excepción")

        report = self._compute_report(
            agent_id=design.agent_id,
            run_id=run_id,
            case_results=case_results,
            human_feedback=human_feedback or [],
        )
        logger.info(
            f"[EVAL] agent_id={design.agent_id} "
            f"score={report.overall_score:.2f} passed={report.pass_threshold}"
        )
        return report

    # ── Ejecución de un caso individual ──────────────────────────────────────

    async def _run_single_case(
        self, runtime, test_case: dict, agent_id: str
    ) -> dict:
        session_id = f"eval_{agent_id}_{test_case.get('id', 0)}"
        start = time.monotonic()
        error = None
        output = ""
        tokens_in = 0
        tokens_out = 0

        try:
            response = await asyncio.wait_for(
                runtime.invoke(test_case["input"], session_id),
                timeout=60.0,
            )
            output = response.output
            tokens_in  = response.tokens_in
            tokens_out = response.tokens_out
        except asyncio.TimeoutError:
            error = "timeout"
        except Exception as e:
            error = str(e)

        latency_ms = (time.monotonic() - start) * 1000

        # Evaluar si usó las tools esperadas (heurística: buscar nombres en el output)
        expected_tools: list[str] = test_case.get("expected_tools", [])
        tool_hit = 0
        if expected_tools:
            for tool in expected_tools:
                if tool.lower() in output.lower():
                    tool_hit += 1
            tool_accuracy = tool_hit / len(expected_tools)
        else:
            tool_accuracy = 1.0  # no se esperaban tools → no penalizar

        # Heurística de hallucination: respuestas muy cortas o genéricas
        hallucination = self._estimate_hallucination(output, test_case)

        return {
            "test_id":       test_case.get("id"),
            "input":         test_case["input"],
            "output":        output,
            "completed":     bool(output) and not error,
            "tool_accuracy": tool_accuracy,
            "latency_ms":    latency_ms,
            "tokens_in":     tokens_in,
            "tokens_out":    tokens_out,
            "hallucination": hallucination,
            "error":         error,
        }

    # ── Cálculo del reporte ───────────────────────────────────────────────────

    def _compute_report(
        self,
        agent_id: UUID,
        run_id: UUID,
        case_results: list[dict],
        human_feedback: list[FeedbackItem],
    ) -> EvalReport:
        if not case_results:
            return self._empty_report(agent_id, run_id)

        n = len(case_results)

        task_completion = sum(1 for r in case_results if r["completed"]) / n
        tool_accuracy   = sum(r["tool_accuracy"] for r in case_results) / n
        latencies       = sorted(r["latency_ms"] for r in case_results)
        avg_latency     = sum(latencies) / n
        p95_latency     = latencies[int(n * 0.95)] if n > 1 else latencies[-1]

        total_tokens_in  = sum(r["tokens_in"]  for r in case_results)
        total_tokens_out = sum(r["tokens_out"] for r in case_results)
        cost_usd = (
            total_tokens_in  * self.COST_PER_TOKEN_IN +
            total_tokens_out * self.COST_PER_TOKEN_OUT
        )
        cost_per_call = cost_usd / n

        hallucination = sum(r["hallucination"] for r in case_results) / n

        # Scores normalizados 0-1 para cada dimensión
        latency_score     = max(0.0, 1.0 - (p95_latency / 10000))  # 10s = score 0
        cost_score        = max(0.0, 1.0 - (cost_per_call / 0.10)) # $0.10 = score 0
        hallucination_inv = max(0.0, 1.0 - hallucination)

        overall = (
            task_completion   * self.WEIGHTS["task_completion"] +
            tool_accuracy     * self.WEIGHTS["tool_accuracy"]   +
            latency_score     * self.WEIGHTS["latency"]         +
            cost_score        * self.WEIGHTS["cost"]            +
            hallucination_inv * self.WEIGHTS["hallucination"]
        )

        # Ajuste por feedback humano (si existe)
        if human_feedback:
            avg_human = sum(f.rating for f in human_feedback) / len(human_feedback) / 5.0
            overall = overall * 0.7 + avg_human * 0.3

        overall = round(min(1.0, max(0.0, overall)), 4)

        return EvalReport(
            agent_id=agent_id,
            run_id=run_id,
            task_completion_rate=round(task_completion, 4),
            tool_accuracy=round(tool_accuracy, 4),
            avg_latency_ms=round(avg_latency, 1),
            p95_latency_ms=round(p95_latency, 1),
            estimated_cost_usd=round(cost_usd, 6),
            hallucination_score=round(hallucination, 4),
            human_feedback=human_feedback,
            overall_score=overall,
            pass_threshold=overall >= DEFAULT_PASS_THRESHOLD,
            notes=self._generate_notes(task_completion, tool_accuracy, p95_latency, hallucination),
        )

    def _estimate_hallucination(self, output: str, test_case: dict) -> float:
        """
        Heurística simple de detección de hallucination.
        En Sprint 4 se reemplaza por un LLM judge.
        """
        if not output:
            return 1.0
        output_lower = output.lower()

        penalties = 0.0
        # Respuesta genérica sin contenido específico
        generic_phrases = ["no lo sé", "no tengo información", "como ia", "como modelo de lenguaje"]
        if any(p in output_lower for p in generic_phrases):
            penalties += 0.3
        # Respuesta excesivamente corta para una pregunta compleja
        if len(output) < 50 and len(test_case.get("input", "")) > 30:
            penalties += 0.2
        # Contradicción interna: menciona "no" y "sí" para la misma pregunta
        if "no " in output_lower and "sí " in output_lower and len(output) < 200:
            penalties += 0.1

        return min(1.0, penalties)

    def _generate_notes(
        self,
        completion: float,
        tool_acc: float,
        p95: float,
        hallucination: float,
    ) -> str:
        issues = []
        if completion < 0.8:
            issues.append(f"Tasa de completitud baja ({completion:.0%}) — revisar el system prompt")
        if tool_acc < 0.7:
            issues.append(f"Precisión de tools baja ({tool_acc:.0%}) — verificar nombres y descripciones")
        if p95 > 8000:
            issues.append(f"Latencia p95 elevada ({p95:.0f}ms) — considerar reducir max_tokens o simplificar el grafo")
        if hallucination > 0.3:
            issues.append(f"Score de hallucination elevado ({hallucination:.2f}) — ajustar temperatura o agregar contexto")
        return " | ".join(issues) if issues else "Agente listo para producción."

    def _empty_report(self, agent_id: UUID, run_id: UUID) -> EvalReport:
        return EvalReport(
            agent_id=agent_id, run_id=run_id,
            task_completion_rate=0, tool_accuracy=0,
            avg_latency_ms=0, p95_latency_ms=0,
            estimated_cost_usd=0, hallucination_score=0,
            overall_score=0, pass_threshold=False,
            notes="Sin test cases disponibles.",
        )
