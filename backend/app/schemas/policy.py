from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class BehaviorPolicyIn(BaseModel):
    tone: str = "profesional"
    escalation_conditions: list[str] = Field(default_factory=list)
    confirmation_triggers: list[str] = Field(default_factory=list)
    format_requirements: str = ""
    custom_rules: list[str] = Field(default_factory=list)


class BehaviorPolicyOut(BehaviorPolicyIn):
    id: str
    agent_id: str

    @classmethod
    def from_row(cls, row: dict) -> "BehaviorPolicyOut":
        import json
        def _load(v):
            return json.loads(v) if isinstance(v, str) else (v or [])
        return cls(
            id=str(row["id"]),
            agent_id=str(row["agent_id"]),
            tone=row.get("tone") or "profesional",
            escalation_conditions=_load(row.get("escalation_conditions_json")),
            confirmation_triggers=_load(row.get("confirmation_triggers_json")),
            format_requirements=row.get("format_requirements") or "",
            custom_rules=_load(row.get("custom_rules_json")),
        )
