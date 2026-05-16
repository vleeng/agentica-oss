from __future__ import annotations

from typing import Annotated, AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentContext, get_current_context
from app.db.repository import AgentRepository
from app.db.session import ensure_tenant_schema, get_tenant_session_factory


async def get_tenant_session(
    ctx: Annotated[CurrentContext, Depends(get_current_context)],
) -> AsyncIterator[AsyncSession]:
    await ensure_tenant_schema(ctx.tenant_id)
    factory = get_tenant_session_factory(ctx.tenant_id)
    async with factory() as session:
        yield session


async def get_repo(
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> AgentRepository:
    return AgentRepository(session)


TenantSession = Annotated[AsyncSession, Depends(get_tenant_session)]
TenantRepo    = Annotated[AgentRepository, Depends(get_repo)]
