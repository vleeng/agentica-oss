from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from croniter import croniter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.repository import AgentRepository
from app.db.session import PublicSessionFactory, get_tenant_session_factory
from app.tasks.agent_tasks import run_scheduled_agent

logger = logging.getLogger(__name__)
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("America/Buenos_Aires")


def _next_run_at(cron_expression: str, tz_name: str, *, from_dt: datetime | None = None) -> datetime | None:
    expr = (cron_expression or "").strip()
    if not expr:
        return None
    base = from_dt or _utcnow()
    zone = _parse_zone(tz_name or "America/Buenos_Aires")
    base_local = base.astimezone(zone)
    try:
        next_local = croniter(expr, base_local).get_next(datetime)
    except Exception as exc:
        logger.warning("[Scheduler] cron invalido '%s': %s", expr, exc)
        return None
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=zone)
    return next_local.astimezone(timezone.utc)


async def sync_agent_schedule_state(tenant_id: str, agent_id: str, design: Any) -> None:
    schedule = getattr(getattr(design, "spec", None), "schedule", None)
    enabled = bool(schedule and getattr(schedule, "enabled", False) and getattr(design.spec, "execution_mode", None) and design.spec.execution_mode.value == "scheduled")
    cron_expression = getattr(schedule, "cron_expression", "0 9 * * *") or "0 9 * * *"
    timezone_name = getattr(schedule, "timezone", "America/Buenos_Aires") or "America/Buenos_Aires"
    delivery_mode = getattr(schedule, "delivery_mode", "email")
    delivery_targets = list(getattr(schedule, "delivery_targets", []) or [])
    webhook_url = getattr(schedule, "webhook_url", None)
    subject_template = getattr(schedule, "subject_template", "Resultado programado de {agent_name}") or "Resultado programado de {agent_name}"
    input_template = getattr(schedule, "input_template", "{goal}") or "{goal}"
    next_run_at = _next_run_at(cron_expression, timezone_name) if enabled else None

    async with PublicSessionFactory() as db:
        await db.execute(
            text("""
                INSERT INTO public.agent_schedule_states (
                    agent_id, tenant_id, enabled, cron_expression, timezone,
                    delivery_mode, delivery_targets, webhook_url, subject_template,
                    input_template, next_run_at, updated_at
                )
                VALUES (
                    CAST(:agent_id AS uuid), CAST(:tenant_id AS uuid), :enabled, :cron_expression, :timezone,
                    :delivery_mode, CAST(:delivery_targets AS text[]), :webhook_url, :subject_template,
                    :input_template, :next_run_at, NOW()
                )
                ON CONFLICT (agent_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    enabled = EXCLUDED.enabled,
                    cron_expression = EXCLUDED.cron_expression,
                    timezone = EXCLUDED.timezone,
                    delivery_mode = EXCLUDED.delivery_mode,
                    delivery_targets = EXCLUDED.delivery_targets,
                    webhook_url = EXCLUDED.webhook_url,
                    subject_template = EXCLUDED.subject_template,
                    input_template = EXCLUDED.input_template,
                    next_run_at = EXCLUDED.next_run_at,
                    updated_at = NOW()
            """),
            {
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "enabled": enabled,
                "cron_expression": cron_expression,
                "timezone": timezone_name,
                "delivery_mode": getattr(delivery_mode, "value", delivery_mode),
                "delivery_targets": delivery_targets,
                "webhook_url": webhook_url,
                "subject_template": subject_template,
                "input_template": input_template,
                "next_run_at": next_run_at,
            },
        )
        await db.commit()


async def mark_schedule_execution(
    tenant_id: str,
    agent_id: str,
    *,
    status: str,
    error: str | None = None,
) -> None:
    async with PublicSessionFactory() as db:
        await db.execute(
            text("""
                UPDATE public.agent_schedule_states
                SET last_run_at = NOW(),
                    last_status = :status,
                    last_error = :error,
                    updated_at = NOW()
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND agent_id = CAST(:agent_id AS uuid)
            """),
            {"tenant_id": tenant_id, "agent_id": agent_id, "status": status, "error": error},
        )
        await db.commit()


async def _load_due_schedule_rows(limit: int) -> list[dict[str, Any]]:
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT agent_id, tenant_id, enabled, cron_expression, timezone,
                       delivery_mode, delivery_targets, webhook_url,
                       subject_template, input_template, next_run_at
                FROM public.agent_schedule_states
                WHERE enabled = TRUE
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= NOW()
                ORDER BY next_run_at ASC
                LIMIT :limit
            """),
            {"limit": limit},
        )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


async def _advance_next_run(agent_id: str, tenant_id: str, cron_expression: str, tz_name: str) -> None:
    next_run_at = _next_run_at(cron_expression, tz_name)
    async with PublicSessionFactory() as db:
        await db.execute(
            text("""
                UPDATE public.agent_schedule_states
                SET next_run_at = :next_run_at,
                    updated_at = NOW()
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND agent_id = CAST(:agent_id AS uuid)
            """),
            {"tenant_id": tenant_id, "agent_id": agent_id, "next_run_at": next_run_at},
        )
        await db.commit()


async def tick_scheduled_agents(limit: int | None = None) -> int:
    batch_limit = limit or settings.scheduled_batch_size
    due_rows = await _load_due_schedule_rows(batch_limit)
    launched = 0

    for row in due_rows:
        agent_id = str(row["agent_id"])
        tenant_id = str(row["tenant_id"])
        cron_expression = str(row["cron_expression"] or "0 9 * * *")
        timezone_name = str(row["timezone"] or "America/Buenos_Aires")

        try:
            await _advance_next_run(agent_id, tenant_id, cron_expression, timezone_name)
            async with get_tenant_session_factory(tenant_id)() as session:
                repo = AgentRepository(session)
                agent = await repo.get_agent(agent_id)
            if not agent:
                logger.warning("[Scheduler] agent not found agent_id=%s tenant_id=%s", agent_id, tenant_id)
                await mark_schedule_execution(tenant_id, agent_id, status="failed", error="agent_not_found")
                continue

            run_scheduled_agent.delay(
                agent_id,
                tenant_id,
                agent["design"],
                None,
            )
            launched += 1
            logger.info("[Scheduler] launched scheduled run agent_id=%s tenant_id=%s", agent_id, tenant_id)
        except Exception as exc:
            logger.exception("[Scheduler] failed to launch scheduled run agent_id=%s tenant_id=%s", agent_id, tenant_id)
            await mark_schedule_execution(tenant_id, agent_id, status="failed", error=str(exc))

    return launched


class ScheduledAgentScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="scheduled-agent-scheduler")
        logger.info("[Scheduler] started poll=%ss batch=%s", settings.scheduled_poll_seconds, settings.scheduled_batch_size)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                launched = await tick_scheduled_agents()
                logger.debug("[Scheduler] tick done launched=%s", launched)
            except Exception as exc:
                logger.exception("[Scheduler] tick error: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.scheduled_poll_seconds)
            except asyncio.TimeoutError:
                continue


scheduled_agent_scheduler = ScheduledAgentScheduler()
