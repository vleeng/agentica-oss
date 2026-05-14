from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WizardAdvisorItem(BaseModel):
    title: str
    detail: str
    severity: Literal["info", "warning", "critical"] = "info"


class WizardAdvisorRequest(BaseModel):
    step: int = Field(..., ge=0, le=5)
    step_key: str = Field(default="unknown", max_length=50)
    final_review: bool = False
    wizard_state: dict[str, Any] = Field(default_factory=dict)
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_readiness: list[dict[str, Any]] = Field(default_factory=list)
    available_models: list[dict[str, Any]] = Field(default_factory=list)


class WizardAdvisorResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    status: Literal["ready", "requires_review", "high_risk"]
    summary: str
    suggestions: list[WizardAdvisorItem] = Field(default_factory=list)
    risks: list[WizardAdvisorItem] = Field(default_factory=list)
    questions: list[WizardAdvisorItem] = Field(default_factory=list)
    proposed_patch: dict[str, Any] = Field(default_factory=dict)
    source: Literal["ai", "rules"] = "ai"
