from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.api.deps import TenantRepo
from app.core.security import CurrentContext, RequestContext, decode_access_token
from app.runtime.factory import RuntimeFactory
from app.runtime.llm import infer_provider, qualify_model_name
from app.runtime.store import get_runtime_store
from app.schemas.agent import (
    AgentDesign,
    AgentResponse,
    AgentSpec,
    GraphBlueprint,
    GraphUpdateRequest,
    GraphUpdateResponse,
    GraphValidationReport,
    ModelParams,
)
from app.schemas.eval import EvalReport, FeedbackItem
from app.services.designer.graph_validator import normalize_graph_blueprint, validate_graph_blueprint
from app.services.model_catalog import calculate_model_cost, estimate_usage_tokens, resolve_model_pricing
from app.services.designer.design_generator import DesignGeneratorService
from app.services.evaluator.eval_engine import EvalEngineService
from app.services.optimizer.optimizer import OptimizerService
from app.services.selector.framework_selector import FrameworkSelectorService

router = APIRouter()
logger = logging.getLogger(__name__)

selector_svc = FrameworkSelectorService()
designer_svc = DesignGeneratorService()
eval_svc = EvalEngineService()
optimizer_svc = OptimizerService()

REST_INVOKE_TIMEOUT_SECONDS = 240.0
WS_INVOKE_TIMEOUT_SECONDS = 180.0


@router.post("/spec", response_model=AgentDesign, status_code=201)
async def create_agent_from_spec(
    spec: AgentSpec,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> AgentDesign:
    ctx.require_developer()
    spec.tenant_id = ctx.tenant_id
    _normalize_single_agent_spec(spec)

    from app.core.plan_limits import plan_checker
    from app.core.rate_limiter import get_rate_limiter

    await plan_checker.check_can_create_agent(ctx.tenant_id)
    if spec.mode.value == "crew":
        await plan_checker.check_can_use_crew(ctx.tenant_id)
    if spec.rag and spec.rag.enabled:
        await plan_checker.check_can_use_rag(ctx.tenant_id)
    await get_rate_limiter().check(ctx.tenant_id, scope="spec")

    framework = await selector_svc.select(spec)
    design = await designer_svc.generate(spec, framework)

    await repo.create_agent(design)
    await get_runtime_store().save_design(str(design.agent_id), design)

    return design


def _normalize_single_agent_spec(spec: AgentSpec) -> None:
    if spec.mode.value != "single" or spec.single_agent_mode.value != "direct":
        return

    spec.tools = []
    spec.rag.enabled = False
    spec.rag.sources = []


@router.post("/{agent_id}/build", status_code=202)
async def build_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    ctx.require_human_user()
    ctx.require_developer()

    design = await _restore_design(agent_id, ctx, repo)
    build_id = await repo.create_build(agent_id, design.version)

    try:
        store = get_runtime_store()
        runtime = await RuntimeFactory(redis_client=store.redis_client).build(design)
        design.status = "testing"
        await store.save_runtime(agent_id, runtime, design)
        await repo.update_build(build_id, "ready")
        await repo.update_agent_status(agent_id, "testing")
    except Exception as exc:
        await repo.update_build(build_id, "failed", error=str(exc))
        raise HTTPException(500, f"Error en el build: {exc}")

    return {
        "agent_id": agent_id,
        "build_id": build_id,
        "status": "ready",
        "framework": design.framework.framework,
    }


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
    runtime, design = await _get_runtime(agent_id, ctx, repo)
    session_id = body.session_id or f"{ctx.tenant_id}_{agent_id}_default"

    from app.core.rate_limiter import get_rate_limiter
    from app.core.plan_limits import plan_checker

    await get_rate_limiter().check(ctx.tenant_id, scope="invoke")
    await plan_checker.check_can_invoke(ctx.tenant_id)

    try:
        response = await asyncio.wait_for(runtime.invoke(body.input, session_id), timeout=REST_INVOKE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(504, f"Timeout - el agente tardo mas de {int(REST_INVOKE_TIMEOUT_SECONDS)}s")
    except Exception as exc:
        raise HTTPException(500, _format_runtime_error(exc))

    try:
        await _persist_usage_event(
            repo=repo,
            agent_id=agent_id,
            ctx=ctx,
            design=design,
            session_id=session_id,
            channel="rest_api",
            user_input=body.input,
            output=response.output,
            reported_tokens_in=response.tokens_in,
            reported_tokens_out=response.tokens_out,
        )
    except Exception as exc:
        logger.warning("[INVOKE] Error al persistir conversacion: %s", exc)

    return response


@router.websocket("/{agent_id}/ws")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    ctx = await _get_ws_context(websocket)
    if ctx is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "JSON invalido"})
                continue

            user_input = data.get("input", "").strip()
            session_id = data.get("session_id", f"ws_{agent_id}_{id(websocket)}")

            if not user_input:
                await websocket.send_json({"type": "error", "message": "Input vacio"})
                continue

            if len(user_input) > 8000:
                await websocket.send_json({"type": "error", "message": "Mensaje demasiado largo (max 8000 caracteres)"})
                continue

            try:
                from app.core.rate_limiter import get_rate_limiter
                from app.core.plan_limits import plan_checker

                await get_rate_limiter().check(ctx.tenant_id, scope="invoke")
                await plan_checker.check_can_invoke(ctx.tenant_id)
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "message": str(exc.detail)})
                continue

            try:
                runtime, _design = await _get_runtime(agent_id, ctx)
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "message": exc.detail})
                continue

            try:
                async def _do_stream() -> tuple[str, int, int]:
                    runtime.set_progress_callback(_make_ws_progress_sender(websocket))
                    collected: list[str] = []
                    try:
                        async for token in runtime.stream(user_input, session_id):
                            await websocket.send_json({"type": "token", "content": token})
                            collected.append(token)

                        if collected:
                            return "".join(collected).strip(), 0, 0

                        logger.warning("[WS] stream yielded no tokens for agent %s - falling back to invoke", agent_id)
                        response = await asyncio.wait_for(runtime.invoke(user_input, session_id), timeout=WS_INVOKE_TIMEOUT_SECONDS)
                        if response.output:
                            await websocket.send_json({"type": "token", "content": response.output})
                        return response.output, response.tokens_in, response.tokens_out
                    finally:
                        runtime.set_progress_callback(None)

                output, reported_tokens_in, reported_tokens_out = await asyncio.wait_for(_do_stream(), timeout=WS_INVOKE_TIMEOUT_SECONDS)
                await _persist_usage_event(
                    repo=None,
                    agent_id=agent_id,
                    ctx=ctx,
                    design=_design,
                    session_id=session_id,
                    channel="web_chat",
                    user_input=user_input,
                    output=output,
                    reported_tokens_in=reported_tokens_in,
                    reported_tokens_out=reported_tokens_out,
                )
                await websocket.send_json({"type": "done", "session_id": session_id})
            except asyncio.TimeoutError:
                logger.warning("[WS] stream timed out after %ss for agent %s", int(WS_INVOKE_TIMEOUT_SECONDS), agent_id)
                await websocket.send_json({
                    "type": "error",
                    "message": (
                        f"El agente tardo demasiado en responder "
                        f"(timeout {int(WS_INVOKE_TIMEOUT_SECONDS)}s). "
                        "Probá con un modelo mas rapido o una consulta mas corta."
                    ),
                })
            except Exception as exc:
                logger.exception("[WS] error during stream for agent %s: %s", agent_id, exc)
                await websocket.send_json({"type": "error", "message": _format_runtime_error(exc)})

    except WebSocketDisconnect:
        pass


@router.post("/{agent_id}/eval", response_model=EvalReport)
async def eval_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> EvalReport:
    ctx.require_human_user()
    ctx.require_developer()
    _, design = await _get_runtime(agent_id, ctx, repo)
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
    ctx.require_human_user()
    ctx.require_developer()
    _, design = await _get_runtime(agent_id, ctx, repo)
    return await eval_svc.run(design, human_feedback=body.feedback)


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
    ctx.require_human_user()
    ctx.require_developer()
    _, design = await _get_runtime(agent_id, ctx, repo)

    updated_design, patch = await optimizer_svc.optimize(design, body.eval_report)

    if body.auto_rebuild:
        store = get_runtime_store()
        new_runtime = await RuntimeFactory(redis_client=store.redis_client).build(updated_design)
        updated_design.status = "testing"
        await store.save_runtime(agent_id, new_runtime, updated_design)
        await repo.create_agent(updated_design)

    return {
        "agent_id": agent_id,
        "new_version": updated_design.version,
        "patch": {
            "system_prompt_changed": patch.system_prompt is not None,
            "temperature": patch.temperature,
            "max_tokens": patch.max_tokens,
            "tools_added": patch.tools_to_add,
            "tools_removed": patch.tools_to_remove,
            "reasoning": patch.reasoning,
            "confidence": patch.confidence,
        },
        "rebuilt": body.auto_rebuild,
    }


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    llm_key_id: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(None, ge=256, le=8192)


class ValidateGraphRequest(BaseModel):
    graph_blueprint: GraphBlueprint


@router.put("/{agent_id}", response_model=AgentDesign)
async def update_agent(
    agent_id: str,
    body: UpdateAgentRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> AgentDesign:
    ctx.require_human_user()
    ctx.require_developer()
    await _assert_agent_access(agent_id, ctx, repo)

    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(400, "No hay campos para actualizar")
    if body.model and "provider" not in patch:
        patch["provider"] = infer_provider(
            ModelParams(
                model=body.model,
                temperature=body.temperature if body.temperature is not None else 0.3,
                max_tokens=body.max_tokens if body.max_tokens is not None else 2048,
                top_p=1.0,
            )
        )
    if body.model:
        provider_for_model = patch.get("provider") or body.provider
        if provider_for_model:
            patch["model"] = qualify_model_name(body.model, provider_for_model)

    updated_dict = await repo.update_agent_core(agent_id, patch)
    if not updated_dict:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")

    new_design = AgentDesign.model_validate(updated_dict)
    store = get_runtime_store()
    await store.save_design(agent_id, new_design)

    try:
        runtime = await RuntimeFactory(redis_client=store.redis_client).build(new_design)
        new_design.status = "testing"
        await store.save_runtime(agent_id, runtime, new_design)
        await repo.update_agent_status(agent_id, "testing")
    except Exception as exc:
        logger.warning("[UPDATE] Rebuild fallido tras edicion: %s", exc)

    return new_design


@router.post("/{agent_id}/graph/validate", response_model=GraphValidationReport)
async def validate_agent_graph(
    agent_id: str,
    body: ValidateGraphRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> GraphValidationReport:
    ctx.require_human_user()
    ctx.require_developer()
    design = await _restore_design(agent_id, ctx, repo)
    normalized_graph = normalize_graph_blueprint(design, body.graph_blueprint)
    return validate_graph_blueprint(design, normalized_graph)


@router.put("/{agent_id}/graph", response_model=GraphUpdateResponse)
async def update_agent_graph(
    agent_id: str,
    body: GraphUpdateRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> GraphUpdateResponse:
    ctx.require_human_user()
    ctx.require_developer()
    design = await _restore_design(agent_id, ctx, repo)

    normalized_graph = normalize_graph_blueprint(design, body.graph_blueprint)
    validation = validate_graph_blueprint(design, normalized_graph)
    if not validation.ok:
        raise HTTPException(status_code=400, detail=validation.model_dump())

    mermaid = design.mermaid_diagram
    if body.auto_regenerate_mermaid:
        mermaid = designer_svc.blueprint_to_mermaid(normalized_graph, design.spec)

    updated_dict = await repo.update_agent_graph(
        agent_id,
        graph_blueprint=normalized_graph.as_dict(),
        mermaid_diagram=mermaid,
    )
    if not updated_dict:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")

    updated_design = AgentDesign.model_validate(updated_dict)
    store = get_runtime_store()
    await store.save_runtime(agent_id, None, updated_design)

    return GraphUpdateResponse(
        graph_blueprint=normalized_graph,
        mermaid_diagram=mermaid,
        validation=validation,
    )


@router.post("/{agent_id}/deploy")
async def deploy_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    ctx.require_human_user()
    ctx.require_developer()
    _, design = await _get_runtime(agent_id, ctx, repo)
    await repo.update_agent_status(agent_id, "deployed")

    design.status = "deployed"
    store = get_runtime_store()
    await store.save_design(agent_id, design)

    logger.info("[DEPLOY] agent_id=%s tenant=%s -> deployed", agent_id, ctx.tenant_id)

    return {
        "agent_id": agent_id,
        "status": "deployed",
        "version": design.version,
        "message": "Agente desplegado correctamente.",
    }


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> Response:
    ctx.require_human_user()
    ctx.require_developer()
    await _assert_agent_access(agent_id, ctx, repo)
    deleted = await repo.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")
    await get_runtime_store().delete(agent_id)
    return Response(status_code=204)


@router.get("/{agent_id}/design", response_model=AgentDesign)
async def get_design(agent_id: str, ctx: CurrentContext, repo: TenantRepo) -> AgentDesign:
    ctx.require_human_user()
    agent = await _assert_agent_access(agent_id, ctx, repo)
    result = await get_runtime_store().get(agent_id)
    if result is not None:
        _, design = result
        return design

    design = _materialize_design(agent["design"], agent_id=agent_id, tenant_id=ctx.tenant_id, status=agent.get("status"))
    await get_runtime_store().save_design(agent_id, design)
    logger.info("[RuntimeHydration] design restored from db agent_id=%s tenant_id=%s via=get_design", agent_id, ctx.tenant_id)
    return design


@router.get("/{agent_id}/state")
async def get_state(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
    session_id: str = "default",
) -> dict:
    ctx.require_human_user()
    ctx.require_developer()
    runtime, design = await _get_runtime(agent_id, ctx, repo)
    return {
        "agent_id": agent_id,
        "framework": design.framework.framework,
        "mode": design.spec.mode.value,
        "version": design.version,
        "state": runtime.get_state(session_id),
    }


@router.get("/{agent_id}/history")
async def get_history(
    agent_id: str,
    session_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> list[dict]:
    ctx.require_human_user()
    await _assert_agent_access(agent_id, ctx, repo)
    return await repo.get_conversation_history(agent_id, session_id)


@router.delete("/{agent_id}/session/{session_id}", status_code=204)
async def reset_session(agent_id: str, session_id: str, ctx: CurrentContext, repo: TenantRepo) -> Response:
    ctx.require_human_user()
    ctx.require_developer()
    runtime, _ = await _get_runtime(agent_id, ctx, repo)
    runtime.reset(session_id)
    return Response(status_code=204)


async def _assert_agent_access(agent_id: str, ctx: RequestContext, repo: TenantRepo) -> dict:
    if ctx.is_agent_user and ctx.agent_id != agent_id:
        raise HTTPException(403, "La API key solo puede acceder a su agente asignado")
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")
    return agent


def _materialize_design(raw_design: Any, *, agent_id: str, tenant_id: str, status: str | None = None) -> AgentDesign:
    if isinstance(raw_design, str):
        design_dict = json.loads(raw_design)
    else:
        design_dict = dict(raw_design or {})

    design_dict.setdefault("schema_version", 1)
    design_dict["agent_id"] = design_dict.get("agent_id") or agent_id
    design_dict["tenant_id"] = design_dict.get("tenant_id") or tenant_id
    if status:
        design_dict["status"] = status

    design = AgentDesign.model_validate(design_dict)
    _normalize_design_models(design)
    try:
        blueprint = GraphBlueprint.model_validate(design.graph_blueprint or {})
        normalized_blueprint = normalize_graph_blueprint(design, blueprint)
        design.graph_blueprint = normalized_blueprint.as_dict()
        design.mermaid_diagram = designer_svc.blueprint_to_mermaid(normalized_blueprint, design.spec)
    except Exception:
        pass
    return design


async def _restore_design(agent_id: str, ctx: RequestContext, repo: TenantRepo) -> AgentDesign:
    agent = await _assert_agent_access(agent_id, ctx, repo)
    design = _materialize_design(agent["design"], agent_id=agent_id, tenant_id=ctx.tenant_id, status=agent.get("status"))
    await get_runtime_store().save_design(agent_id, design)
    logger.info("[RuntimeHydration] design restored from db agent_id=%s tenant_id=%s", agent_id, ctx.tenant_id)
    return design


async def _get_runtime(agent_id: str, ctx: RequestContext, repo: TenantRepo | None = None) -> tuple:
    if ctx.is_agent_user and ctx.agent_id != agent_id:
        raise HTTPException(403, "La API key solo puede invocar su agente asignado")

    store = get_runtime_store()
    result = await store.get(agent_id)

    if result is None:
        if repo is None:
            from app.db.repository import AgentRepository
            from app.db.session import get_tenant_session_factory

            session_factory = get_tenant_session_factory(ctx.tenant_id)
            async with session_factory() as session:
                repo = AgentRepository(session)
                design = await _restore_design(agent_id, ctx, repo)
        else:
            design = await _restore_design(agent_id, ctx, repo)
        result = await store.get(agent_id)
        if result is None:
            result = (None, design)
    elif repo is not None:
        await _assert_agent_access(agent_id, ctx, repo)

    if result is None:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado - llama a /spec primero")

    runtime, design = result
    if str(design.tenant_id) != str(ctx.tenant_id):
        raise HTTPException(403, "Agente no autorizado")

    normalized = _normalize_design_models(design)
    if normalized:
        await store.save_design(agent_id, design)

    if runtime is None:
        try:
            logger.info("[RuntimeHydration] rebuilding runtime on demand agent_id=%s tenant_id=%s", agent_id, ctx.tenant_id)
            runtime = await RuntimeFactory(redis_client=store.redis_client).build(design)
            await store.save_runtime(agent_id, runtime, design)
        except Exception as exc:
            logger.exception("[RuntimeHydration] runtime rebuild failed agent_id=%s tenant_id=%s error=%s", agent_id, ctx.tenant_id, exc)
            raise HTTPException(409, f"Agente sin build - llama a /{agent_id}/build")

    return runtime, design


async def _get_ws_context(websocket: WebSocket) -> RequestContext | None:
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("api_key")

    auth_header = websocket.headers.get("authorization")
    if not token and auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]

    if token:
        try:
            payload = decode_access_token(token)
            return RequestContext(
                tenant_id=payload["tenant_id"],
                user_id=payload["sub"],
                role=payload["role"],
            )
        except Exception:
            return None

    if api_key:
        try:
            from app.api.v1.endpoints.api_keys import resolve_api_key

            result = await resolve_api_key(api_key)
            if result and "invoke" in result.get("scopes", []):
                return RequestContext(
                    tenant_id=result["tenant_id"],
                    user_id="api_key",
                    role="agent_user",
                    agent_id=result.get("agent_id"),
                )
        except Exception:
            return None

    return None


async def _persist_usage_event(
    *,
    repo,
    agent_id: str,
    ctx: RequestContext,
    design: AgentDesign,
    session_id: str,
    channel: str,
    user_input: str,
    output: str,
    reported_tokens_in: int,
    reported_tokens_out: int,
) -> None:
    async def _write_usage(usage_repo) -> None:
        tokens_in, tokens_out = estimate_usage_tokens(
            user_input,
            output,
            reported_tokens_in=reported_tokens_in,
            reported_tokens_out=reported_tokens_out,
        )
        pricing = await resolve_model_pricing(ctx.tenant_id, design.spec.model_params)
        cost = calculate_model_cost(tokens_in, tokens_out, pricing)
        conv_id = await usage_repo.upsert_conversation(agent_id, session_id, channel, user_ref=ctx.user_id)
        await usage_repo.save_message(conv_id, "user", user_input)
        await usage_repo.save_message(conv_id, "assistant", output, tokens_in, tokens_out)
        await usage_repo.record_billing_event(agent_id, conv_id, tokens_in, tokens_out, cost)

    if repo is not None:
        await _write_usage(repo)
        return

    from app.db.repository import AgentRepository
    from app.db.session import get_tenant_session_factory

    session_factory = get_tenant_session_factory(ctx.tenant_id)
    async with session_factory() as session:
        await _write_usage(AgentRepository(session))


def _normalize_design_models(design: AgentDesign) -> bool:
    changed = False

    base_params = design.spec.model_params
    base_provider = base_params.provider or infer_provider(base_params)
    qualified_base_model = qualify_model_name(base_params.model, base_provider)
    if qualified_base_model != base_params.model:
        base_params.model = qualified_base_model
        changed = True
    if base_params.provider != base_provider:
        base_params.provider = base_provider
        changed = True

    if design.spec.manager_model:
        qualified_manager_model = qualify_model_name(design.spec.manager_model, base_provider)
        if qualified_manager_model != design.spec.manager_model:
            design.spec.manager_model = qualified_manager_model
            changed = True

    for role in design.spec.agents:
        if not role.model_params:
            continue
        role_provider = role.model_params.provider or infer_provider(role.model_params)
        qualified_role_model = qualify_model_name(role.model_params.model, role_provider)
        if qualified_role_model != role.model_params.model:
            role.model_params.model = qualified_role_model
            changed = True
        if role.model_params.provider != role_provider:
            role.model_params.provider = role_provider
            changed = True

    return changed


def _format_runtime_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()

    if "ratelimiterror" in lowered or "error code: 429" in lowered or "temporarily rate-limited upstream" in lowered:
        return (
            "El proveedor del modelo rechazo la solicitud por limite temporal de uso. "
            "Si estas usando un modelo free de OpenRouter, probá de nuevo en unos minutos "
            "o cambiá a un modelo/credencial con mas capacidad."
        )

    if "invalid_api_key" in lowered or "incorrect api key" in lowered:
        return "La credencial del proveedor LLM no es valida para este modelo."

    return message


def _make_ws_progress_sender(websocket: WebSocket):
    async def _send(payload: dict) -> None:
        phase = str(payload.get("phase") or "").strip().lower()
        message_type = "trace" if phase == "trace" else "status"
        await websocket.send_json({"type": message_type, **payload})

    return _send
