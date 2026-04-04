from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import TenantRepo
from app.core.security import CurrentContext, create_access_token, hash_password, verify_password
from app.db.session import engine, provision_tenant
from app.schemas.tenant import TenantCreate, TokenOut, UserCreate

router = APIRouter()


@router.post("/register", response_model=TokenOut, status_code=201)
async def register_tenant(body: TenantCreate, user: UserCreate) -> TokenOut:
    from app.db.session import PublicSessionFactory
    import uuid

    async with PublicSessionFactory() as db:
        existing = await db.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": body.slug})
        if existing.fetchone():
            raise HTTPException(409, f"Slug '{body.slug}' ya en uso")
        existing_email = await db.execute(text("SELECT id FROM users WHERE email = :e"), {"e": user.email})
        if existing_email.fetchone():
            raise HTTPException(409, "Email ya registrado")

        tenant_id = str(uuid.uuid4())
        user_id   = str(uuid.uuid4())
        await db.execute(
            text("INSERT INTO tenants (id, name, slug, plan_id) VALUES (:id, :n, :s, :p)"),
            {"id": tenant_id, "n": body.name, "s": body.slug, "p": body.plan_id},
        )
        await db.execute(
            text("INSERT INTO users (id, tenant_id, email, full_name, password_hash, role) VALUES (:id, :t, :e, :n, :h, 'owner')"),
            {"id": user_id, "t": tenant_id, "e": user.email, "n": user.full_name or "", "h": hash_password(user.password)},
        )
        await db.commit()

    async with engine.begin() as conn:
        await provision_tenant(tenant_id, conn)

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
    return await repo.list_agents()


@router.get("/me/billing")
async def billing_summary(ctx: CurrentContext, repo: TenantRepo) -> dict:
    return await repo.get_billing_summary()
