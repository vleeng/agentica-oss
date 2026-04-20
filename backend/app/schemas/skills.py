from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.agent import ToolRef


class SkillIn(BaseModel):
    name: str
    description: str = ""
    objective: str
    usage_conditions: str = ""
    tools: list[ToolRef] = Field(default_factory=list)
    procedure: str
    quality_rules: str = ""
    output_format: str = ""
    guardrails: list[str] = Field(default_factory=list)


class SkillOut(SkillIn):
    id: str
    is_active: bool
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "SkillOut":
        import json
        tools_raw = row.get("tools_json", [])
        guardrails_raw = row.get("guardrails_json", [])
        if isinstance(tools_raw, str):
            tools_raw = json.loads(tools_raw)
        if isinstance(guardrails_raw, str):
            guardrails_raw = json.loads(guardrails_raw)
        return cls(
            id=str(row["id"]),
            name=row["name"],
            description=row.get("description") or "",
            objective=row["objective"],
            usage_conditions=row.get("usage_conditions") or "",
            tools=[ToolRef(**t) for t in tools_raw],
            procedure=row["procedure"],
            quality_rules=row.get("quality_rules") or "",
            output_format=row.get("output_format") or "",
            guardrails=guardrails_raw,
            is_active=row["is_active"],
            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        )
