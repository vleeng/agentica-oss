from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.security import CurrentContext
from app.schemas.wizard_advisor import WizardAdvisorRequest, WizardAdvisorResponse
from app.schemas.wizard_chat import (
    WizardChatMessageRequest,
    WizardChatSessionResponse,
    WizardChatStartRequest,
)
from app.services.wizard.advisor import WizardAdvisorService
from app.services.wizard.chat import WizardChatService

router = APIRouter()
advisor_svc = WizardAdvisorService()
chat_svc = WizardChatService()


@router.post("/wizard/advisor/analyze", response_model=WizardAdvisorResponse)
async def analyze_wizard(
    body: WizardAdvisorRequest,
    ctx: CurrentContext,
) -> WizardAdvisorResponse:
    ctx.require_human_user()
    ctx.require_developer()
    return await advisor_svc.analyze(body)


@router.post("/wizard/chat/start", response_model=WizardChatSessionResponse)
async def start_wizard_chat(
    body: WizardChatStartRequest,
    ctx: CurrentContext,
) -> WizardChatSessionResponse:
    ctx.require_human_user()
    ctx.require_developer()
    return await chat_svc.start(tenant_id=ctx.tenant_id, initial_mode=body.initial_mode)


@router.get("/wizard/chat/{session_id}", response_model=WizardChatSessionResponse)
async def get_wizard_chat(
    session_id: str,
    ctx: CurrentContext,
) -> WizardChatSessionResponse:
    ctx.require_human_user()
    ctx.require_developer()
    try:
        return chat_svc.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesion de wizard no encontrada.") from exc


@router.post("/wizard/chat/{session_id}/message", response_model=WizardChatSessionResponse)
async def send_wizard_chat_message(
    session_id: str,
    body: WizardChatMessageRequest,
    ctx: CurrentContext,
) -> WizardChatSessionResponse:
    ctx.require_human_user()
    ctx.require_developer()
    try:
        return await chat_svc.message(session_id, body.message)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesion de wizard no encontrada.") from exc
