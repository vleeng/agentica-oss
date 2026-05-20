from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
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
_verified_tenants: set[str] = set()

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
            connect_args={"server_settings": {"search_path": f"{schema},public"}},
        )

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

CREATE TABLE IF NOT EXISTS {schema}.conversation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES {schema}.conversations(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    phase           TEXT,
    actor           TEXT,
    kind            TEXT,
    message         TEXT NOT NULL DEFAULT '',
    payload_json    JSONB NOT NULL DEFAULT '{{}}',
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

CREATE TABLE IF NOT EXISTS {schema}.skills (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    description      TEXT,
    objective        TEXT NOT NULL,
    usage_conditions TEXT,
    tools_json       JSONB NOT NULL DEFAULT '[]',
    procedure        TEXT NOT NULL,
    quality_rules    TEXT,
    output_format    TEXT,
    guardrails_json  JSONB NOT NULL DEFAULT '[]',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS {schema}.mcp_servers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  TEXT NOT NULL,
    endpoint              TEXT NOT NULL,
    transport             TEXT NOT NULL DEFAULT 'sse',
    auth_type             TEXT NOT NULL DEFAULT 'none',
    auth_config_json      JSONB NOT NULL DEFAULT '{{}}',
    discovered_tools_json JSONB NOT NULL DEFAULT '[]',
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    last_tested_at        TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS {schema}.knowledge_bases (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT,
    access_mode   TEXT NOT NULL DEFAULT 'restricted',
    rag_spec_json JSONB NOT NULL DEFAULT '{{}}',
    status        TEXT NOT NULL DEFAULT 'empty',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name)
);

ALTER TABLE IF EXISTS {schema}.knowledge_bases
ADD COLUMN IF NOT EXISTS access_mode TEXT NOT NULL DEFAULT 'restricted';

CREATE TABLE IF NOT EXISTS {schema}.agent_skills (
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    skill_id    UUID NOT NULL REFERENCES {schema}.skills(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, skill_id)
);

CREATE TABLE IF NOT EXISTS {schema}.agent_mcp_servers (
    agent_id      UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    mcp_server_id UUID NOT NULL REFERENCES {schema}.mcp_servers(id) ON DELETE CASCADE,
    assigned_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, mcp_server_id)
);

CREATE TABLE IF NOT EXISTS {schema}.agent_knowledge_bases (
    agent_id    UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    kb_id       UUID NOT NULL REFERENCES {schema}.knowledge_bases(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, kb_id)
);

CREATE TABLE IF NOT EXISTS {schema}.behavior_policies (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                   UUID NOT NULL UNIQUE REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    tone                       TEXT NOT NULL DEFAULT 'profesional',
    escalation_conditions_json JSONB NOT NULL DEFAULT '[]',
    confirmation_triggers_json JSONB NOT NULL DEFAULT '[]',
    format_requirements        TEXT,
    custom_rules_json          JSONB NOT NULL DEFAULT '[]',
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.guardrail_rules (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id       UUID NOT NULL REFERENCES {schema}.agents(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    rule_type      TEXT NOT NULL,
    condition_json JSONB NOT NULL DEFAULT '{{}}',
    action         TEXT NOT NULL DEFAULT 'block',
    priority       INTEGER NOT NULL DEFAULT 0,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_skills_agent    ON {schema}.agent_skills(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_mcp_agent       ON {schema}.agent_mcp_servers(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_kb_agent        ON {schema}.agent_knowledge_bases(agent_id);
CREATE INDEX IF NOT EXISTS idx_conversation_events_conversation ON {schema}.conversation_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_guardrails_agent      ON {schema}.guardrail_rules(agent_id);
CREATE INDEX IF NOT EXISTS idx_behavior_policy_agent ON {schema}.behavior_policies(agent_id);
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
    _verified_tenants.add(tenant_id)


async def ensure_tenant_schema(tenant_id: str) -> None:
    if tenant_id in _verified_tenants:
        return
    async with engine.begin() as conn:
        await provision_tenant(tenant_id, conn)


@asynccontextmanager
async def get_public_session() -> AsyncIterator[AsyncSession]:
    async with PublicSessionFactory() as session:
        yield session
