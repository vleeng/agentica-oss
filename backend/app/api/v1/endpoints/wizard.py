from __future__ import annotations

from fastapi import APIRouter

from app.core.security import CurrentContext
from app.schemas.wizard_advisor import WizardAdvisorRequest, WizardAdvisorResponse
from app.services.wizard.advisor import WizardAdvisorService

router = APIRouter()
advisor_svc = WizardAdvisorService()


@router.post("/wizard/advisor/analyze", response_model=WizardAdvisorResponse)
async def analyze_wizard(
    body: WizardAdvisorRequest,
    ctx: CurrentContext,
) -> WizardAdvisorResponse:
    ctx.require_human_user()
    ctx.require_developer()
    return await advisor_svc.analyze(body)
