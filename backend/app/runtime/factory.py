from __future__ import annotations

from app.builders.crewai.builder import CrewAIAgentBuilder
from app.builders.langchain.builder import LangChainAgentBuilder
from app.runtime.base import AgentRuntime
from app.schemas.agent import AgentDesign, AgentMode


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
        # Extraer LLM Key 
        llm_provider = "openai" if "gpt" in design.spec.model_params.model else "anthropic"
        api_key = await self._get_llm_api_key(design.tenant_id, llm_provider, design.spec.model_params.llm_key_id)

        if design.spec.mode == AgentMode.single:
            builder = LangChainAgentBuilder(
                redis_client=self._redis,
                session_factory=self._session_factory,
            )
            return await builder.build(design, api_key=api_key)

        elif design.spec.mode == AgentMode.crew:
            builder = CrewAIAgentBuilder()
            return await builder.build(design, api_key=api_key)

        else:
            raise ValueError(f"AgentMode desconocido: {design.spec.mode}")

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
