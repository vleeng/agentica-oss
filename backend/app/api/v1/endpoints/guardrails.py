from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.schemas.guardrail import GuardrailRuleIn, GuardrailRuleOut

router = APIRouter()


@router.get("/agents/{agent_id}/guardrails", response_model=list[GuardrailRuleOut])
async def list_guardrails(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.list_guardrail_rules(agent_id)
    return [GuardrailRuleOut.from_row(r) for r in rows]


@router.post("/agents/{agent_id}/guardrails", response_model=GuardrailRuleOut, status_code=201)
async def create_guardrail(agent_id: str, body: GuardrailRuleIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "rule_type": body.rule_type,
        "condition_json": json.dumps(body.condition),
        "action": body.action,
        "priority": body.priority,
    }
    row = await repo.create_guardrail_rule(agent_id, data)
    return GuardrailRuleOut.from_row(row)


@router.put("/agents/{agent_id}/guardrails/{rule_id}", response_model=GuardrailRuleOut)
async def update_guardrail(agent_id: str, rule_id: str, body: GuardrailRuleIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    rules = await repo.list_guardrail_rules(agent_id)
    if not any(str(r["id"]) == rule_id for r in rules):
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    data = {
        "name": body.name,
        "rule_type": body.rule_type,
        "condition_json": json.dumps(body.condition),
        "action": body.action,
        "priority": body.priority,
    }
    row = await repo.update_guardrail_rule(rule_id, data)
    if not row:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return GuardrailRuleOut.from_row(row)


@router.patch("/agents/{agent_id}/guardrails/{rule_id}/toggle", response_model=GuardrailRuleOut)
async def toggle_guardrail(agent_id: str, rule_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    rules = await repo.list_guardrail_rules(agent_id)
    current = next((r for r in rules if str(r["id"]) == rule_id), None)
    if not current:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    row = await repo.toggle_guardrail_rule(rule_id, not current["is_active"])
    return GuardrailRuleOut.from_row(row)


@router.delete("/agents/{agent_id}/guardrails/{rule_id}", status_code=204)
async def delete_guardrail(agent_id: str, rule_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    rules = await repo.list_guardrail_rules(agent_id)
    if not any(str(r["id"]) == rule_id for r in rules):
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    deleted = await repo.delete_guardrail_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return Response(status_code=204)
