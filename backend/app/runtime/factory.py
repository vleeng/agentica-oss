from __future__ import annotations

from app.builders.crewai.builder import CrewAIAgentBuilder
from app.builders.langchain.builder import LangChainAgentBuilder
from app.runtime.base import AgentRuntime
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

        # Extraer LLM Key
        llm_provider = "openai" if "gpt" in design.spec.model_params.model else "anthropic"
        api_key = await self._get_llm_api_key(design.tenant_id, llm_provider, design.spec.model_params.llm_key_id)

        # Enriquecer el design con skills, MCPs y políticas asignadas al agente
        await self._enrich_design(design)

        if design.spec.mode == AgentMode.single:
            builder = LangChainAgentBuilder(
                redis_client=self._redis,
                session_factory=self._session_factory,
            )
            return await builder.build(design, api_key=api_key)

        elif design.spec.mode == AgentMode.crew:
            builder = CrewAIAgentBuilder(session_factory=self._session_factory)
            return await builder.build(design, api_key=api_key)

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

    async def _get_llm_api_key(self, tenant_id: str, provider: str, key_id: str | None) -> str:
        from app.db.session import PublicSessionFactory
        from app.core.security import decrypt_provider_key
        from sqlalchemy import text
        
        async with PublicSessionFactory() as db:
            if key_id:
                res = await db.execute(
                    text("SELECT encrypted_key FROM llm_provider_keys WHERE id = :id::uuid AND tenant_id = :tid::uuid"),
                    {"id": key_id, "tid": tenant_id}
                )
            else:
                res = await db.execute(
                    text("SELECT encrypted_key FROM llm_provider_keys WHERE tenant_id = :tid::uuid AND provider = :prov AND is_default = TRUE"),
                    {"tid": tenant_id, "prov": provider}
                )
            row = res.fetchone()
            
        if not row:
            import os
            # Fallback a global env vars
            if provider == "openai" and "OPENAI_API_KEY" in os.environ:
                return os.environ["OPENAI_API_KEY"]
            if provider == "anthropic" and "ANTHROPIC_API_KEY" in os.environ:
                return os.environ["ANTHROPIC_API_KEY"]
            
            raise ValueError(f"No hay una llave configurada para el proveedor {provider} en este tenant y no hay llaves globales.")

        return decrypt_provider_key(row.encrypted_key)
