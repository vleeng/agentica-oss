from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.runtime.factory import RuntimeFactory
from app.runtime.store import get_runtime_store
from app.schemas.agent import AgentDesign, AgentResponse, AgentSpec
from app.schemas.eval import EvalReport, FeedbackItem
from app.services.designer.design_generator import DesignGeneratorService
from app.services.evaluator.eval_engine import EvalEngineService
from app.services.optimizer.optimizer import OptimizerService
from app.services.selector.framework_selector import FrameworkSelectorService

router = APIRouter()
logger = logging.getLogger(__name__)

selector_svc  = FrameworkSelectorService()
designer_svc  = DesignGeneratorService()
eval_svc      = EvalEngineService()
optimizer_svc = OptimizerService()


# ── POST /spec ────────────────────────────────────────────────────────────────

@router.post("/spec", response_model=AgentDesign, status_code=201)
async def create_agent_from_spec(
    spec: AgentSpec,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> AgentDesign:
    ctx.require_developer()
    spec.tenant_id = ctx.tenant_id

    # Sprint 6: plan limits + rate limiting
    from app.core.plan_limits import plan_checker
    from app.core.rate_limiter import get_rate_limiter
    await plan_checker.check_can_create_agent(ctx.tenant_id)
    if spec.mode.value == "crew":
        await plan_checker.check_can_use_crew(ctx.tenant_id)
    if spec.rag and spec.rag.enabled:
        await plan_checker.check_can_use_rag(ctx.tenant_id)
    await get_rate_limiter().check(ctx.tenant_id, scope="spec")

    framework = await selector_svc.select(spec)
    design    = await designer_svc.generate(spec, framework)

    # Persistir en DB y en RuntimeStore
    await repo.create_agent(design)
    await get_runtime_store().save_design(str(design.agent_id), design)

    return design


# ── POST /{id}/build ──────────────────────────────────────────────────────────

@router.post("/{agent_id}/build", status_code=202)
async def build_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    ctx.require_developer()

    result = await get_runtime_store().get(agent_id)
    if result is None:
        raise HTTPException(404, "Design no encontrado — llamá primero a /spec")

    _, design = result
    build_id = await repo.create_build(agent_id, design.version)

    try:
        store = get_runtime_store()
        runtime = await RuntimeFactory().build(design)
        await store.save_runtime(agent_id, runtime, design)
        await repo.update_build(build_id, "ready")
        await repo.update_agent_status(agent_id, "testing")
    except Exception as e:
        await repo.update_build(build_id, "failed", error=str(e))
        raise HTTPException(500, f"Error en el build: {e}")

    return {
        "agent_id":  agent_id,
        "build_id":  build_id,
        "status":    "ready",
        "framework": design.framework.framework,
    }


# ── POST /{id}/invoke ─────────────────────────────────────────────────────────

class InvokeRequest(BaseModel):
    input: str = Field(..., min_length=1, max_length=8000)
    session_id: str = Field(default="", max_length=100)


@router.post("/{agent_id}/invoke", response_model=AgentResponse)
async def invoke_agent(
    agent_id: str,
    body: InvokeRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> AgentResponse:
    runtime, design = await _get_runtime(agent_id)
    session_id = body.session_id or f"{ctx.tenant_id}_{agent_id}_default"

    # Sprint 6: rate limiting por tenant
    from app.core.rate_limiter import get_rate_limiter
    await get_rate_limiter().check(ctx.tenant_id, scope="invoke")

    # Sprint 6: plan invocation limits
    from app.core.plan_limits import plan_checker
    await plan_checker.check_can_invoke(ctx.tenant_id)

    try:
        response = await asyncio.wait_for(
            runtime.invoke(body.input, session_id), timeout=120.0
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "Timeout — agente tardó más de 120s")
    except Exception as e:
        raise HTTPException(500, str(e))

    # Persistir conversación y billing
    try:
        conv_id = await repo.upsert_conversation(agent_id, session_id, "rest_api")
        await repo.save_message(conv_id, "user", body.input)
        await repo.save_message(conv_id, "assistant", response.output,
                                response.tokens_in, response.tokens_out)
        cost = response.tokens_in * 3e-6 + response.tokens_out * 15e-6
        await repo.record_billing_event(agent_id, conv_id,
                                        response.tokens_in, response.tokens_out, cost)
    except Exception as e:
        logger.warning(f"[INVOKE] Error al persistir conversación: {e}")

    return response


# ── WS /{id}/ws ───────────────────────────────────────────────────────────────

@router.websocket("/{agent_id}/ws")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "JSON inválido"})
                continue

            user_input = data.get("input", "").strip()
            session_id = data.get("session_id", f"ws_{agent_id}_{id(websocket)}")

            if not user_input:
                await websocket.send_json({"type": "error", "message": "Input vacío"})
                continue
                
            if len(user_input) > 8000:
                await websocket.send_json({"type": "error", "message": "Mensaje demasiado largo (máx 8000 caracteres)"})
                continue

            try:
                runtime, _ = await _get_runtime(agent_id)
            except HTTPException as e:
                await websocket.send_json({"type": "error", "message": e.detail})
                continue

            try:
                async for token in runtime.stream(user_input, session_id):
                    await websocket.send_json({"type": "token", "content": token})
                await websocket.send_json({"type": "done", "session_id": session_id})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        pass


# ── POST /{id}/eval ───────────────────────────────────────────────────────────

@router.post("/{agent_id}/eval", response_model=EvalReport)
async def eval_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> EvalReport:
    ctx.require_developer()
    _, design = await _get_runtime(agent_id)
    report = await eval_svc.run(design)

    build = await repo.get_latest_build(agent_id)
    build_id = build["build_id"] if build else None
    if build_id:
        await repo.save_eval_run(agent_id, build_id, report.model_dump())

    return report


class FeedbackRequest(BaseModel):
    feedback: list[FeedbackItem]


@router.post("/{agent_id}/eval/feedback", response_model=EvalReport)
async def eval_with_feedback(
    agent_id: str,
    body: FeedbackRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> EvalReport:
    ctx.require_developer()
    _, design = await _get_runtime(agent_id)
    return await eval_svc.run(design, human_feedback=body.feedback)


# ── POST /{id}/optimize ───────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    eval_report: EvalReport
    auto_rebuild: bool = False


@router.post("/{agent_id}/optimize")
async def optimize_agent(
    agent_id: str,
    body: OptimizeRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    ctx.require_developer()
    _, design = await _get_runtime(agent_id)

    updated_design, patch = await optimizer_svc.optimize(design, body.eval_report)

    if body.auto_rebuild:
        new_runtime = await RuntimeFactory().build(updated_design)
        await get_runtime_store().save_runtime(agent_id, new_runtime, updated_design)
        await repo.create_agent(updated_design)   # upsert nueva versión

    return {
        "agent_id":    agent_id,
        "new_version": updated_design.version,
        "patch": {
            "system_prompt_changed": patch.system_prompt is not None,
            "temperature":           patch.temperature,
            "max_tokens":            patch.max_tokens,
            "tools_added":           patch.tools_to_add,
            "tools_removed":         patch.tools_to_remove,
            "reasoning":             patch.reasoning,
            "confidence":            patch.confidence,
        },
        "rebuilt": body.auto_rebuild,
    }


# ── GET /{id}/design ──────────────────────────────────────────────────────────

@router.get("/{agent_id}/design", response_model=AgentDesign)
async def get_design(agent_id: str, ctx: CurrentContext) -> AgentDesign:
    result = await get_runtime_store().get(agent_id)
    if result is None:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")
    _, design = result
    return design


# ── GET /{id}/state ───────────────────────────────────────────────────────────

@router.get("/{agent_id}/state")
async def get_state(
    agent_id: str,
    ctx: CurrentContext,
    session_id: str = "default",
) -> dict:
    ctx.require_developer()
    runtime, design = await _get_runtime(agent_id)
    return {
        "agent_id":  agent_id,
        "framework": design.framework.framework,
        "mode":      design.spec.mode.value,
        "version":   design.version,
        "state":     runtime.get_state(session_id),
    }


# ── GET /{id}/history ─────────────────────────────────────────────────────────

@router.get("/{agent_id}/history")
async def get_history(
    agent_id: str,
    session_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> list[dict]:
    return await repo.get_conversation_history(agent_id, session_id)


# ── DELETE /{id}/session/{sid} ────────────────────────────────────────────────

@router.delete("/{agent_id}/session/{session_id}", status_code=204)
async def reset_session(agent_id: str, session_id: str, ctx: CurrentContext) -> None:
    runtime, _ = await _get_runtime(agent_id)
    runtime.reset(session_id)


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_runtime(agent_id: str) -> tuple:
    result = await get_runtime_store().get(agent_id)
    if result is None:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado — llamá a /spec primero")
    runtime, design = result
    if runtime is None:
        raise HTTPException(409, f"Agente sin build — llamá a /{agent_id}/build")
    return runtime, design
