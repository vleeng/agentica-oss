from __future__ import annotations
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.components.mcp.mcp_client import discover_tools
from app.schemas.mcp import MCPServerIn, MCPServerOut

router = APIRouter()


@router.get("/mcp/", response_model=list[MCPServerOut])
async def list_mcp_servers(repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.list_mcp_servers()
    return [MCPServerOut.from_row(r) for r in rows]


@router.post("/mcp/", response_model=MCPServerOut, status_code=201)
async def create_mcp_server(body: MCPServerIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "endpoint": body.endpoint,
        "transport": body.transport,
        "auth_type": body.auth_type,
        "auth_config_json": json.dumps(body.auth_config),
        "discovered_tools_json": "[]",
    }
    row = await repo.create_mcp_server(data)
    return MCPServerOut.from_row(row)


@router.get("/mcp/{server_id}", response_model=MCPServerOut)
async def get_mcp_server(server_id: str, repo: TenantRepo, ctx: CurrentContext):
    row = await repo.get_mcp_server(server_id)
    if not row:
        raise HTTPException(status_code=404, detail="Servidor MCP no encontrado")
    return MCPServerOut.from_row(row)


@router.put("/mcp/{server_id}", response_model=MCPServerOut)
async def update_mcp_server(server_id: str, body: MCPServerIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "endpoint": body.endpoint,
        "transport": body.transport,
        "auth_type": body.auth_type,
        "auth_config_json": json.dumps(body.auth_config),
    }
    row = await repo.update_mcp_server(server_id, data)
    if not row:
        raise HTTPException(status_code=404, detail="Servidor MCP no encontrado")
    return MCPServerOut.from_row(row)


@router.delete("/mcp/{server_id}", status_code=204)
async def delete_mcp_server(server_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    deleted = await repo.delete_mcp_server(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Servidor MCP no encontrado")
    return Response(status_code=204)


@router.post("/mcp/{server_id}/test", response_model=MCPServerOut)
async def test_mcp_server(server_id: str, repo: TenantRepo, ctx: CurrentContext):
    """Prueba la conexión al servidor MCP y redescubre sus tools."""
    ctx.require_developer()
    row = await repo.get_mcp_server(server_id)
    if not row:
        raise HTTPException(status_code=404, detail="Servidor MCP no encontrado")

    auth_raw = row.get("auth_config_json", {})
    auth_config = json.loads(auth_raw) if isinstance(auth_raw, str) else auth_raw

    tools = await discover_tools(
        endpoint=row["endpoint"],
        transport=row["transport"],
        auth_type=row["auth_type"],
        auth_config=auth_config,
    )

    updated = await repo.update_mcp_server(server_id, {
        "discovered_tools_json": json.dumps(tools),
        "last_tested_at": datetime.now(timezone.utc),
    })
    return MCPServerOut.from_row(updated)


# ── Asignación a agentes ──────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/mcp", response_model=list[MCPServerOut])
async def get_agent_mcp_servers(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.get_agent_mcp_servers(agent_id)
    return [MCPServerOut.from_row(r) for r in rows]


@router.post("/agents/{agent_id}/mcp/{server_id}", status_code=204)
async def assign_mcp(agent_id: str, server_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    server = await repo.get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Servidor MCP no encontrado")
    await repo.assign_mcp_to_agent(agent_id, server_id)
    return Response(status_code=204)


@router.delete("/agents/{agent_id}/mcp/{server_id}", status_code=204)
async def unassign_mcp(agent_id: str, server_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    await repo.unassign_mcp_from_agent(agent_id, server_id)
    return Response(status_code=204)
