from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text

from app.core.product_profile import get_product_profile_state
from app.db.session import PublicSessionFactory

logger = logging.getLogger(__name__)

# Seed inicial y fallback si la tabla public.plans estuviera vacía.
PLAN_DEFAULTS = {
    "free": {
        "name": "Free",
        "max_agents": 3,
        "max_invocations_month": 1_000,
        "price_usd": 0,
        "features": {"rag": False, "crew": False},
    },
    "starter": {
        "name": "Starter",
        "max_agents": 10,
        "max_invocations_month": 10_000,
        "price_usd": 29,
        "features": {"rag": True, "crew": False},
    },
    "pro": {
        "name": "Pro",
        "max_agents": 50,
        "max_invocations_month": 100_000,
        "price_usd": 99,
        "features": {"rag": True, "crew": True},
    },
    "business": {
        "name": "Business",
        "max_agents": 100,
        "max_invocations_month": 500_000,
        "price_usd": 299,
        "features": {"rag": True, "crew": True},
    },
    "enterprise": {
        "name": "Enterprise",
        "max_agents": 999,
        "max_invocations_month": 999_999,
        "price_usd": 999,
        "features": {"rag": True, "crew": True},
    },
}

DEFAULT_LIMITS = PLAN_DEFAULTS["free"]


async def seed_default_plans() -> None:
    async with PublicSessionFactory() as db:
        for plan_id, plan in PLAN_DEFAULTS.items():
            await db.execute(
                text("""
                    INSERT INTO plans (id, name, max_agents, max_invocations_month, price_usd, features)
                    VALUES (:id, :name, :max_agents, :max_invocations_month, :price_usd, CAST(:features AS jsonb))
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        max_agents = EXCLUDED.max_agents,
                        max_invocations_month = EXCLUDED.max_invocations_month,
                        price_usd = EXCLUDED.price_usd,
                        features = EXCLUDED.features
                """),
                {
                    "id": plan_id,
                    "name": plan["name"],
                    "max_agents": plan["max_agents"],
                    "max_invocations_month": plan["max_invocations_month"],
                    "price_usd": plan["price_usd"],
                    "features": json.dumps(plan["features"]),
                },
            )
        await db.commit()


async def list_plans() -> list[dict]:
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT id, name, max_agents, max_invocations_month, price_usd, features
                FROM plans
                ORDER BY
                    CASE id
                        WHEN 'free' THEN 1
                        WHEN 'starter' THEN 2
                        WHEN 'pro' THEN 3
                        WHEN 'business' THEN 4
                        WHEN 'enterprise' THEN 5
                        ELSE 99
                    END
            """)
        )
        rows = result.fetchall()

    if rows:
        return [
            {
                "id": row.id,
                "name": row.name,
                "max_agents": row.max_agents,
                "max_invocations_month": row.max_invocations_month,
                "price_usd": float(row.price_usd or 0),
                "features": row.features or {},
            }
            for row in rows
        ]

    return [{"id": plan_id, **plan} for plan_id, plan in PLAN_DEFAULTS.items()]


async def get_tenant_plan(tenant_id: str) -> dict:
    """Retorna el plan y sus límites para un tenant."""
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT
                    t.plan_id,
                    p.name,
                    p.max_agents,
                    p.max_invocations_month,
                    p.price_usd,
                    p.features
                FROM tenants t
                LEFT JOIN plans p ON p.id = t.plan_id
                WHERE t.id = :id
            """),
            {"id": tenant_id},
        )
        row = result.fetchone()

    plan_id = row.plan_id if row else "free"
    if row and row.max_agents is not None:
        features = row.features or {}
        return {
            "plan_id": plan_id,
            "name": row.name or plan_id.capitalize(),
            "max_agents": row.max_agents,
            "max_invocations_month": row.max_invocations_month,
            "price_usd": float(row.price_usd or 0),
            "rag": bool(features.get("rag")),
            "crew": bool(features.get("crew")),
            "features": features,
        }

    fallback = PLAN_DEFAULTS.get(plan_id, DEFAULT_LIMITS)
    return {
        "plan_id": plan_id,
        "name": fallback["name"],
        "max_agents": fallback["max_agents"],
        "max_invocations_month": fallback["max_invocations_month"],
        "price_usd": fallback["price_usd"],
        "rag": bool(fallback["features"].get("rag")),
        "crew": bool(fallback["features"].get("crew")),
        "features": fallback["features"],
    }


async def get_tenant_usage(tenant_id: str) -> dict:
    """Retorna el uso actual del tenant en el mes en curso."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    schema = f"tenant_{tenant_id.replace('-', '_')}"

    async with PublicSessionFactory() as db:
        try:
            agents_result = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.agents WHERE status != 'archived'")
            )
            agent_count = agents_result.scalar() or 0
        except Exception:
            agent_count = 0

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
        "agent_count": agent_count,
        "invocations_month": invocations,
        "month_start": month_start.isoformat(),
    }


class PlanLimitsChecker:
    @staticmethod
    async def check_can_create_agent(tenant_id: str) -> None:
        if not get_product_profile_state().features.usage_limits:
            return
        plan = await get_tenant_plan(tenant_id)
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
        if not get_product_profile_state().features.usage_limits:
            return
        plan = await get_tenant_plan(tenant_id)
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
        if not get_product_profile_state().features.usage_limits:
            return
        plan = await get_tenant_plan(tenant_id)
        if not plan["rag"]:
            raise HTTPException(
                status_code=402,
                detail=f"El plan '{plan['plan_id']}' no incluye RAG. Actualizá a Starter o superior.",
            )

    @staticmethod
    async def check_can_use_crew(tenant_id: str) -> None:
        if not get_product_profile_state().features.usage_limits:
            return
        plan = await get_tenant_plan(tenant_id)
        if not plan["crew"]:
            raise HTTPException(
                status_code=402,
                detail=f"El plan '{plan['plan_id']}' no incluye equipos multi-agente. Actualizá a Pro o superior.",
            )

    @staticmethod
    async def get_usage_summary(tenant_id: str) -> dict:
        if not get_product_profile_state().features.usage_limits:
            usage = await get_tenant_usage(tenant_id)
            return {
                "plan_id": "unlimited",
                "agents": {
                    "used": usage["agent_count"],
                    "limit": 0,
                    "pct": 0,
                },
                "invocations": {
                    "used": usage["invocations_month"],
                    "limit": 0,
                    "pct": 0,
                },
                "features": {
                    "rag": True,
                    "crew": True,
                },
            }
        plan = await get_tenant_plan(tenant_id)
        usage = await get_tenant_usage(tenant_id)
        return {
            "plan_id": plan["plan_id"],
            "agents": {
                "used": usage["agent_count"],
                "limit": plan["max_agents"],
                "pct": round(usage["agent_count"] / plan["max_agents"] * 100, 1),
            },
            "invocations": {
                "used": usage["invocations_month"],
                "limit": plan["max_invocations_month"],
                "pct": round(usage["invocations_month"] / plan["max_invocations_month"] * 100, 1),
            },
            "features": {
                "rag": plan["rag"],
                "crew": plan["crew"],
            },
        }


plan_checker = PlanLimitsChecker()
