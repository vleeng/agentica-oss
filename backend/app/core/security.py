from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password hashing ─────────────────────────────────────────────────────────

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Symmetric Encryption (API Keys) ──────────────────────────────────────────

import os
from cryptography.fernet import Fernet

_ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not _ENCRYPTION_KEY:
    if settings.is_production:
        raise RuntimeError(
            "ENCRYPTION_KEY no definida. "
            "Generá una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "y agregala al .env antes de iniciar en producción."
        )
    else:
        _ENCRYPTION_KEY = Fernet.generate_key().decode()
        print("[DEV] ENCRYPTION_KEY autogenerada — solo válida en desarrollo.")

_fernet = Fernet(_ENCRYPTION_KEY.encode())

def encrypt_provider_key(plain_key: str) -> str:
    return _fernet.encrypt(plain_key.encode()).decode()

def decrypt_provider_key(encrypted_key: str) -> str:
    try:
        return _fernet.decrypt(encrypted_key.encode()).decode()
    except Exception:
        raise ValueError("ENCRYPTION_KEY errónea o payload corrupto. Por favor introduzca su llave LLM de nuevo en la bóveda.")

# ── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(
    tenant_id: str,
    user_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Contexto de request (tenant + usuario) ───────────────────────────────────

class RequestContext:
    """Inyectado en todos los endpoints vía Depends."""

    def __init__(self, tenant_id: str, user_id: str, role: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_developer(self) -> bool:
        return self.role in ("owner", "developer")

    def require_developer(self) -> None:
        if not self.is_developer:
            raise HTTPException(status_code=403, detail="Se requiere rol developer o superior")

    def require_owner(self) -> None:
        if not self.is_owner:
            raise HTTPException(status_code=403, detail="Se requiere rol owner")


# ── Dependency para FastAPI ───────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_context(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(bearer_scheme),
    ] = None,
) -> RequestContext:
    """
    Dependency de FastAPI. Valida JWT y retorna el contexto del request.
    También soporta API keys en el header X-API-Key para integraciones externas.
    """
    token: Optional[str] = None

    # Prioridad: Bearer JWT > X-API-Key
    if credentials:
        token = credentials.credentials
    elif api_key := request.headers.get("X-API-Key"):
        ctx = await _resolve_api_key(api_key)
        if ctx:
            return ctx
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o expirada",
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    return RequestContext(
        tenant_id=payload["tenant_id"],
        user_id=payload["sub"],
        role=payload["role"],
    )


async def _resolve_api_key(raw_key: str) -> Optional[RequestContext]:
    """Resuelve una API key a su RequestContext. Importación tardía para evitar ciclos."""
    try:
        from app.api.v1.endpoints.api_keys import resolve_api_key
        result = await resolve_api_key(raw_key)
        if result:
            return RequestContext(
                tenant_id=result["tenant_id"],
                user_id="api_key",
                role="agent_user",   # scoped: solo puede invocar agentes
            )
    except Exception:
        pass
    return None


# Alias corto para usar como Depends
CurrentContext = Annotated[RequestContext, Depends(get_current_context)]
