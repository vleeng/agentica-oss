from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class DiscoveredTool(BaseModel):
    name: str
    description: str
    input_schema: dict = Field(default_factory=dict)


class MCPServerIn(BaseModel):
    name: str
    endpoint: str
    transport: Literal["sse", "http"] = "sse"
    auth_type: Literal["none", "bearer", "basic"] = "none"
    auth_config: dict = Field(default_factory=dict)


class MCPServerOut(MCPServerIn):
    id: str
    discovered_tools: list[DiscoveredTool] = Field(default_factory=list)
    is_active: bool
    last_tested_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "MCPServerOut":
        import json
        tools_raw = row.get("discovered_tools_json", [])
        auth_raw = row.get("auth_config_json", {})
        if isinstance(tools_raw, str):
            tools_raw = json.loads(tools_raw)
        if isinstance(auth_raw, str):
            auth_raw = json.loads(auth_raw)
        last_tested = row.get("last_tested_at")
        return cls(
            id=str(row["id"]),
            name=row["name"],
            endpoint=row["endpoint"],
            transport=row["transport"],
            auth_type=row["auth_type"],
            auth_config=auth_raw,
            discovered_tools=[DiscoveredTool(**t) for t in tools_raw],
            is_active=row["is_active"],
            last_tested_at=last_tested.isoformat() if last_tested and hasattr(last_tested, "isoformat") else None,
        )
