-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- búsqueda full-text

-- ── Tablas globales (schema public) ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.plans (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    max_agents  INTEGER NOT NULL DEFAULT 3,
    max_invocations_month INTEGER NOT NULL DEFAULT 1000,
    price_usd   NUMERIC(10,2) NOT NULL DEFAULT 0,
    features    JSONB NOT NULL DEFAULT '{}'
);

INSERT INTO public.plans VALUES
    ('free',       'Free',       3,    1000,  0,      '{"channels":["web_chat"]}'),
    ('starter', 'Starter', 10, 10000, 29, '{"channels":"all","rag":false,"crew":false,"white_label":false,"priority_support":false}'),
    ('pro', 'Pro', 50, 100000, 99, '{"channels":"all","rag":true,"crew":true,"white_label":false,"priority_support":true}'),
    ('business', 'Business', 100, 500000, 299, '{"channels":"all","rag":true,"crew":true,"white_label":true,"priority_support":true}'),
    ('enterprise', 'Enterprise', 999, 999999, 499, '{"channels":"all","rag":true,"crew":true,"white_label":true,"priority_support":true}')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    plan_id     TEXT NOT NULL REFERENCES public.plans(id) DEFAULT 'free',
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','deleted')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'developer'
                         CHECK (role IN ('owner','developer','viewer','agent_user')),
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    key_hash    TEXT NOT NULL UNIQUE,   -- SHA256 de la key real (nunca se guarda en claro)
    name        TEXT NOT NULL,
    scopes      TEXT[] NOT NULL DEFAULT '{"invoke"}',
    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.free_account_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_name     TEXT NOT NULL,
    slug            TEXT NOT NULL,
    owner_email     TEXT NOT NULL,
    owner_name      TEXT,
    password_hash   TEXT NOT NULL,
    requested_plan_id TEXT NOT NULL DEFAULT 'free',
    status          TEXT NOT NULL DEFAULT 'pending',
    review_notes    TEXT,
    approved_tenant_id UUID REFERENCES public.tenants(id) ON DELETE SET NULL,
    processed_by_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.llm_provider_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    name TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    truncated_key TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    models JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices globales
CREATE INDEX IF NOT EXISTS idx_llm_keys_tenant_provider
  ON public.llm_provider_keys(tenant_id, provider, is_default);
CREATE INDEX IF NOT EXISTS idx_users_tenant    ON public.users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON public.api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenants_slug    ON public.tenants(slug);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user
  ON public.password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_free_account_requests_status
  ON public.free_account_requests(status, created_at DESC);
