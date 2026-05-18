from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class WizardChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    content: str


class WizardChatStartRequest(BaseModel):
    initial_mode: Optional[Literal["single", "crew"]] = None


class WizardChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class WizardChatSessionResponse(BaseModel):
    session_id: str
    messages: list[WizardChatMessage] = Field(default_factory=list)
    draft_state: dict[str, Any] = Field(default_factory=dict)
    ready_to_create: bool = False
    completion: int = 0
    next_focus: Optional[str] = None
