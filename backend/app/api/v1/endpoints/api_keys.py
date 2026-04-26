from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import TenantRepo
from app.core.security import CurrentContext, encrypt_provider_key
from app.db.session import PublicSessionFactory
from app.schemas.tenant import LLMProviderKeyCreate, LLMProviderKeyOut

router = APIRouter()


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class CreateKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["invoke"]
    expires_days: Optional[int] = None   # None = sin expiración


class APIKeyOut(BaseModel):
    id: str
    name: str
    key: Optional[str] = None    # Solo presente al crear — nunca más
    key_prefix: str              # Primeros 8 chars para identificar en la UI
    scopes: list[str]
    expires_at: Optional[str]
    created_at: str


@router.post("/", response_model=APIKeyOut, status_code=201)
async def create_api_key(
    body: CreateKeyRequest,
    ctx: CurrentContext,
) -> APIKeyOut:
    """
    Genera una nueva API key para el tenant.
    La key completa solo se muestra una vez — no se puede recuperar después.
    """
    ctx.require_developer()

    import uuid
    raw_key  = f"ak_{secrets.token_urlsafe(32)}"
    key_id   = str(uuid.uuid4())
    key_hash = _hash_key(raw_key)

    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_days)

    async with PublicSessionFactory() as db:
        await db.execute(
            text("""
                INSERT INTO api_keys (id, tenant_id, key_hash, name, scopes, expires_at)
                VALUES (:id, :tenant_id, :hash, :name, :scopes, :expires)
            """),
            {
                "id":        key_id,
                "tenant_id": ctx.tenant_id,
                "hash":      key_hash,
                "name":      body.name,
                "scopes":    body.scopes,
                "expires":   expires_at,
            },
        )
        await db.commit()

    return APIKeyOut(
        id=key_id,
        name=body.name,
        key=raw_key,           # única vez que se devuelve
        key_prefix=raw_key[:10],
        scopes=body.scopes,
        expires_at=expires_at.isoformat() if expires_at else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/", response_model=list[APIKeyOut])
async def list_api_keys(ctx: CurrentContext) -> list[APIKeyOut]:
    """Lista todas las API keys del tenant (sin mostrar la key completa)."""
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT id, name, key_hash, scopes, expires_at, created_at
                FROM api_keys WHERE tenant_id = :tid ORDER BY created_at DESC
            """),
            {"tid": ctx.tenant_id},
        )
        rows = result.fetchall()

    return [
        APIKeyOut(
            id=str(r.id),
            name=r.name,
            key_prefix=r.key_hash[:10],
            scopes=list(r.scopes),
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: str, ctx: CurrentContext) -> Response:
    """Revoca (elimina) una API key."""
    ctx.require_developer()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("DELETE FROM api_keys WHERE id = :id AND tenant_id = :tid RETURNING id"),
            {"id": key_id, "tid": ctx.tenant_id},
        )
        if not result.fetchone():
            raise HTTPException(404, "API key no encontrada")
        await db.commit()
    return Response(status_code=204)


async def resolve_api_key(raw_key: str) -> Optional[dict]:
    """
    Valida una API key y retorna { tenant_id, scopes } si es válida.
    Usado por el security middleware para autenticación de widgets/bots.
    """
    key_hash = _hash_key(raw_key)
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT k.tenant_id, k.scopes, k.expires_at
                FROM api_keys k
                WHERE k.key_hash = :hash
            """),
            {"hash": key_hash},
        )
        row = result.fetchone()

    if not row:
        return None
    if row.expires_at and row.expires_at <= datetime.now(timezone.utc):
        return None
    return {"tenant_id": str(row.tenant_id), "scopes": list(row.scopes)}


# ── LLM Provider Keys (Bóveda) ────────────────────────────────────────────────

@router.get("/llm", response_model=list[LLMProviderKeyOut])
async def list_llm_keys(ctx: CurrentContext) -> list[LLMProviderKeyOut]:
    """Lista las llaves de IA guardadas (ocultando la clave real)."""
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT id, provider, name, is_default, created_at, truncated_key, models
                FROM llm_provider_keys
                WHERE tenant_id = :tid ORDER BY created_at DESC
            """),
            {"tid": ctx.tenant_id},
        )
        rows = result.fetchall()

    return [
        LLMProviderKeyOut(
            id=r.id,
            provider=r.provider,
            name=r.name,
            is_default=r.is_default,
            created_at=r.created_at,
            truncated_key=r.truncated_key,
            models=list(r.models) if r.models else [],
        )
        for r in rows
    ]


@router.post("/llm", response_model=LLMProviderKeyOut, status_code=201)
async def create_llm_key(body: LLMProviderKeyCreate, ctx: CurrentContext) -> LLMProviderKeyOut:
    """Guarda una nueva credencial en la bóveda de forma cifrada."""
    ctx.require_developer()
    enc_key = encrypt_provider_key(body.raw_key)
    truncated_key = (
        f"{body.raw_key[:6]}...{body.raw_key[-4:]}"
        if len(body.raw_key) > 10
        else "********"
    )

    async with PublicSessionFactory() as db:
        # Si es la primera para este provider, la hacemos default
        res = await db.execute(
            text("SELECT 1 FROM llm_provider_keys WHERE tenant_id = :tid AND provider = :prov"),
            {"tid": ctx.tenant_id, "prov": body.provider}
        )
        is_first = res.fetchone() is None
        is_def = True if is_first else False

        result = await db.execute(
            text("""
                INSERT INTO llm_provider_keys
                    (tenant_id, provider, name, encrypted_key, truncated_key, is_default)
                VALUES
                    (:tid, :prov, :name, :enc, :truncated, :is_def)
                RETURNING id, created_at
            """),
            {
                "tid": ctx.tenant_id,
                "prov": body.provider,
                "name": body.name,
                "enc": enc_key,
                "truncated": truncated_key,
                "is_def": is_def,
            }
        )
        row = result.fetchone()
        await db.commit()

    return LLMProviderKeyOut(
        id=row.id,
        provider=body.provider,
        name=body.name,
        is_default=is_def,
        created_at=row.created_at,
        truncated_key=truncated_key,
        models=[],
    )


@router.put("/llm/{key_id}/default", status_code=200)
async def set_default_llm_key(key_id: str, provider: str, ctx: CurrentContext) -> dict:
    """Fija una llave como la predeterminada para un modelo/proveedor dado."""
    ctx.require_developer()
    async with PublicSessionFactory() as db:
        await db.execute(
            text("UPDATE llm_provider_keys SET is_default = FALSE WHERE tenant_id = :tid AND provider = :prov"),
            {"tid": ctx.tenant_id, "prov": provider}
        )
        await db.execute(
            text("UPDATE llm_provider_keys SET is_default = TRUE WHERE id = :id AND tenant_id = :tid"),
            {"id": key_id, "tid": ctx.tenant_id}
        )
        await db.commit()
    return {"status": "ok"}


class UpdateModelsRequest(BaseModel):
    models: list[str]

@router.put("/llm/{key_id}/models", status_code=200)
async def update_llm_key_models(key_id: str, body: UpdateModelsRequest, ctx: CurrentContext) -> dict:
    """Actualiza la lista de modelos disponibles para una key de la bóveda."""
    ctx.require_developer()
    import json
    async with PublicSessionFactory() as db:
        await db.execute(
            text("UPDATE llm_provider_keys SET models = CAST(:models AS jsonb) WHERE id = :id AND tenant_id = :tid"),
            {"models": json.dumps(body.models), "id": key_id, "tid": ctx.tenant_id}
        )
        await db.commit()
    return {"status": "ok", "models": body.models}


@router.delete("/llm/{key_id}", status_code=204)
async def delete_llm_key(key_id: str, ctx: CurrentContext) -> Response:
    """Elimina una credencial de la bóveda."""
    ctx.require_developer()
    async with PublicSessionFactory() as db:
        await db.execute(
            text("DELETE FROM llm_provider_keys WHERE id = :id AND tenant_id = :tid"),
            {"id": key_id, "tid": ctx.tenant_id}
        )
        await db.commit()
    return Response(status_code=204)
