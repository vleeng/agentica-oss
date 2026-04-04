from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# ── Engine global ────────────────────────────────────────────────────────────

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    echo=settings.debug,
    future=True,
)

# Session factory sin schema (para operaciones en schema public)
PublicSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ── Base declarativa ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Session factory por tenant (search_path) ────────────────────────────────

def _make_tenant_schema(tenant_id: str) -> str:
    """Convierte tenant_id (UUID con guiones) a nombre de schema PostgreSQL válido."""
    return f"tenant_{tenant_id.replace('-', '_')}"


_tenant_engines: dict[str, AsyncEngine] = {}

def get_tenant_session_factory(tenant_id: str) -> async_sessionmaker[AsyncSession]:
    """
    Crea una session factory que automáticamente hace SET search_path
    al schema del tenant antes de cada operación.
    """
    schema = _make_tenant_schema(tenant_id)

    # Reusar engine existente si ya fue creado para este tenant
    if tenant_id not in _tenant_engines:
        engine_with_schema = create_async_engine(
            settings.database_url,
            pool_size=2,
            max_overflow=5,
            echo=settings.debug,
            future=True,
            execution_options={"schema_translate_map": None},
        )

        @event.listens_for(engine_with_schema.sync_engine, "connect")
        def set_search_path(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute(f"SET search_path TO {schema}, public")
            cursor.close()

        _tenant_engines[tenant_id] = engine_with_schema

    return async_sessionmaker(
        _tenant_engines[tenant_id],
        expire_on_commit=False,
        class_=AsyncSession,
    )


# ── Provisioning de tenant ───────────────────────────────────────────────────

TENANT_TABLES_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.agents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    mode        TEXT NOT NULL CHECK (mode IN ('single', 'crew')),
    framework   TEXT NOT NULL CHECK (framework IN ('langchain', 'crewai')),
    status      TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','building','testing','deployed','archived')),
    spec_json   JSONB NOT NULL DEFAULT '{{}}',
    design_json JSONB NOT NULL DEFAULT '{{}}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.agent_builds (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','building','ready','failed')),
    code_path   TEXT,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.deployments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id       UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    build_id       UUID NOT NULL REFERENCES {schema}.agent_builds(id),
    endpoint_url   TEXT,
    ws_url         TEXT,
    container_id   TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','active','stopped','failed')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL,
    channel     TEXT NOT NULL,
    user_ref    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, agent_id)
);

CREATE TABLE IF NOT EXISTS {schema}.messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES {schema}.conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool','system')),
    content         TEXT NOT NULL,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.memory_store (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agent_id, session_id, key)
);

CREATE TABLE IF NOT EXISTS {schema}.eval_runs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    build_id    UUID REFERENCES {schema}.agent_builds(id),
    score       FLOAT NOT NULL DEFAULT 0,
    passed      BOOLEAN NOT NULL DEFAULT FALSE,
    report_json JSONB NOT NULL DEFAULT '{{}}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.billing_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID REFERENCES {schema}.agents(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES {schema}.conversations(id) ON DELETE SET NULL,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.custom_tools (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT NOT NULL,
    source_code   TEXT NOT NULL,
    config_schema JSONB NOT NULL DEFAULT '{{}}',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    test_input    TEXT NOT NULL DEFAULT '',
    last_error    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS idx_custom_tools_name
    ON {schema}.custom_tools(name);
"""


async def provision_tenant(tenant_id: str, conn: AsyncConnection) -> None:
    """
    Crea el schema y todas las tablas para un tenant nuevo.
    Se llama una sola vez al registrar el tenant.
    """
    schema = _make_tenant_schema(tenant_id)
    await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    for statement in TENANT_TABLES_DDL.format(schema=schema).split(";"):
        stmt = statement.strip()
        if stmt:
            await conn.execute(text(stmt))
    await conn.commit()


@asynccontextmanager
async def get_public_session() -> AsyncIterator[AsyncSession]:
    async with PublicSessionFactory() as session:
        yield session
