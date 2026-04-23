from __future__ import annotations

from fastapi import APIRouter, HTTPException, status, Request
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
    return {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id, "role": ctx.role}
