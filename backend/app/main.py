from __future__ import annotations

import os

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.rate_limiter import init_rate_limiter
from app.db.session import engine, Base
from app.runtime.store import init_runtime_store
from app.api.v1.endpoints import (
    auth, tenants, agents, builds, channels,
    knowledge, api_keys, usage, custom_tools,
    skills, mcp, knowledge_bases, policies, guardrails,
    system_settings,
)

settings = get_settings()
_redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client

    # Crear tablas del schema public
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migraciones incrementales (idempotentes)
        from sqlalchemy import text as _text
        await conn.execute(_text(
            "ALTER TABLE IF EXISTS public.llm_provider_keys "
            "ADD COLUMN IF NOT EXISTS models JSONB NOT NULL DEFAULT '[]'"
        ))
        await conn.execute(_text(
            "CREATE TABLE IF NOT EXISTS public.system_config ("
            "  key TEXT PRIMARY KEY,"
            "  value TEXT NOT NULL,"
            "  updated_at TIMESTAMPTZ DEFAULT NOW()"
            ")"
        ))
        await conn.execute(_text(
            "ALTER TABLE IF EXISTS public.api_keys "
            "ADD COLUMN IF NOT EXISTS agent_id UUID"
        ))
        await conn.execute(_text(
            "ALTER TABLE IF EXISTS public.api_keys "
            "ADD COLUMN IF NOT EXISTS created_by_user_id UUID"
        ))
        await conn.execute(_text(
            "CREATE INDEX IF NOT EXISTS idx_api_keys_tenant_agent "
            "ON public.api_keys (tenant_id, agent_id)"
        ))

    # Sembrar superusuario admin
    import uuid
    from sqlalchemy import text
    from app.db.session import PublicSessionFactory, provision_tenant
    from app.core.security import hash_password
    async with PublicSessionFactory() as db:
        res = await db.execute(text("SELECT id, tenant_id FROM users WHERE email = 'admin'"))
        row = res.fetchone()
        if not row:
            admin_pwd = os.getenv("ADMIN_PASSWORD")
            if not admin_pwd:
                raise RuntimeError(
                    "[STARTUP] ADMIN_PASSWORD no definida en .env — "
                    "no se puede crear el super-usuario de forma segura."
                )
            print("[STARTUP] Creando super-usuario 'admin'")
            tenant_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            await db.execute(
                text("INSERT INTO tenants (id, name, slug, plan_id) VALUES (:id, :n, :s, 'business')"),
                {"id": tenant_id, "n": "System Admin", "s": "admin"},
            )
            await db.execute(
                text("INSERT INTO users (id, tenant_id, email, full_name, password_hash, role) VALUES (:id, :t, :e, :n, :h, 'owner')"),
                {"id": user_id, "t": tenant_id, "e": "admin", "n": "Super Admin", "h": hash_password(admin_pwd)},
            )
            await db.commit()
            async with engine.begin() as conn:
                await provision_tenant(tenant_id, conn)
        else:
            # Siempre re-provisionar (CREATE TABLE IF NOT EXISTS es idempotente)
            tenant_id = str(row.tenant_id)
            print(f"[STARTUP] Verificando schema del tenant admin ({tenant_id})...")
            async with engine.begin() as conn:
                await provision_tenant(tenant_id, conn)
            print("[STARTUP] Schema del tenant admin verificado OK")

    # Conectar Redis
    try:
        _redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis_client.ping()
        print("[STARTUP] Redis conectado")
    except Exception as e:
        print(f"[WARN] Redis no disponible: {e} — usando in-memory fallback")
        _redis_client = None

    # Inicializar servicios con Redis
    init_runtime_store(redis_client=_redis_client)
    init_rate_limiter(redis_client=_redis_client)

    yield

    if _redis_client:
        await _redis_client.aclose()
    await engine.dispose()
    print("[SHUTDOWN] Conexiones cerradas")


app = FastAPI(
    title="AGENTICA API",
    description="Plataforma de construcción y despliegue automático de agentes IA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limit headers en todas las respuestas ────────────────────────────────

@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = "AGENTICA"
    return response

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["auth"])
app.include_router(tenants.router,   prefix="/api/v1/tenants",   tags=["tenants"])
app.include_router(agents.router,    prefix="/api/v1/agents",    tags=["agents"])
app.include_router(builds.router,    prefix="/api/v1/builds",    tags=["builds"])
# app.include_router(channels.router,  prefix="/api/v1/channels",  tags=["channels"]) # Sprint 5
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(api_keys.router,  prefix="/api/v1/keys",      tags=["api-keys"])
app.include_router(usage.router,        prefix="/api/v1/usage",        tags=["usage"])
app.include_router(custom_tools.router, prefix="/api/v1/tools/custom",  tags=["custom-tools"])
app.include_router(skills.router,        prefix="/api/v1",               tags=["skills"])
app.include_router(mcp.router,           prefix="/api/v1",               tags=["mcp"])
app.include_router(knowledge_bases.router, prefix="/api/v1",             tags=["knowledge-bases"])
app.include_router(policies.router,      prefix="/api/v1",               tags=["policies"])
app.include_router(guardrails.router,    prefix="/api/v1",               tags=["guardrails"])
app.include_router(system_settings.router, prefix="/api/v1",             tags=["system"])


@app.get("/health")
async def health():
    return {
        "status":  "ok",
        "version": "1.0.0",
        "redis":   _redis_client is not None,
    }
