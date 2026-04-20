from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class GuardrailRuleIn(BaseModel):
    name: str
    rule_type: Literal["input_block", "output_filter", "length_limit", "topic_restrict"]
    condition: dict = Field(default_factory=dict)
    action: Literal["block", "warn", "transform"] = "block"
    priority: int = 0


class GuardrailRuleOut(GuardrailRuleIn):
    id: str
    agent_id: str
    is_active: bool

    @classmethod
    def from_row(cls, row: dict) -> "GuardrailRuleOut":
        import json
        cond = row.get("condition_json", {})
        if isinstance(cond, str):
            cond = json.loads(cond)
        return cls(
            id=str(row["id"]),
            agent_id=str(row["agent_id"]),
            name=row["name"],
            rule_type=row["rule_type"],
            condition=cond,
            action=row["action"],
            priority=row["priority"],
            is_active=row["is_active"],
        )
