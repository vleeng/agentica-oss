from __future__ import annotations

from app.core.config import get_settings
from app.schemas.agent import AgentMode, AgentSpec, CrewProcess, FrameworkSelection
from app.services.llm_client import TextGenerationClient

settings = get_settings()

# Modelos que soportan function calling nativo (mejor performance que ReAct)
FUNCTION_CALLING_MODELS = {
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
}


class FrameworkSelectorService:
    """
    Selecciona automáticamente el framework según el AgentSpec.
    El usuario nunca ve LangChain ni CrewAI — solo ve 'agente simple' o 'equipo'.
    """

    def __init__(self):
        self._client = TextGenerationClient()

    async def select(self, spec: AgentSpec) -> FrameworkSelection:
        framework = "langchain" if spec.mode == AgentMode.single else "crewai"
        agent_type = None
        process = None
        complexity = self._estimate_complexity(spec)

        if framework == "langchain":
            agent_type = (
                "openai_functions"
                if spec.model_params.model in FUNCTION_CALLING_MODELS
                else "react"
            )
        else:
            process = spec.process or CrewProcess.sequential

        justification = await self._generate_justification(spec, framework, agent_type, complexity)

        return FrameworkSelection(
            framework=framework,
            agent_type=agent_type,
            process=process,
            justification=justification,
            estimated_complexity=complexity,
        )

    def _estimate_complexity(self, spec: AgentSpec) -> str:
        if spec.mode == AgentMode.crew:
            if len(spec.agents) > 4 or spec.process == CrewProcess.hierarchical:
                return "high"
            if len(spec.agents) > 2:
                return "medium"
            return "medium"

        # Single agent
        tool_count = len(spec.tools)
        has_rag = spec.rag.enabled
        has_memory = spec.memory.type.value != "none"

        score = tool_count + (2 if has_rag else 0) + (1 if has_memory else 0)
        if score <= 2:
            return "low"
        if score <= 5:
            return "medium"
        return "high"

    async def _generate_justification(
        self,
        spec: AgentSpec,
        framework: str,
        agent_type: str | None,
        complexity: str,
    ) -> str:
        prompt = f"""Explicá en 2-3 oraciones, en español y en lenguaje simple (sin mencionar LangChain ni CrewAI), 
por qué este agente fue configurado como {'agente simple con herramientas' if framework == 'langchain' else 'equipo de agentes con roles'}.

Objetivo del agente: {spec.goal}
Modo: {spec.mode.value}
Herramientas: {[t.name for t in spec.tools] if spec.tools else 'ninguna'}
Agentes/roles: {[a.role for a in spec.agents] if spec.agents else 'N/A'}
Complejidad estimada: {complexity}
{'Tipo de razonamiento: ' + agent_type if agent_type else ''}

Respondé directamente la justificación, sin saludos ni intro."""

        return await self._client.complete(prompt, max_tokens=200, temperature=settings.builder_temperature)
