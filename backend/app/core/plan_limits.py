from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import HTTPException, Request
from sqlalchemy import text

from app.db.session import PublicSessionFactory

logger = logging.getLogger(__name__)

# Definición de límites por plan — espejo de init.sql
PLAN_LIMITS = {
    "free":       {"max_agents": 3,   "max_invocations_month": 1_000,   "rag": False, "crew": False},
    "starter":    {"max_agents": 10,  "max_invocations_month": 10_000,  "rag": True,  "crew": False},
    "pro":        {"max_agents": 50,  "max_invocations_month": 100_000, "rag": True,  "crew": True},
    "business":   {"max_agents": 100, "max_invocations_month": 500_000, "rag": True,  "crew": True},
    "enterprise": {"max_agents": 999, "max_invocations_month": 999_999, "rag": True,  "crew": True},
}

DEFAULT_LIMITS = PLAN_LIMITS["free"]


async def get_tenant_plan(tenant_id: str) -> dict:
    """Retorna el plan y sus límites para un tenant."""
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("SELECT plan_id FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        )
        row = result.fetchone()
    plan_id = row.plan_id if row else "free"
    return {"plan_id": plan_id, **PLAN_LIMITS.get(plan_id, DEFAULT_LIMITS)}


async def get_tenant_usage(tenant_id: str) -> dict:
    """Retorna el uso actual del tenant en el mes en curso."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    schema = f"tenant_{tenant_id.replace('-', '_')}"

    async with PublicSessionFactory() as db:
        # Contar agentes activos
        try:
            agents_result = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.agents WHERE status != 'archived'")
            )
            agent_count = agents_result.scalar() or 0
        except Exception:
            agent_count = 0

        # Contar invocaciones del mes
        try:
            inv_result = await db.execute(
                text(f"""
                    SELECT COUNT(*) FROM {schema}.billing_events
                    WHERE created_at >= :since
                """),
                {"since": month_start},
            )
            invocations = inv_result.scalar() or 0
        except Exception:
            invocations = 0

    return {
        "agent_count":   agent_count,
        "invocations_month": invocations,
        "month_start":   month_start.isoformat(),
    }


class PlanLimitsChecker:
    """
    Verifica límites de plan antes de operaciones costosas.
    Se usa como dependency en los endpoints relevantes.
    """

    @staticmethod
    async def check_can_create_agent(tenant_id: str) -> None:
        plan  = await get_tenant_plan(tenant_id)
        usage = await get_tenant_usage(tenant_id)

        if usage["agent_count"] >= plan["max_agents"]:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"Límite de agentes alcanzado ({usage['agent_count']}/{plan['max_agents']}) "
                    f"en el plan '{plan['plan_id']}'. "
                    f"Actualizá tu plan para crear más agentes."
                ),
            )

    @staticmethod
    async def check_can_invoke(tenant_id: str) -> None:
        plan  = await get_tenant_plan(tenant_id)
        usage = await get_tenant_usage(tenant_id)

        if usage["invocations_month"] >= plan["max_invocations_month"]:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Límite de invocaciones del mes alcanzado "
                    f"({usage['invocations_month']}/{plan['max_invocations_month']}). "
                    f"Actualizá tu plan o esperá al próximo mes."
                ),
            )

    @staticmethod
    async def check_can_use_rag(tenant_id: str) -> None:
        plan = await get_tenant_plan(tenant_id)
        if not plan["rag"]:
            raise HTTPException(
                status_code=402,
                detail=f"El plan '{plan['plan_id']}' no incluye RAG. Actualizá a Starter o superior.",
            )

    @staticmethod
    async def check_can_use_crew(tenant_id: str) -> None:
        plan = await get_tenant_plan(tenant_id)
        if not plan["crew"]:
            raise HTTPException(
                status_code=402,
                detail=f"El plan '{plan['plan_id']}' no incluye equipos multi-agente. Actualizá a Pro o superior.",
            )

    @staticmethod
    async def get_usage_summary(tenant_id: str) -> dict:
        """Retorna plan + uso + porcentajes para el dashboard."""
        plan  = await get_tenant_plan(tenant_id)
        usage = await get_tenant_usage(tenant_id)
        return {
            "plan_id":           plan["plan_id"],
            "agents": {
                "used":  usage["agent_count"],
                "limit": plan["max_agents"],
                "pct":   round(usage["agent_count"] / plan["max_agents"] * 100, 1),
            },
            "invocations": {
                "used":  usage["invocations_month"],
                "limit": plan["max_invocations_month"],
                "pct":   round(usage["invocations_month"] / plan["max_invocations_month"] * 100, 1),
            },
            "features": {
                "rag":  plan["rag"],
                "crew": plan["crew"],
            },
        }


plan_checker = PlanLimitsChecker()
