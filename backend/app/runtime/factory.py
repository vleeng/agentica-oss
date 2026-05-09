from __future__ import annotations

from app.builders.crewai.builder import CrewAIAgentBuilder
from app.builders.langchain.builder import LangChainAgentBuilder
from app.runtime.base import AgentRuntime
from app.runtime.llm import LLMConfig, canonical_provider, infer_provider, resolve_base_url
from app.schemas.agent import AgentDesign, AgentMode
from app.components.skills.skill_loader import expand_skill
from app.components.mcp.mcp_client import get_agent_mcp_tools
from app.components.policies.policy_renderer import render_policy


class RuntimeFactory:
    """
    Punto único de entrada para construir cualquier AgentRuntime.
    El caller nunca necesita saber qué framework se usa.

    Uso:
        factory = RuntimeFactory(redis_client=redis, session_factory=db_factory)
        runtime = await factory.build(design)
        response = await runtime.invoke("Hola", session_id="s_123")
    """

    def __init__(self, redis_client=None, session_factory=None):
        self._redis = redis_client
        self._session_factory = session_factory

    async def build(self, design: AgentDesign) -> AgentRuntime:
        design = design.model_copy(deep=True)

        if self._session_factory is None:
            from app.db.session import get_tenant_session_factory
            self._session_factory = get_tenant_session_factory(design.tenant_id)

        # Extraer configuración LLM explícita o inferida por modelo/proveedor.
        llm_config = await self._get_llm_config(design.tenant_id, design.spec.model_params)

        # Enriquecer el design con skills, MCPs y políticas asignadas al agente
        await self._enrich_design(design)

        if design.spec.mode == AgentMode.single:
            builder = LangChainAgentBuilder(
                redis_client=self._redis,
                session_factory=self._session_factory,
            )
            return await builder.build(design, llm_config=llm_config)

        elif design.spec.mode == AgentMode.crew:
            builder = CrewAIAgentBuilder(
                redis_client=self._redis,
                session_factory=self._session_factory,
            )
            return await builder.build(design, llm_config=llm_config)

        else:
            raise ValueError(f"AgentMode desconocido: {design.spec.mode}")

    async def _enrich_design(self, design: AgentDesign) -> None:
        """
        Carga skills, MCPs y policy asignados al agente e inyecta sus contribuciones
        directamente en el design antes de pasarlo al builder.
        """
        if not self._session_factory:
            return

        agent_id = str(design.agent_id)

        try:
            async with self._session_factory() as session:
                from app.db.repository import AgentRepository
                repo = AgentRepository(session)

                # 1. Skills → inyectar tools + fragmentos de prompt
                skills = await repo.get_agent_skills(agent_id)
                for skill in skills:
                    extra_tools, prompt_fragment = expand_skill(skill)
                    design.spec.tools.extend(extra_tools)
                    design.system_prompt += f"\n{prompt_fragment}"

                # 2. MCP servers → inyectar tools descubiertas (se pasan como _mcp_tools al builder)
                mcp_servers = await repo.get_agent_mcp_servers(agent_id)
                if mcp_servers:
                    mcp_tools = await get_agent_mcp_tools(mcp_servers)
                    # Guardamos en design para que el builder pueda accederlas
                    if not hasattr(design, "_extra_lc_tools"):
                        design.__dict__["_extra_lc_tools"] = []
                    design.__dict__["_extra_lc_tools"].extend(mcp_tools)

                # 3. Behavior policy → appendear al system_prompt
                policy = await repo.get_agent_policy(agent_id)
                if policy:
                    design.system_prompt += render_policy(policy)

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"_enrich_design failed for agent {agent_id}: {e}")

    async def _get_llm_config(self, tenant_id: str, params) -> LLMConfig:
        provider = infer_provider(params)
        api_key, key_provider = await self._get_llm_api_key(tenant_id, provider, params.llm_key_id)
        provider = canonical_provider(key_provider or provider)
        return LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=resolve_base_url(provider, params.base_url),
        )

    async def _get_llm_api_key(self, tenant_id: str, provider: str, key_id: str | None) -> tuple[str, str | None]:
        from app.db.session import PublicSessionFactory
        from app.core.security import decrypt_provider_key
        from sqlalchemy import text
        
        async with PublicSessionFactory() as db:
            if key_id:
                res = await db.execute(
                    text("SELECT provider, encrypted_key FROM llm_provider_keys WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tid AS uuid)"),
                    {"id": key_id, "tid": tenant_id}
                )
            else:
                res = await db.execute(
                    text("SELECT provider, encrypted_key FROM llm_provider_keys WHERE tenant_id = CAST(:tid AS uuid) AND provider = :prov AND is_default = TRUE"),
                    {"tid": tenant_id, "prov": provider}
                )
            row = res.fetchone()
            if not row and not key_id and provider == "openrouter":
                res = await db.execute(
                    text("SELECT provider, encrypted_key FROM llm_provider_keys WHERE tenant_id = CAST(:tid AS uuid) AND provider = 'google' AND is_default = TRUE"),
                    {"tid": tenant_id}
                )
                row = res.fetchone()
            
        if not row:
            import os
            # Fallback a global env vars (solo si no están vacías)
            def _env(name: str) -> str | None:
                v = os.environ.get(name, "").strip()
                return v if v else None

            if provider == "openai":
                key = _env("OPENAI_API_KEY")
                if key:
                    return key, None
            if provider == "anthropic":
                key = _env("ANTHROPIC_API_KEY")
                if key:
                    return key, None
            env_name = f"{provider.upper()}_API_KEY"
            key = _env(env_name)
            if key:
                return key, None

            raise ValueError(
                f"No hay una llave API configurada para el proveedor '{provider}'. "
                f"Agregala en la Bóveda IA del tenant o configurá {env_name} en el servidor."
            )

        return decrypt_provider_key(row.encrypted_key), row.provider
