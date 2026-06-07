from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.api.deps import TenantRepo
from app.core.product_profile import get_product_profile_state
from app.core.security import (
    CurrentContext,
    RequestContext,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.session import engine, provision_tenant
from app.schemas.tenant import TenantCreate, TokenOut, UserCreate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=TokenOut, status_code=201)
async def register_tenant(body: TenantCreate, user: UserCreate, request: Request) -> TokenOut:
    caller_ctx = await _get_optional_context(request)
    if not get_product_profile_state().features.signup and caller_ctx is None:
        raise HTTPException(404, "El alta publica de tenants no esta disponible en este perfil.")

    from app.db.session import PublicSessionFactory
    import uuid

    if get_product_profile_state().features.plans:
        requested_plan = body.plan_id or "free"
    else:
        requested_plan = "enterprise"

    if caller_ctx is not None:
        caller_ctx.require_human_user()
        if not await _is_system_admin(caller_ctx):
            logger.warning(
                "[Access] tenant_register_forbidden_non_admin tenant_id=%s user_id=%s requested_plan=%s",
                caller_ctx.tenant_id,
                caller_ctx.user_id,
                requested_plan,
            )
            raise HTTPException(403, "Solo el admin general puede crear tenants desde la consola")
    elif requested_plan != "free":
        logger.warning(
            "[Access] tenant_register_forbidden_public_plan owner_email=%s requested_plan=%s",
            user.email,
            requested_plan,
        )
        raise HTTPException(403, "El registro publico solo permite crear tenants en plan free")

    logger.info(
        "[Access] tenant_register_requested slug=%s plan_id=%s owner_email=%s",
        body.slug,
        requested_plan,
        user.email,
    )

    async with PublicSessionFactory() as db:
        existing = await db.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": body.slug})
        if existing.fetchone():
            logger.warning("[Access] tenant_register_conflict_slug slug=%s", body.slug)
            raise HTTPException(409, f"Slug '{body.slug}' ya en uso")
        existing_email = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": user.email})
        if existing_email.fetchone():
            logger.warning("[Access] tenant_register_conflict_email owner_email=%s", user.email)
            raise HTTPException(409, "Email ya registrado")

        tenant_id = str(uuid.uuid4())
        user_id   = str(uuid.uuid4())
        await db.execute(
            text("INSERT INTO tenants (id, name, slug, plan_id) VALUES (:id, :n, :s, :p)"),
            {"id": tenant_id, "n": body.name, "s": body.slug, "p": requested_plan},
        )
        await db.execute(
            text("INSERT INTO users (id, tenant_id, email, full_name, password_hash, role) VALUES (:id, :t, :e, :n, :h, 'owner')"),
            {"id": user_id, "t": tenant_id, "e": user.email, "n": user.full_name or "", "h": hash_password(user.password)},
        )
        await db.commit()

    async with engine.begin() as conn:
        await provision_tenant(tenant_id, conn)

    logger.info(
        "[Access] tenant_register_success tenant_id=%s user_id=%s slug=%s plan_id=%s",
        tenant_id,
        user_id,
        body.slug,
        requested_plan,
    )
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role="owner")
    return TokenOut(access_token=token, tenant_id=tenant_id, user_id=user_id, role="owner")


@router.post("/login", response_model=TokenOut)
async def login(user: UserCreate) -> TokenOut:
    from app.db.session import PublicSessionFactory

    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("SELECT id, tenant_id, password_hash, role FROM users WHERE email = :e AND status = 'active'"),
            {"e": user.email},
        )
        row = result.fetchone()

    if not row or not verify_password(user.password, row.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")

    token = create_access_token(str(row.tenant_id), str(row.id), row.role)
    return TokenOut(access_token=token, tenant_id=str(row.tenant_id), user_id=str(row.id), role=row.role)


@router.get("/me/agents")
async def list_agents(ctx: CurrentContext, repo: TenantRepo) -> list[dict]:
    ctx.require_human_user()
    return await repo.list_agents()


@router.get("/me/billing")
async def billing_summary(ctx: CurrentContext, repo: TenantRepo) -> dict:
    ctx.require_human_user()
    if not get_product_profile_state().features.billing:
        raise HTTPException(404, "El billing no esta disponible en este perfil.")
    return await repo.get_billing_summary()


async def _get_optional_context(request: Request) -> RequestContext | None:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None

    payload = decode_access_token(auth_header[7:])
    return RequestContext(
        tenant_id=payload["tenant_id"],
        user_id=payload["sub"],
        role=payload["role"],
    )


async def _is_system_admin(ctx: RequestContext) -> bool:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT t.slug
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE u.id = :user_id AND t.id = :tenant_id
            """),
            {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id},
        )
        row = result.fetchone()

    return bool(row and row.slug == "admin" and ctx.role == "owner")
