from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper para correr coroutines desde Celery (que es síncrono)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.agent_tasks.build_agent", max_retries=2)
def build_agent(self, agent_id: str, tenant_id: str, design_json: dict) -> dict:
    """
    Task de build: toma el design JSON y construye el agente en el RuntimeFactory.
    En Sprint 3 también genera los archivos para deploy.
    """
    logger.info(f"[BUILD] Iniciando build para agent_id={agent_id}")
    try:
        from app.schemas.agent import AgentDesign
        from app.runtime.factory import RuntimeFactory

        design = AgentDesign(**design_json)
        # DATABASE_URL disponible vía env — necesario para resolver LLM keys de la bóveda
        factory = RuntimeFactory()
        
        async def _do_build():
            return await factory.build(design)
            
        runtime = _run_async(_do_build())

        logger.info(f"[BUILD] Build exitoso para agent_id={agent_id}")
        return {
            "agent_id": agent_id,
            "status": "ready",
            "framework": design.framework.framework,
            "mode": design.spec.mode.value,
        }
    except Exception as exc:
        logger.error(f"[BUILD] Error: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="app.tasks.agent_tasks.eval_agent", max_retries=1)
def eval_agent(self, agent_id: str, tenant_id: str, design_json: dict) -> dict:
    """
    Task de evaluación: corre los test_cases del design contra el agente en sandbox.
    Retorna un EvalReport serializado.
    """
    logger.info(f"[EVAL] Iniciando evaluación para agent_id={agent_id}")
    try:
        return _run_async(_run_eval(agent_id, tenant_id, design_json))
    except Exception as exc:
        logger.error(f"[EVAL] Error: {exc}")
        raise self.retry(exc=exc, countdown=60)


async def _run_eval(agent_id: str, tenant_id: str, design_json: dict) -> dict:
    from app.schemas.agent import AgentDesign
    from app.runtime.factory import RuntimeFactory
    import time

    design = AgentDesign(**design_json)
    factory = RuntimeFactory()
    runtime = await factory.build(design)

    results = []
    for tc in design.test_cases[:5]:  # máximo 5 casos en eval automático
        start = time.monotonic()
        try:
            response = await runtime.invoke(
                input=tc.get("input", "test"),
                session_id=f"eval_{agent_id}_{tc.get('id', 0)}",
            )
            latency = (time.monotonic() - start) * 1000
            results.append({
                "test_id": tc.get("id"),
                "passed": bool(response.output),
                "latency_ms": latency,
                "tokens_out": response.tokens_out,
            })
        except Exception as e:
            results.append({"test_id": tc.get("id"), "passed": False, "error": str(e)})

    passed = sum(1 for r in results if r.get("passed"))
    total  = len(results) or 1
    score  = passed / total

    return {
        "agent_id": agent_id,
        "overall_score": score,
        "pass_threshold": score >= 0.75,
        "results": results,
    }


@celery_app.task(bind=True, name="app.tasks.agent_tasks.deploy_agent", max_retries=1)
def deploy_agent(self, agent_id: str, tenant_id: str, build_path: str) -> dict:
    """
    Task de deploy: construye imagen Docker y levanta el contenedor vía Traefik.
    Implementación completa en Sprint 3.
    """
    logger.info(f"[DEPLOY] Iniciando deploy para agent_id={agent_id}")
    # Sprint 3: docker build + docker run + Traefik config
    return {"agent_id": agent_id, "status": "pending_sprint3"}
