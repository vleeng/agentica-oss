from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional
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
