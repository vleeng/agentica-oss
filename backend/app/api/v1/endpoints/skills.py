from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Response

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.schemas.skills import SkillIn, SkillOut

router = APIRouter()


@router.get("/skills/", response_model=list[SkillOut])
async def list_skills(repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.list_skills()
    return [SkillOut.from_row(r) for r in rows]


@router.post("/skills/", response_model=SkillOut, status_code=201)
async def create_skill(body: SkillIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "description": body.description,
        "objective": body.objective,
        "usage_conditions": body.usage_conditions,
        "tools_json": json.dumps([t.model_dump() for t in body.tools]),
        "procedure": body.procedure,
        "quality_rules": body.quality_rules,
        "output_format": body.output_format,
        "guardrails_json": json.dumps(body.guardrails),
    }
    row = await repo.create_skill(data)
    return SkillOut.from_row(row)


@router.get("/skills/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: str, repo: TenantRepo, ctx: CurrentContext):
    row = await repo.get_skill(skill_id)
    if not row:
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    return SkillOut.from_row(row)


@router.put("/skills/{skill_id}", response_model=SkillOut)
async def update_skill(skill_id: str, body: SkillIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "description": body.description,
        "objective": body.objective,
        "usage_conditions": body.usage_conditions,
        "tools_json": json.dumps([t.model_dump() for t in body.tools]),
        "procedure": body.procedure,
        "quality_rules": body.quality_rules,
        "output_format": body.output_format,
        "guardrails_json": json.dumps(body.guardrails),
    }
    row = await repo.update_skill(skill_id, data)
    if not row:
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    return SkillOut.from_row(row)


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    deleted = await repo.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    return Response(status_code=204)


# ── Asignación a agentes ──────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/skills", response_model=list[SkillOut])
async def get_agent_skills(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.get_agent_skills(agent_id)
    return [SkillOut.from_row(r) for r in rows]


@router.post("/agents/{agent_id}/skills/{skill_id}", status_code=204)
async def assign_skill(agent_id: str, skill_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    skill = await repo.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    await repo.assign_skill_to_agent(agent_id, skill_id)
    return Response(status_code=204)


@router.delete("/agents/{agent_id}/skills/{skill_id}", status_code=204)
async def unassign_skill(agent_id: str, skill_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    await repo.unassign_skill_from_agent(agent_id, skill_id)
    return Response(status_code=204)
