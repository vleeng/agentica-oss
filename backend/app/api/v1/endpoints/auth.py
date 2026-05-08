from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from app.core.security import (
    CurrentContext,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import PublicSessionFactory, engine, provision_tenant
from app.schemas.tenant import LoginInput, TokenOut, UserCreate

router = APIRouter()


class TenantUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    role: Literal["developer", "viewer"] = "viewer"


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: UserCreate, request: Request) -> TokenOut:
    from app.core.rate_limiter import get_rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    await get_rate_limiter().check(
        identifier=f"register:{client_ip}",
        scope="register",
        max_requests=5,
        window_seconds=60,
    )
    """
    Registro rápido de usuario con tenant automático (slug = email prefix).
    Para registro completo con nombre de empresa usar POST /tenants/register.
    """
    import uuid

    async with PublicSessionFactory() as db:
        existing = await db.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": body.email}
        )
        if existing.fetchone():
            # Si ya existe, hacer login directo
            result = await db.execute(
                text("SELECT id, tenant_id, password_hash, role FROM users WHERE email = :e"),
                {"e": body.email},
            )
            row = result.fetchone()
            if row and verify_password(body.password, row.password_hash):
                token = create_access_token(str(row.tenant_id), str(row.id), row.role)
                return TokenOut(access_token=token, tenant_id=str(row.tenant_id),
                                user_id=str(row.id), role=row.role)
            raise HTTPException(409, "Email ya registrado con otra contraseña")

        tenant_id = str(uuid.uuid4())
        user_id   = str(uuid.uuid4())
        slug      = body.email.split("@")[0].lower().replace(".", "-")[:50]

        # Garantizar slug único
        slug_check = await db.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": slug})
        if slug_check.fetchone():
            slug = f"{slug}-{user_id[:6]}"

        await db.execute(
            text("INSERT INTO tenants (id, name, slug, plan_id) VALUES (:id, :n, :s, 'free')"),
            {"id": tenant_id, "n": body.full_name or body.email.split("@")[0], "s": slug},
        )
        await db.execute(
            text("""INSERT INTO users (id, tenant_id, email, full_name, password_hash, role)
                    VALUES (:id, :t, :e, :n, :h, 'owner')"""),
            {"id": user_id, "t": tenant_id, "e": body.email,
             "n": body.full_name or "", "h": hash_password(body.password)},
        )
        await db.commit()

    # Provisionar schema del tenant
    async with engine.begin() as conn:
        await provision_tenant(tenant_id, conn)

    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role="owner")
    return TokenOut(access_token=token, tenant_id=tenant_id, user_id=user_id, role="owner")


@router.post("/login", response_model=TokenOut)
async def login(body: LoginInput, request: Request) -> TokenOut:
    from app.core.rate_limiter import get_rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    await get_rate_limiter().check(
        identifier=f"login:{client_ip}",
        scope="login",
        max_requests=10,
        window_seconds=60,
    )
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("SELECT id, tenant_id, password_hash, role FROM users WHERE email = :e AND status='active'"),
            {"e": body.email},
        )
        row = result.fetchone()

    if not row or not verify_password(body.password, row.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")

    token = create_access_token(str(row.tenant_id), str(row.id), row.role)
    return TokenOut(access_token=token, tenant_id=str(row.tenant_id),
                    user_id=str(row.id), role=row.role)


@router.get("/me")
async def get_me(ctx: CurrentContext) -> dict:
    ctx.require_human_user()
    return {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id, "role": ctx.role}


@router.get("/users")
async def list_users(ctx: CurrentContext) -> list[dict]:
    ctx.require_human_user()
    ctx.require_owner()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT id, tenant_id, email, full_name, role, status, created_at
                FROM users
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC
            """),
            {"tenant_id": ctx.tenant_id},
        )
        rows = result.fetchall()

    return [
        {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "email": row.email,
            "full_name": row.full_name,
            "role": row.role,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post("/users", status_code=201)
async def create_user(body: TenantUserCreate, ctx: CurrentContext) -> dict:
    ctx.require_human_user()
    ctx.require_owner()

    import uuid

    async with PublicSessionFactory() as db:
        existing = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": body.email},
        )
        if existing.fetchone():
            raise HTTPException(409, "Email ya registrado")

        user_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO users (id, tenant_id, email, full_name, password_hash, role, status)
                VALUES (:id, :tenant_id, :email, :full_name, :password_hash, :role, 'active')
            """),
            {
                "id": user_id,
                "tenant_id": ctx.tenant_id,
                "email": body.email,
                "full_name": body.full_name or "",
                "password_hash": hash_password(body.password),
                "role": body.role,
            },
        )
        await db.commit()

    return {
        "id": user_id,
        "tenant_id": ctx.tenant_id,
        "email": body.email,
        "full_name": body.full_name or "",
        "role": body.role,
        "status": "active",
    }
