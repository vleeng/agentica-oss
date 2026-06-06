from __future__ import annotations

import hashlib
import logging
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.core.mailer import MailerNotConfiguredError, is_mailer_configured, send_email
from app.core.product_profile import get_product_profile_state
from app.core.security import (
    CurrentContext,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import PublicSessionFactory, engine, provision_tenant
from app.schemas.tenant import LoginInput, TokenOut, UserCreate

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


class TenantUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = None
    role: Literal["developer", "viewer"] = "viewer"


class ChangePasswordInput(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ForgotPasswordOut(BaseModel):
    accepted: bool = True
    reset_token: str | None = None
    expires_in_minutes: int = 60
    email_sent: bool = False


class ResetPasswordInput(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)


class FreeAccountRequestInput(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=80)
    last_name: str = Field(..., min_length=2, max_length=80)
    owner_email: EmailStr
    company_name: str = Field(..., min_length=2, max_length=100)
    company_sector: str = Field(..., min_length=2, max_length=80)
    job_title: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)


class FreeAccountRequestOut(BaseModel):
    id: str
    tenant_name: str
    slug: str
    owner_email: EmailStr
    owner_name: str | None = None
    company_sector: str | None = None
    job_title: str | None = None
    requested_plan_id: str
    status: str
    created_at: str


def _slugify_company_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:50] or "workspace"


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: UserCreate, request: Request) -> TokenOut:
    if not get_product_profile_state().features.signup:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El registro publico no esta disponible en este perfil.")
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
    if not settings.allow_direct_signup:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "El alta directa estÃ¡ deshabilitada. SolicitÃ¡ una cuenta free para aprobaciÃ³n.",
        )

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


@router.post("/free-request", response_model=FreeAccountRequestOut, status_code=201)
async def request_free_account(body: FreeAccountRequestInput, request: Request) -> FreeAccountRequestOut:
    if not get_product_profile_state().features.signup:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La solicitud de cuentas publicas no esta disponible en este perfil.")
    from app.core.rate_limiter import get_rate_limiter
    import uuid

    client_ip = request.client.host if request.client else "unknown"
    await get_rate_limiter().check(
        identifier=f"free-request:{client_ip}",
        scope="free-request",
        max_requests=5,
        window_seconds=300,
    )

    logger.info(
        "[Access] free_request_requested company=%s owner_email=%s",
        body.company_name,
        body.owner_email,
    )

    async with PublicSessionFactory() as db:
        existing_user = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": body.owner_email},
        )
        if existing_user.fetchone():
            raise HTTPException(409, "Ese email ya estÃ¡ registrado")

        existing_request = await db.execute(
            text("""
                SELECT id
                FROM free_account_requests
                WHERE status = 'pending'
                  AND owner_email = :owner_email
                LIMIT 1
            """),
            {"owner_email": body.owner_email},
        )
        if existing_request.fetchone():
            raise HTTPException(409, "Ya existe una solicitud pendiente para ese email")

        base_slug = _slugify_company_name(body.company_name)
        slug = base_slug
        suffix = 2
        while True:
            slug_conflict = await db.execute(
                text("""
                    SELECT 1
                    FROM (
                        SELECT slug FROM tenants
                        UNION ALL
                        SELECT slug FROM free_account_requests
                    ) candidates
                    WHERE slug = :slug
                    LIMIT 1
                """),
                {"slug": slug},
            )
            if not slug_conflict.fetchone():
                break
            slug = f"{base_slug[: max(1, 50 - len(str(suffix)) - 1)]}-{suffix}"
            suffix += 1

        request_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        owner_name = f"{body.first_name.strip()} {body.last_name.strip()}".strip()
        await db.execute(
            text("""
                INSERT INTO free_account_requests (
                    id,
                    tenant_name,
                    slug,
                    owner_email,
                    owner_name,
                    company_sector,
                    job_title,
                    password_hash,
                    requested_plan_id,
                    status
                )
                VALUES (
                    :id,
                    :tenant_name,
                    :slug,
                    :owner_email,
                    :owner_name,
                    :company_sector,
                    :job_title,
                    :password_hash,
                    'free',
                    'pending'
                )
            """),
            {
                "id": request_id,
                "tenant_name": body.company_name,
                "slug": slug,
                "owner_email": body.owner_email,
                "owner_name": owner_name,
                "company_sector": body.company_sector,
                "job_title": body.job_title,
                "password_hash": hash_password(body.password),
            },
        )
        await db.commit()

    logger.info(
        "[Access] free_request_success request_id=%s slug=%s owner_email=%s",
        request_id,
        slug,
        body.owner_email,
    )
    return FreeAccountRequestOut(
        id=request_id,
        tenant_name=body.company_name,
        slug=slug,
        owner_email=body.owner_email,
        owner_name=owner_name,
        company_sector=body.company_sector,
        job_title=body.job_title,
        requested_plan_id="free",
        status="pending",
        created_at=created_at.isoformat(),
    )


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
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT u.email, u.full_name, t.name AS tenant_name, t.slug AS tenant_slug
                FROM users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE u.id = :user_id AND u.tenant_id = :tenant_id
            """),
            {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id},
        )
        row = result.fetchone()
    logger.info("[Access] auth_me tenant_id=%s user_id=%s role=%s", ctx.tenant_id, ctx.user_id, ctx.role)
    return {
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "role": ctx.role,
        "email": row.email if row else None,
        "full_name": row.full_name if row else None,
        "tenant_name": row.tenant_name if row else None,
        "tenant_slug": row.tenant_slug if row else None,
    }


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

    logger.info("[Access] auth_users_list tenant_id=%s owner_user_id=%s count=%s", ctx.tenant_id, ctx.user_id, len(rows))

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
    logger.info(
        "[Access] auth_user_create_requested tenant_id=%s owner_user_id=%s email=%s role=%s",
        ctx.tenant_id,
        ctx.user_id,
        body.email,
        body.role,
    )

    import uuid

    async with PublicSessionFactory() as db:
        existing = await db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": body.email},
        )
        if existing.fetchone():
            logger.warning("[Access] auth_user_create_conflict email=%s", body.email)
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

    logger.info(
        "[Access] auth_user_create_success tenant_id=%s created_user_id=%s email=%s role=%s",
        ctx.tenant_id,
        user_id,
        body.email,
        body.role,
    )

    return {
        "id": user_id,
        "tenant_id": ctx.tenant_id,
        "email": body.email,
        "full_name": body.full_name or "",
        "role": body.role,
        "status": "active",
    }


@router.post("/change-password", status_code=204, response_class=Response, response_model=None)
async def change_password(body: ChangePasswordInput, ctx: CurrentContext) -> None:
    ctx.require_human_user()
    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT password_hash
                FROM users
                WHERE id = :user_id AND tenant_id = :tenant_id AND status = 'active'
            """),
            {"user_id": ctx.user_id, "tenant_id": ctx.tenant_id},
        )
        row = result.fetchone()
        if not row or not verify_password(body.current_password, row.password_hash):
            raise HTTPException(400, "La contraseña actual no coincide")

        await db.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash
                WHERE id = :user_id AND tenant_id = :tenant_id
            """),
            {
                "user_id": ctx.user_id,
                "tenant_id": ctx.tenant_id,
                "password_hash": hash_password(body.new_password),
            },
        )
        await db.execute(
            text("""
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE user_id = :user_id AND used_at IS NULL
            """),
            {"user_id": ctx.user_id},
        )
        await db.commit()

    logger.info("[Access] auth_change_password_success tenant_id=%s user_id=%s", ctx.tenant_id, ctx.user_id)


@router.post("/forgot-password", response_model=ForgotPasswordOut)
async def forgot_password(body: ForgotPasswordInput, request: Request) -> ForgotPasswordOut:
    from app.core.rate_limiter import get_rate_limiter

    client_ip = request.client.host if request.client else "unknown"
    await get_rate_limiter().check(
        identifier=f"forgot-password:{client_ip}",
        scope="forgot-password",
        max_requests=5,
        window_seconds=300,
    )

    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT id
                FROM users
                WHERE email = :email AND status = 'active'
            """),
            {"email": body.email},
        )
        row = result.fetchone()
        if not row:
            logger.info("[Access] auth_forgot_password_unknown_email email=%s", body.email)
            return ForgotPasswordOut()

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)

        await db.execute(
            text("DELETE FROM password_reset_tokens WHERE user_id = :user_id OR expires_at < NOW()"),
            {"user_id": row.id},
        )
        await db.execute(
            text("""
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, :expires_at)
            """),
            {
                "user_id": row.id,
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )
        await db.commit()

    if not is_mailer_configured():
        logger.warning("[Access] auth_forgot_password_mailer_missing email=%s", body.email)
        if settings.email_return_tokens_in_response:
            return ForgotPasswordOut(reset_token=raw_token, email_sent=False)
        raise HTTPException(503, "El correo de recuperacion no esta configurado")

    reset_url = f"{request.base_url}agentica/login"
    subject = "Recuperacion de contrasena - Agentica"
    text_body = (
        "Recibimos un pedido para restablecer tu contrasena de Agentica.\n\n"
        f"Token de recuperacion: {raw_token}\n"
        f"Vence en {60} minutos.\n\n"
        f"Podes usarlo desde: {reset_url}\n\n"
        "Si no hiciste este pedido, podes ignorar este correo."
    )
    html_body = f"""
        <p>Recibimos un pedido para restablecer tu contrase&ntilde;a de Agentica.</p>
        <p><strong>Token de recuperaci&oacute;n:</strong> <code>{raw_token}</code></p>
        <p>Vence en 60 minutos.</p>
        <p>Pod&eacute;s usarlo desde: <a href="{reset_url}">{reset_url}</a></p>
        <p>Si no hiciste este pedido, pod&eacute;s ignorar este correo.</p>
    """

    try:
        await send_email(
            to_email=body.email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )
    except MailerNotConfiguredError:
        if settings.email_return_tokens_in_response:
            return ForgotPasswordOut(reset_token=raw_token, email_sent=False)
        raise HTTPException(503, "El correo de recuperacion no esta configurado")
    except Exception:
        logger.exception("[Access] auth_forgot_password_mail_error email=%s", body.email)
        if settings.email_return_tokens_in_response:
            return ForgotPasswordOut(reset_token=raw_token, email_sent=False)
        raise HTTPException(502, "No pudimos enviar el correo de recuperacion")

    logger.info("[Access] auth_forgot_password_email_sent email=%s expires_at=%s", body.email, expires_at.isoformat())
    return ForgotPasswordOut(
        reset_token=raw_token if settings.email_return_tokens_in_response else None,
        email_sent=True,
    )


@router.post("/reset-password", status_code=204, response_class=Response, response_model=None)
async def reset_password(body: ResetPasswordInput, request: Request) -> None:
    from app.core.rate_limiter import get_rate_limiter

    client_ip = request.client.host if request.client else "unknown"
    await get_rate_limiter().check(
        identifier=f"reset-password:{client_ip}",
        scope="reset-password",
        max_requests=10,
        window_seconds=300,
    )

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()

    async with PublicSessionFactory() as db:
        result = await db.execute(
            text("""
                SELECT prt.id, prt.user_id, u.email
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.token_hash = :token_hash
                  AND prt.used_at IS NULL
                  AND prt.expires_at >= NOW()
                  AND u.status = 'active'
            """),
            {"token_hash": token_hash},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(400, "El token de recuperación es inválido o expiró")

        await db.execute(
            text("""
                UPDATE users
                SET password_hash = :password_hash
                WHERE id = :user_id
            """),
            {"user_id": row.user_id, "password_hash": hash_password(body.new_password)},
        )
        await db.execute(
            text("""
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE user_id = :user_id AND used_at IS NULL
            """),
            {"user_id": row.user_id},
        )
        await db.commit()

    logger.info("[Access] auth_reset_password_success email=%s user_id=%s", row.email, row.user_id)
