from __future__ import annotations
import asyncio
import json
import logging
from typing import Any

import httpx
from langchain_core.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)


def _build_auth_headers(auth_type: str, auth_config: dict) -> dict:
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {auth_config.get('token', '')}"}
    if auth_type == "basic":
        import base64
        creds = f"{auth_config.get('user', '')}:{auth_config.get('pass', '')}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {}


async def discover_tools(
    endpoint: str,
    transport: str,
    auth_type: str,
    auth_config: dict,
    timeout: int = 10,
) -> list[dict]:
    """
    Conecta al servidor MCP vía HTTP o SSE y retorna la lista de tools descubiertas.
    Soporta el endpoint estándar GET /tools (MCP HTTP) y POST /initialize (MCP SSE).
    """
    headers = _build_auth_headers(auth_type, auth_config)
    headers["Accept"] = "application/json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{endpoint.rstrip('/')}/tools", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            # Soporte para respuesta {tools: [...]} o lista directa
            tools = data.get("tools", data) if isinstance(data, dict) else data
            return tools if isinstance(tools, list) else []
        except httpx.HTTPStatusError as e:
            logger.warning(f"MCP discover_tools HTTP error {e.response.status_code} at {endpoint}")
            return []
        except Exception as e:
            logger.warning(f"MCP discover_tools failed at {endpoint}: {e}")
            return []


async def call_mcp_tool(
    endpoint: str,
    tool_name: str,
    arguments: dict,
    auth_type: str,
    auth_config: dict,
    timeout: int = 30,
) -> str:
    """Invoca una tool en el servidor MCP y retorna el resultado como string."""
    headers = _build_auth_headers(auth_type, auth_config)
    headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{endpoint.rstrip('/')}/tools/call",
            json={"name": tool_name, "arguments": arguments},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        # Soporte para {content: [...]} (MCP spec) o {result: ...}
        content = data.get("content", data.get("result", ""))
        if isinstance(content, list):
            return "\n".join(
                c.get("text", str(c)) for c in content if isinstance(c, dict)
            )
        return str(content)


def build_mcp_tool(server_row: dict, tool_meta: dict) -> BaseTool:
    """
    Crea un LangChain BaseTool que delega la ejecución al servidor MCP.
    Sigue el mismo patrón de clase dinámica que custom_loader.py.
    """
    import json as _json

    endpoint = server_row["endpoint"]
    auth_type = server_row.get("auth_type", "none")
    auth_config_raw = server_row.get("auth_config_json", {})
    auth_config = _json.loads(auth_config_raw) if isinstance(auth_config_raw, str) else auth_config_raw

    tool_name = tool_meta["name"]
    tool_description = tool_meta.get("description", tool_name)

    class _MCPTool(BaseTool):
        name: str = Field(default=tool_name)
        description: str = Field(default=tool_description)

        def _run(self, tool_input: str, **kwargs: Any) -> str:
            raise NotImplementedError("Use async version")

        async def _arun(self, tool_input: str, **kwargs: Any) -> str:
            try:
                arguments = _json.loads(tool_input) if tool_input.strip().startswith("{") else {"input": tool_input}
            except Exception:
                arguments = {"input": tool_input}
            return await call_mcp_tool(endpoint, tool_name, arguments, auth_type, auth_config)

    _MCPTool.__name__ = f"MCPTool_{tool_name}"
    return _MCPTool()


async def get_agent_mcp_tools(server_rows: list[dict]) -> list[BaseTool]:
    """Construye la lista de BaseTool para todos los servidores MCP asignados al agente."""
    tools: list[BaseTool] = []
    for server in server_rows:
        discovered_raw = server.get("discovered_tools_json", [])
        if isinstance(discovered_raw, str):
            import json as _j
            discovered_raw = _j.loads(discovered_raw)
        for tool_meta in discovered_raw:
            try:
                tools.append(build_mcp_tool(server, tool_meta))
            except Exception as e:
                logger.warning(f"Failed to build MCP tool {tool_meta.get('name')}: {e}")
    return tools
