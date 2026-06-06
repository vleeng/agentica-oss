from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import TenantRepo
from app.core.plan_limits import plan_checker
from app.core.product_profile import get_product_profile_state
from app.core.rate_limiter import get_rate_limiter
from app.core.security import CurrentContext

router = APIRouter()


def _ensure_billing_enabled() -> None:
    if not get_product_profile_state().features.billing:
        raise HTTPException(status_code=404, detail="Observabilidad comercial no disponible en este perfil.")


@router.get("/summary")
async def get_usage_summary(ctx: CurrentContext) -> dict:
    """Plan, límites y uso actual del tenant — para el dashboard."""
    ctx.require_human_user()
    _ensure_billing_enabled()
    return await plan_checker.get_usage_summary(ctx.tenant_id)


@router.get("/billing")
async def get_billing_detail(
    ctx: CurrentContext,
    repo: TenantRepo,
    days: int = 30,
) -> dict:
    """Detalle de billing de los últimos N días."""
    ctx.require_human_user()
    _ensure_billing_enabled()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await repo._db.execute(
        text("""
            SELECT
                DATE_TRUNC('day', created_at) AS day,
                COUNT(*) AS calls,
                SUM(tokens_in)   AS tokens_in,
                SUM(tokens_out)  AS tokens_out,
                SUM(cost_usd)    AS cost_usd
            FROM billing_events
            WHERE created_at >= :since
            GROUP BY 1
            ORDER BY 1 DESC
        """),
        {"since": since},
    )
    rows = result.fetchall()
    daily = [
        {
            "day":       r.day.strftime("%Y-%m-%d"),
            "calls":     r.calls,
            "tokens_in": r.tokens_in,
            "tokens_out":r.tokens_out,
            "cost_usd":  float(r.cost_usd),
        }
        for r in rows
    ]

    total_cost = sum(d["cost_usd"] for d in daily)
    total_calls = sum(d["calls"] for d in daily)

    return {
        "period_days":  days,
        "total_calls":  total_calls,
        "total_cost_usd": round(total_cost, 6),
        "daily":        daily,
    }


@router.get("/agents")
async def get_agents_usage(
    ctx: CurrentContext,
    repo: TenantRepo,
) -> list[dict]:
    """Uso por agente — invocaciones y costo."""
    ctx.require_human_user()
    _ensure_billing_enabled()
    result = await repo._db.execute(
        text("""
            SELECT
                a.id,
                a.name,
                a.status,
                a.framework,
                COALESCE(b.calls, 0)     AS calls,
                COALESCE(b.cost_usd, 0)  AS cost_usd
            FROM agents a
            LEFT JOIN (
                SELECT agent_id, COUNT(*) AS calls, SUM(cost_usd) AS cost_usd
                FROM billing_events
                GROUP BY agent_id
            ) b ON b.agent_id = a.id
            ORDER BY calls DESC
        """),
    )
    return [
        {
            "agent_id": str(r.id),
            "name":     r.name,
            "status":   r.status,
            "framework":r.framework,
            "calls":    r.calls,
            "cost_usd": float(r.cost_usd),
        }
        for r in result.fetchall()
    ]


@router.get("/rate-limits")
async def get_rate_limit_status(ctx: CurrentContext) -> dict:
    """Estado actual de los rate limits del tenant."""
    ctx.require_human_user()
    _ensure_billing_enabled()
    rl = get_rate_limiter()
    scopes = ["invoke", "build", "spec", "eval", "global"]
    status = {}
    for scope in scopes:
        status[scope] = await rl.get_status(ctx.tenant_id, scope)
    return {"tenant_id": ctx.tenant_id, "limits": status}
