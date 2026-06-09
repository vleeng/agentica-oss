from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import httpx

from app.core.mailer import MailerNotConfiguredError, is_mailer_configured, send_email
from app.services.model_catalog import calculate_model_cost, estimate_usage_tokens, resolve_model_pricing
from app.services.scheduler import mark_schedule_execution
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


@celery_app.task(bind=True, name="app.tasks.agent_tasks.run_scheduled_agent", max_retries=1)
def run_scheduled_agent(
    self,
    agent_id: str,
    tenant_id: str,
    design_json: dict,
    input_text: str | None = None,
) -> dict:
    logger.info("[SCHEDULED] Iniciando run programado para agent_id=%s", agent_id)
    try:
        return _run_async(_run_scheduled_agent(agent_id, tenant_id, design_json, input_text))
    except Exception as exc:
        logger.error("[SCHEDULED] Error: %s", exc)
        raise self.retry(exc=exc, countdown=120)


async def _run_scheduled_agent(agent_id: str, tenant_id: str, design_json: dict, input_text: str | None) -> dict[str, Any]:
    from app.db.repository import AgentRepository
    from app.db.session import get_tenant_session_factory
    from app.runtime.factory import RuntimeFactory
    from app.schemas.agent import AgentDesign
    import time

    design = AgentDesign.model_validate(design_json)
    schedule = design.spec.schedule
    session_id = f"scheduled_{agent_id}_{uuid4().hex[:12]}"

    try:
        runtime = await RuntimeFactory().build(design)
        scheduled_input = (input_text or "").strip()
        if not scheduled_input:
            template = (schedule.input_template or "{goal}").strip()
            scheduled_input = template.format(
                goal=design.spec.goal,
                agent_name=design.spec.name,
                description=design.spec.description,
            ).strip()
        if not scheduled_input:
            scheduled_input = design.spec.goal or design.spec.description or "Run programado de Agentica"

        progress_events: list[dict[str, Any]] = []
        runtime.set_progress_callback(lambda event: progress_events.append(dict(event)))
        started_at = time.monotonic()
        response = await runtime.invoke(scheduled_input, session_id)
        elapsed_ms = round((time.monotonic() - started_at) * 1000, 2)

        tokens_in, tokens_out = estimate_usage_tokens(
            scheduled_input,
            response.output,
            reported_tokens_in=response.tokens_in,
            reported_tokens_out=response.tokens_out,
        )
        pricing = await resolve_model_pricing(tenant_id, design.spec.model_params)
        cost = calculate_model_cost(tokens_in, tokens_out, pricing)

        async with get_tenant_session_factory(tenant_id)() as session:
            repo = AgentRepository(session)
            conv_id = await repo.upsert_conversation(agent_id, session_id, "scheduled", user_ref="scheduled")
            await repo.save_message(conv_id, "user", scheduled_input)
            await repo.save_conversation_event(
                conv_id,
                "invoke_start",
                phase="invoke",
                actor="agent",
                message="Inicio de ejecucion programada",
                payload={
                    "channel": "scheduled",
                    "session_id": session_id,
                    "agent_name": design.spec.name,
                    "execution_mode": design.spec.execution_mode.value,
                    "schedule": design.spec.schedule.model_dump(mode="json"),
                },
            )
            for event in progress_events:
                await repo.save_conversation_event(
                    conv_id,
                    "progress",
                    phase=str(event.get("phase") or ""),
                    actor=str(event.get("actor") or "") or None,
                    kind=str(event.get("kind") or "") or None,
                    message=str(event.get("message") or "") or "",
                    payload=event,
                )
            await repo.save_message(conv_id, "assistant", response.output, tokens_in, tokens_out)
            await repo.save_conversation_event(
                conv_id,
                "response_final",
                phase="completed",
                actor="assistant",
                message="Respuesta programada generada",
                payload={
                    "preview": (response.output or "")[:600],
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "elapsed_ms": elapsed_ms,
                },
            )
            await repo.record_billing_event(agent_id, conv_id, tokens_in, tokens_out, cost)

        delivery = await _deliver_scheduled_result(
            tenant_id=tenant_id,
            design=design,
            scheduled_input=scheduled_input,
            output=response.output,
        )
        await mark_schedule_execution(
            tenant_id,
            agent_id,
            status=delivery.get("status", "completed"),
            error=delivery.get("reason"),
        )

        return {
            "agent_id": agent_id,
            "session_id": session_id,
            "conversation_id": conv_id,
            "output": response.output,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed_ms": elapsed_ms,
            "delivery": delivery,
        }
    except Exception as exc:
        await mark_schedule_execution(tenant_id, agent_id, status="failed", error=str(exc))
        raise


async def _deliver_scheduled_result(*, tenant_id: str, design: Any, scheduled_input: str, output: str) -> dict[str, Any]:
    schedule = getattr(design.spec, "schedule", None)
    if not schedule or not getattr(schedule, "enabled", False):
        return {"status": "skipped", "reason": "schedule_disabled"}

    subject = (schedule.subject_template or "Resultado programado de {agent_name}").format(
        agent_name=design.spec.name,
        goal=design.spec.goal,
    )
    text_body = "\n\n".join([
        f"Agente: {design.spec.name}",
        f"Objetivo: {design.spec.goal}",
        f"Entrada programada: {scheduled_input}",
        "",
        "Resultado:",
        output,
    ])

    if schedule.delivery_mode == "email":
        if not is_mailer_configured():
            return {"status": "skipped", "reason": "mailer_not_configured"}
        recipients = [item for item in (schedule.delivery_targets or []) if str(item).strip()]
        if not recipients:
            return {"status": "skipped", "reason": "no_email_recipients"}
        delivered = []
        for recipient in recipients:
            try:
                await send_email(
                    to_email=recipient,
                    subject=subject,
                    text_body=text_body,
                )
                delivered.append(recipient)
            except MailerNotConfiguredError:
                return {"status": "skipped", "reason": "mailer_not_configured"}
        return {"status": "sent", "mode": "email", "recipients": delivered}

    webhook_url = (schedule.webhook_url or "").strip()
    if schedule.delivery_mode in {"webhook", "slack"}:
        if not webhook_url:
            return {"status": "skipped", "reason": "webhook_url_missing"}
        payload = {
            "tenant_id": tenant_id,
            "agent_name": design.spec.name,
            "agent_id": str(design.agent_id),
            "execution_mode": design.spec.execution_mode.value,
            "schedule": schedule.model_dump(mode="json"),
            "input": scheduled_input,
            "output": output,
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        return {"status": "sent", "mode": schedule.delivery_mode, "webhook_url": webhook_url}

    return {"status": "skipped", "reason": f"unsupported_delivery_mode:{schedule.delivery_mode}"}
