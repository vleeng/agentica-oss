from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Response

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.schemas.policy import BehaviorPolicyIn, BehaviorPolicyOut

router = APIRouter()


@router.get("/agents/{agent_id}/policy", response_model=BehaviorPolicyOut)
async def get_policy(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    row = await repo.get_agent_policy(agent_id)
    if not row:
        raise HTTPException(status_code=404, detail="Política no encontrada")
    return BehaviorPolicyOut.from_row(row)


@router.put("/agents/{agent_id}/policy", response_model=BehaviorPolicyOut)
async def upsert_policy(agent_id: str, body: BehaviorPolicyIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "tone": body.tone,
        "escalation_conditions_json": json.dumps(body.escalation_conditions),
        "confirmation_triggers_json": json.dumps(body.confirmation_triggers),
        "format_requirements": body.format_requirements,
        "custom_rules_json": json.dumps(body.custom_rules),
    }
    row = await repo.upsert_agent_policy(agent_id, data)
    return BehaviorPolicyOut.from_row(row)


@router.delete("/agents/{agent_id}/policy", status_code=204)
async def delete_policy(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    await repo.delete_agent_policy(agent_id)
    return Response(status_code=204)
