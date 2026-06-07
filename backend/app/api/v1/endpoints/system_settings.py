from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.core.mailer import send_email
from app.core.mailer import is_mailer_configured
from app.core.plan_limits import get_tenant_plan, get_tenant_usage, list_plans
from app.core.product_profile import get_product_profile_state
from app.core.security import CurrentContext
from app.db.session import PublicSessionFactory, engine, provision_tenant

router = APIRouter()
logger = logging.getLogger(__name__)

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


class FreeRequestDecision(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


class FreeRequestApprove(BaseModel):
    notes: str | None = Field(default=None, max_length=500)
    plan_id: str | None = Field(default=None, max_length=50)


class FreeRequestOut(BaseModel):
    id: str
    tenant_name: str
    slug: str
    owner_email: str
    owner_name: str | None = None
    company_sector: str | None = None
    job_title: str | None = None
    requested_plan_id: str
    status: str
    review_notes: str | None = None
    approved_tenant_id: str | None = None
    processed_by_user_id: str | None = None
    processed_at: str | None = None
    created_at: str


class TenantOverviewUserOut(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str
    status: str
    created_at: str


class TenantOverviewOut(BaseModel):
    tenant_id: str
    name: str
    slug: str
    plan_id: str
    created_at: str
    owner_email: str | None = None
    owner_name: str | None = None
    user_count: int
    developer_count: int
    viewer_count: int
    agents_used: int
    agents_limit: int
    invocations_used: int
    invocations_limit: int
    users: list[TenantOverviewUserOut]


class ToolReadinessOut(BaseModel):
    name: str
    configured: bool
    state: str
    state_label: str
    setup_hint: str | None = None


class ProductFeaturesOut(BaseModel):
    billing: bool
    plans: bool
    usage_limits: bool
    signup: bool
    enterprise_auth: bool
    white_label: bool
    community_theme: bool


class ProductProfileOut(BaseModel):
    profile: str
    display_name: str
    features: ProductFeaturesOut


@router.get("/system/profile/public", response_model=ProductProfileOut)
async def get_public_product_profile() -> ProductProfileOut:
    state = get_product_profile_state()
    return ProductProfileOut(
        profile=state.profile,
        display_name=state.display_name,
        features=ProductFeaturesOut(**state.features.to_dict()),
    )


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


def _ensure_plans_enabled() -> None:
    if not get_product_profile_state().features.plans:
        raise HTTPException(status_code=404, detail="La gestion de planes no esta disponible en este perfil.")


def _ensure_signup_enabled() -> None:
    if not get_product_profile_state().features.signup:
        raise HTTPException(status_code=404, detail="Las solicitudes publicas no estan disponibles en este perfil.")


def _map_free_request(row) -> FreeRequestOut:
    return FreeRequestOut(
        id=str(row.id),
        tenant_name=row.tenant_name,
        slug=row.slug,
        owner_email=row.owner_email,
        owner_name=row.owner_name,
        company_sector=getattr(row, "company_sector", None),
        job_title=getattr(row, "job_title", None),
        requested_plan_id=row.requested_plan_id,
        status=row.status,
        review_notes=row.review_notes,
        approved_tenant_id=str(row.approved_tenant_id) if row.approved_tenant_id else None,
        processed_by_user_id=str(row.processed_by_user_id) if row.processed_by_user_id else None,
        processed_at=row.processed_at.isoformat() if row.processed_at else None,
        created_at=row.created_at.isoformat(),
    )


async def _send_free_request_approval_email(owner_email: str, owner_name: str | None, tenant_name: str, plan_id: str) -> None:
    greeting = owner_name or owner_email
    await send_email(
        to_email=owner_email,
        subject="Tu cuenta de Agentica fue aprobada",
        text_body=(
            f"Hola {greeting},\n\n"
            f"Tu solicitud para {tenant_name} fue aprobada.\n"
            f"El workspace ya esta activo con plan {plan_id}.\n\n"
            "Ya podes ingresar con tu email y la contrasena que definiste al solicitar la cuenta.\n"
            "Si no recordas la contrasena, usa el flujo de recuperacion en la pantalla de login.\n"
        ),
        html_body=(
            f"<p>Hola {greeting},</p>"
            f"<p>Tu solicitud para <strong>{tenant_name}</strong> fue aprobada.</p>"
            f"<p>El workspace ya est&aacute; activo con plan <strong>{plan_id}</strong>.</p>"
            "<p>Ya pod&eacute;s ingresar con tu email y la contrase&ntilde;a que definiste al solicitar la cuenta.</p>"
            "<p>Si no record&aacute;s la contrase&ntilde;a, us&aacute; el flujo de recuperaci&oacute;n en la pantalla de login.</p>"
        ),
    )


async def _send_free_request_rejection_email(owner_email: str, owner_name: str | None, tenant_name: str, notes: str | None) -> None:
    greeting = owner_name or owner_email
    notes_block = f"\n\nObservaciones del equipo:\n{notes}" if notes else ""
    notes_html = f"<p><strong>Observaciones del equipo:</strong><br>{notes}</p>" if notes else ""
    await send_email(
        to_email=owner_email,
        subject="Actualizacion de tu solicitud de Agentica",
        text_body=(
            f"Hola {greeting},\n\n"
            f"Por ahora no pudimos aprobar la solicitud para {tenant_name}.{notes_block}\n\n"
            "Si queres volver a intentarlo, podes enviar una nueva solicitud con informacion actualizada."
        ),
        html_body=(
            f"<p>Hola {greeting},</p>"
            f"<p>Por ahora no pudimos aprobar la solicitud para <strong>{tenant_name}</strong>.</p>"
            f"{notes_html}"
            "<p>Si quer&eacute;s volver a intentarlo, pod&eacute;s enviar una nueva solicitud con informaci&oacute;n actualizada.</p>"
        ),
    )

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


@router.get("/system/tool-readiness", response_model=list[ToolReadinessOut])
async def get_tool_readiness(ctx: CurrentContext) -> list[ToolReadinessOut]:
    ctx.require_human_user()
    settings = get_settings()
    tavily_ready = bool(settings.tavily_api_key)
    smtp_ready = is_mailer_configured()

    return [
        ToolReadinessOut(
            name="web_search",
            configured=tavily_ready,
            state="ready" if tavily_ready else "needs_config",
            state_label="Configurada globalmente" if tavily_ready else "Falta Tavily global",
            setup_hint=(
                "La clave Tavily ya esta cargada en esta instalacion."
                if tavily_ready
                else "Necesita una clave Tavily configurada en el backend o resuelta desde configuracion global."
            ),
        ),
        ToolReadinessOut(
            name="sql_query",
            configured=False,
            state="needs_config",
            state_label="Pendiente datasource",
            setup_hint="Necesita un DSN o conexion segura y todavia no tiene una UX completa de configuracion.",
        ),
        ToolReadinessOut(
            name="rest_api_call",
            configured=False,
            state="needs_config",
            state_label="Pendiente politica",
            setup_hint="Conviene definir dominios permitidos, metodos y headers por defecto antes de usarla en produccion.",
        ),
        ToolReadinessOut(
            name="calculator",
            configured=True,
            state="ready",
            state_label="Lista",
            setup_hint="No requiere credenciales ni configuracion adicional.",
        ),
        ToolReadinessOut(
            name="send_email",
            configured=smtp_ready,
            state="ready" if smtp_ready else "needs_config",
            state_label="Configurada globalmente" if smtp_ready else "Falta SMTP global",
            setup_hint=(
                "La plataforma ya tiene un mailer SMTP valido para esta tool."
                if smtp_ready
                else "Depende de una configuracion SMTP global valida en la plataforma; no requiere credenciales separadas por tool."
            ),
        ),
    ]

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
    _ensure_plans_enabled()
    plans = [PlanOut(**plan) for plan in await list_plans()]
    logger.info("[Access] system_plans_list tenant_id=%s user_id=%s count=%s", ctx.tenant_id, ctx.user_id, len(plans))
    return plans


@router.put("/system/plans/{plan_id}", response_model=PlanOut)
async def update_plan(plan_id: str, body: PlanUpdate, ctx: CurrentContext) -> PlanOut:
    await _require_system_admin(ctx)
    _ensure_plans_enabled()
    logger.info("[Access] system_plan_update_requested tenant_id=%s user_id=%s plan_id=%s", ctx.tenant_id, ctx.user_id, plan_id)
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

    logger.info("[Access] system_plan_update_success tenant_id=%s user_id=%s plan_id=%s", ctx.tenant_id, ctx.user_id, plan_id)
    return PlanOut(
        id=row.id,
        name=row.name,
        max_agents=row.max_agents,
        max_invocations_month=row.max_invocations_month,
        price_usd=float(row.price_usd or 0),
        features=row.features or {},
    )


@router.get("/system/free-requests", response_model=list[FreeRequestOut])
async def list_free_requests(ctx: CurrentContext, status: str | None = None) -> list[FreeRequestOut]:
    await _require_system_admin(ctx)
    _ensure_signup_enabled()
    query = """
        SELECT
            id,
            tenant_name,
            slug,
            owner_email,
            owner_name,
            company_sector,
            job_title,
            requested_plan_id,
            status,
            review_notes,
            approved_tenant_id,
            processed_by_user_id,
            processed_at,
            created_at
        FROM free_account_requests
    """
    params: dict[str, object] = {}
    if status:
        query += " WHERE status = :status"
        params["status"] = status
    query += """
        ORDER BY
            CASE status WHEN 'pending' THEN 1 WHEN 'approved' THEN 2 WHEN 'rejected' THEN 3 ELSE 9 END,
            created_at DESC
    """
    async with PublicSessionFactory() as db:
        result = await db.execute(text(query), params)
        rows = result.fetchall()
    logger.info("[Access] system_free_requests_list tenant_id=%s user_id=%s count=%s", ctx.tenant_id, ctx.user_id, len(rows))
    return [_map_free_request(row) for row in rows]


@router.post("/system/free-requests/{request_id}/approve", response_model=FreeRequestOut)
async def approve_free_request(request_id: str, body: FreeRequestApprove, ctx: CurrentContext) -> FreeRequestOut:
    await _require_system_admin(ctx)
    _ensure_signup_enabled()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT
                    id,
                    tenant_name,
                    slug,
                    owner_email,
                    owner_name,
                    company_sector,
                    job_title,
                    password_hash,
                    requested_plan_id,
                    status,
                    review_notes,
                    approved_tenant_id,
                    processed_by_user_id,
                    processed_at,
                    created_at
                FROM free_account_requests
                WHERE id = :request_id
            """),
            {"request_id": request_id},
        )
        request_row = result.fetchone()
        if not request_row:
            raise HTTPException(404, "Solicitud no encontrada")
        if request_row.status != "pending":
            raise HTTPException(409, "La solicitud ya fue procesada")

        existing_tenant = await db.execute(
            text("SELECT id FROM tenants WHERE slug = :slug"),
            {"slug": request_row.slug},
        )
        if existing_tenant.fetchone():
            raise HTTPException(409, "Ese slug ya estÃ¡ en uso")

        existing_user = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": request_row.owner_email},
        )
        if existing_user.fetchone():
            raise HTTPException(409, "Ese email ya estÃ¡ registrado")

    import uuid

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    plan_id = body.plan_id or request_row.requested_plan_id or "free"

    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO tenants (id, name, slug, plan_id)
                VALUES (:tenant_id, :tenant_name, :slug, :plan_id)
            """),
            {
                "tenant_id": tenant_id,
                "tenant_name": request_row.tenant_name,
                "slug": request_row.slug,
                "plan_id": plan_id,
            },
        )
        await conn.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, full_name, password_hash, role, status)
                VALUES (:user_id, :tenant_id, :email, :full_name, :password_hash, 'owner', 'active')
            """),
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "email": request_row.owner_email,
                "full_name": request_row.owner_name or "",
                "password_hash": request_row.password_hash,
            },
        )
        await conn.execute(
            text("""
                UPDATE free_account_requests
                SET
                    status = 'approved',
                    review_notes = :review_notes,
                    approved_tenant_id = :tenant_id,
                    processed_by_user_id = :processed_by_user_id,
                    processed_at = NOW(),
                    requested_plan_id = :plan_id
                WHERE id = :request_id
            """),
            {
                "request_id": request_id,
                "review_notes": body.notes,
                "tenant_id": tenant_id,
                "processed_by_user_id": ctx.user_id,
                "plan_id": plan_id,
            },
        )
        await provision_tenant(tenant_id, conn)

    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT
                    id,
                    tenant_name,
                    slug,
                    owner_email,
                    owner_name,
                    company_sector,
                    job_title,
                    requested_plan_id,
                    status,
                    review_notes,
                    approved_tenant_id,
                    processed_by_user_id,
                    processed_at,
                    created_at
                FROM free_account_requests
                WHERE id = :request_id
            """),
            {"request_id": request_id},
        )
        approved_row = result.fetchone()

    logger.info(
        "[Access] system_free_request_approved request_id=%s tenant_id=%s owner_user_id=%s admin_user_id=%s",
        request_id,
        tenant_id,
        user_id,
        ctx.user_id,
    )
    try:
        await _send_free_request_approval_email(
            owner_email=request_row.owner_email,
            owner_name=request_row.owner_name,
            tenant_name=request_row.tenant_name,
            plan_id=plan_id,
        )
    except Exception:
        logger.exception("[Access] system_free_request_approval_email_error request_id=%s", request_id)
    return _map_free_request(approved_row)


@router.post("/system/free-requests/{request_id}/reject", response_model=FreeRequestOut)
async def reject_free_request(request_id: str, body: FreeRequestDecision, ctx: CurrentContext) -> FreeRequestOut:
    await _require_system_admin(ctx)
    _ensure_signup_enabled()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                UPDATE free_account_requests
                SET
                    status = 'rejected',
                    review_notes = :review_notes,
                    processed_by_user_id = :processed_by_user_id,
                    processed_at = NOW()
                WHERE id = :request_id
                  AND status = 'pending'
                RETURNING
                    id,
                    tenant_name,
                    slug,
                    owner_email,
                    owner_name,
                    company_sector,
                    job_title,
                    requested_plan_id,
                    status,
                    review_notes,
                    approved_tenant_id,
                    processed_by_user_id,
                    processed_at,
                    created_at
            """),
            {
                "request_id": request_id,
                "review_notes": body.notes,
                "processed_by_user_id": ctx.user_id,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(404, "Solicitud pendiente no encontrada")
        await db.commit()

    logger.info("[Access] system_free_request_rejected request_id=%s admin_user_id=%s", request_id, ctx.user_id)
    try:
        await _send_free_request_rejection_email(
            owner_email=row.owner_email,
            owner_name=row.owner_name,
            tenant_name=row.tenant_name,
            notes=body.notes,
        )
    except Exception:
        logger.exception("[Access] system_free_request_rejection_email_error request_id=%s", request_id)
    return _map_free_request(row)


@router.get("/system/overview", response_model=list[TenantOverviewOut])
async def get_system_overview(ctx: CurrentContext) -> list[TenantOverviewOut]:
    await _require_system_admin(ctx)
    async with PublicSessionFactory() as db:
        tenants_result = await db.execute(
            text("""
                SELECT
                    t.id,
                    t.name,
                    t.slug,
                    t.plan_id,
                    t.created_at,
                    owner.email AS owner_email,
                    owner.full_name AS owner_name,
                    COALESCE(stats.user_count, 0) AS user_count,
                    COALESCE(stats.developer_count, 0) AS developer_count,
                    COALESCE(stats.viewer_count, 0) AS viewer_count
                FROM tenants t
                LEFT JOIN LATERAL (
                    SELECT email, full_name
                    FROM users
                    WHERE tenant_id = t.id AND role = 'owner'
                    ORDER BY created_at ASC
                    LIMIT 1
                ) owner ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS user_count,
                        COUNT(*) FILTER (WHERE role = 'developer') AS developer_count,
                        COUNT(*) FILTER (WHERE role = 'viewer') AS viewer_count
                    FROM users
                    WHERE tenant_id = t.id
                ) stats ON TRUE
                ORDER BY t.created_at DESC
            """)
        )
        tenant_rows = tenants_result.fetchall()

        users_result = await db.execute(
            text("""
                SELECT id, tenant_id, email, full_name, role, status, created_at
                FROM users
                ORDER BY created_at DESC
            """)
        )
        user_rows = users_result.fetchall()

    users_by_tenant: dict[str, list[TenantOverviewUserOut]] = {}
    for row in user_rows:
        tenant_key = str(row.tenant_id)
        users_by_tenant.setdefault(tenant_key, []).append(
            TenantOverviewUserOut(
                id=str(row.id),
                email=row.email,
                full_name=row.full_name,
                role=row.role,
                status=row.status,
                created_at=row.created_at.isoformat(),
            )
        )

    overview: list[TenantOverviewOut] = []
    for row in tenant_rows:
        tenant_id = str(row.id)
        plan = await get_tenant_plan(tenant_id)
        usage = await get_tenant_usage(tenant_id)
        overview.append(
            TenantOverviewOut(
                tenant_id=tenant_id,
                name=row.name,
                slug=row.slug,
                plan_id=row.plan_id,
                created_at=row.created_at.isoformat(),
                owner_email=row.owner_email,
                owner_name=row.owner_name,
                user_count=int(row.user_count or 0),
                developer_count=int(row.developer_count or 0),
                viewer_count=int(row.viewer_count or 0),
                agents_used=int(usage["agent_count"]),
                agents_limit=int(plan["max_agents"]),
                invocations_used=int(usage["invocations_month"]),
                invocations_limit=int(plan["max_invocations_month"]),
                users=users_by_tenant.get(tenant_id, []),
            )
        )

    logger.info("[Access] system_overview tenant_id=%s user_id=%s count=%s", ctx.tenant_id, ctx.user_id, len(overview))
    return overview
