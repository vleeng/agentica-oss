from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.plan_limits import list_plans
from app.core.security import CurrentContext
from app.db.session import PublicSessionFactory

router = APIRouter()

class BuilderConfig(BaseModel):
    provider: str           # e.g. "openrouter", "anthropic"
    model: str              # e.g. "openai/gpt-4o-mini"
    llm_key_id: Optional[str] = None   # vault key UUID to use
    api_key: Optional[str] = None       # raw key (only used if llm_key_id not set)

class BuilderConfigOut(BaseModel):
    provider: str
    model: str
    llm_key_id: Optional[str] = None
    configured: bool  # True if settings are in DB (not just env defaults)


class PlanOut(BaseModel):
    id: str
    name: str
    max_agents: int
    max_invocations_month: int
    price_usd: float
    features: dict


class PlanUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    max_agents: int = Field(..., ge=1)
    max_invocations_month: int = Field(..., ge=1)
    price_usd: float = Field(..., ge=0)
    features: dict


async def _require_system_admin(ctx: CurrentContext) -> None:
    ctx.require_human_user()
    ctx.require_owner()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT t.slug
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE u.id = :user_id AND t.id = :tenant_id
            """),
            {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id},
        )
        row = result.fetchone()

    if not row or row.slug != "admin":
        raise HTTPException(status_code=403, detail="Se requiere admin general del sistema")

@router.get("/system/builder", response_model=BuilderConfigOut)
async def get_builder_config(ctx: CurrentContext) -> BuilderConfigOut:
    ctx.require_owner()
    async with PublicSessionFactory() as db:
        result = await db.execute(text("SELECT key, value FROM system_config WHERE key IN ('builder_provider','builder_model','builder_llm_key_id')"))
        rows = {r.key: r.value for r in result.fetchall()}

    import os
    return BuilderConfigOut(
        provider=rows.get("builder_provider") or os.getenv("BUILDER_PROVIDER", "openrouter"),
        model=rows.get("builder_model") or os.getenv("BUILDER_MODEL", "openai/gpt-4o-mini"),
        llm_key_id=rows.get("builder_llm_key_id"),
        configured=bool(rows),
    )

@router.put("/system/builder", response_model=BuilderConfigOut)
async def set_builder_config(body: BuilderConfig, ctx: CurrentContext) -> BuilderConfigOut:
    ctx.require_owner()
    async with PublicSessionFactory() as db:
        for key, value in [
            ("builder_provider", body.provider),
            ("builder_model", body.model),
        ]:
            await db.execute(
                text("INSERT INTO system_config (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()"),
                {"k": key, "v": value}
            )
        if body.llm_key_id:
            await db.execute(
                text("INSERT INTO system_config (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()"),
                {"k": "builder_llm_key_id", "v": body.llm_key_id}
            )
        else:
            await db.execute(text("DELETE FROM system_config WHERE key = 'builder_llm_key_id'"))
        await db.commit()

    return BuilderConfigOut(
        provider=body.provider,
        model=body.model,
        llm_key_id=body.llm_key_id,
        configured=True,
    )


@router.get("/system/plans", response_model=list[PlanOut])
async def get_plans(ctx: CurrentContext) -> list[PlanOut]:
    await _require_system_admin(ctx)
    return [PlanOut(**plan) for plan in await list_plans()]


@router.put("/system/plans/{plan_id}", response_model=PlanOut)
async def update_plan(plan_id: str, body: PlanUpdate, ctx: CurrentContext) -> PlanOut:
    await _require_system_admin(ctx)
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                UPDATE plans
                SET
                    name = :name,
                    max_agents = :max_agents,
                    max_invocations_month = :max_invocations_month,
                    price_usd = :price_usd,
                    features = CAST(:features AS jsonb)
                WHERE id = :plan_id
                RETURNING id, name, max_agents, max_invocations_month, price_usd, features
            """),
            {
                "plan_id": plan_id,
                "name": body.name,
                "max_agents": body.max_agents,
                "max_invocations_month": body.max_invocations_month,
                "price_usd": body.price_usd,
                "features": json.dumps(body.features),
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        await db.commit()

    return PlanOut(
        id=row.id,
        name=row.name,
        max_agents=row.max_agents,
        max_invocations_month=row.max_invocations_month,
        price_usd=float(row.price_usd or 0),
        features=row.features or {},
    )
