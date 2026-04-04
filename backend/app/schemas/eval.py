from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BuildStatus(str, Enum):
    pending   = "pending"
    building  = "building"
    ready     = "ready"
    failed    = "failed"


class AgentBuildOut(BaseModel):
    id: UUID
    agent_id: UUID
    version: int
    status: BuildStatus
    code_path: Optional[str]
    error: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackItem(BaseModel):
    step_index: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class EvalReport(BaseModel):
    agent_id: UUID
    run_id: UUID
    task_completion_rate: float = Field(..., ge=0, le=1)
    tool_accuracy: float = Field(..., ge=0, le=1)
    avg_latency_ms: float
    p95_latency_ms: float
    estimated_cost_usd: float
    hallucination_score: float = Field(..., ge=0, le=1)
    human_feedback: list[FeedbackItem] = Field(default_factory=list)
    overall_score: float = Field(..., ge=0, le=1)
    pass_threshold: bool
    notes: str = ""


class EvalRunOut(BaseModel):
    id: UUID
    agent_id: UUID
    score: float
    passed: bool
    report: EvalReport
    created_at: datetime

    model_config = {"from_attributes": True}
