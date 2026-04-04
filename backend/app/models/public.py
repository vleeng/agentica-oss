from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Schema public — tablas globales ──────────────────────────────────────────

class Plan(Base):
    __tablename__ = "plans"

    id:        Mapped[str]  = mapped_column(String, primary_key=True)
    name:      Mapped[str]  = mapped_column(String(100), nullable=False)
    max_agents: Mapped[int] = mapped_column(Integer, default=3)
    max_invocations_month: Mapped[int] = mapped_column(Integer, default=1000)
    price_usd: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    features:  Mapped[dict]  = mapped_column(JSONB, default=dict)


class Tenant(Base):
    __tablename__ = "tenants"

    id:         Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name:       Mapped[str]       = mapped_column(String(100), nullable=False)
    slug:       Mapped[str]       = mapped_column(String(50), unique=True, nullable=False)
    plan_id:    Mapped[str]       = mapped_column(String, ForeignKey("plans.id"), default="free")
    status:     Mapped[str]       = mapped_column(String(20), default="active")
    created_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    users:    Mapped[list["User"]]   = relationship("User", back_populates="tenant", cascade="all, delete")
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="tenant", cascade="all, delete")


class User(Base):
    __tablename__ = "users"

    id:            Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id:     Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"))
    email:         Mapped[str]       = mapped_column(String(255), unique=True, nullable=False)
    full_name:     Mapped[str | None]= mapped_column(String(200))
    password_hash: Mapped[str]       = mapped_column(Text, nullable=False)
    role:          Mapped[str]       = mapped_column(String(20), default="developer")
    status:        Mapped[str]       = mapped_column(String(20), default="active")
    created_at:    Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


class APIKey(Base):
    __tablename__ = "api_keys"

    id:         Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id:  Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"))
    key_hash:   Mapped[str]          = mapped_column(String(64), unique=True, nullable=False)
    name:       Mapped[str]          = mapped_column(String(100), nullable=False)
    scopes:     Mapped[list[str]]    = mapped_column(ARRAY(String), default=["invoke"])
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utcnow)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")
