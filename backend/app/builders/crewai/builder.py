from __future__ import annotations

from app.components.memory.adapters import (
    InMemoryAdapter,
    PostgreSQLAdapter,
    RedisAdapter,
)
from app.components.tools.builtin import get_tool
from app.runtime.crewai.runtime import CrewAIRuntime
from app.runtime.llm import (
    LLMConfig,
    bind_crewai_call_adapter,
    canonical_provider,
    infer_provider,
    qualify_crewai_model_name,
    resolve_base_url,
)
from app.schemas.agent import AgentDesign, AgentRoleSpec, CrewProcess, MemoryType


class CrewAIAgentBuilder:
    """
    Toma un AgentDesign con mode='crew' y produce un CrewAIRuntime.
    Mapea AgentRoleSpec → crewai.Agent y genera las Tasks
    desde el graph_blueprint del design.
    """

    def __init__(self, redis_client=None, session_factory=None):
        self._redis = redis_client
        self._session_factory = session_factory

    async def build(self, design: AgentDesign, api_key: str = "", llm_config: LLMConfig | None = None) -> CrewAIRuntime:
        from crewai import Crew, Process

        spec = design.spec
        llm_config = llm_config or LLMConfig(provider="anthropic", api_key=api_key)
        llm = self._make_llm(spec.model_params, llm_config)

        # 1. Construir agentes desde los roles del spec
        crew_agents = {}
        for role_spec in spec.agents:
            agent = await self._build_agent_async(role_spec, llm, llm_config, design.tenant_id)
            crew_agents[role_spec.name] = agent

        # 2. Construir tasks desde el graph_blueprint
        tasks = self._build_tasks(design, crew_agents)

        # 3. Determinar proceso
        process_map = {
            CrewProcess.sequential:    Process.sequential,
            CrewProcess.hierarchical:  Process.hierarchical,
            CrewProcess.parallel:      Process.sequential,  # CrewAI no tiene parallel nativo, usamos sequential con delegation
        }
        process = process_map.get(spec.process, Process.sequential)

        # 4. Manager LLM (solo para hierarchical)
        manager_llm = None
        if spec.process == CrewProcess.hierarchical and spec.manager_model:
            manager_params = spec.model_params.model_copy(update={"model": spec.manager_model, "temperature": 0.1})
            manager_llm = self._make_llm(manager_params, llm_config)

        crew = Crew(
            agents=list(crew_agents.values()),
            tasks=tasks,
            process=process,
            manager_llm=manager_llm,
            verbose=True,
            # CrewAI memory usa internamente embeddings OpenAI/Chroma y puede
            # desacoplarse del proveedor/modelo configurado para el agente.
            # Mantenemos la memoria en nuestra propia capa para evitar esa
            # dependencia oculta y reconstruir contexto de forma consistente.
            memory=False,
        )

        return CrewAIRuntime(
            crew=crew,
            spec=spec,
            agent_id=str(design.agent_id),
            session_factory=self._session_factory,
            memory_adapter=self._build_memory(design),
        )

    def _make_llm(self, params, llm_config: LLMConfig):
        from crewai import LLM

        provider = canonical_provider(params.provider or llm_config.provider or infer_provider(params))
        model = qualify_crewai_model_name(params.model, provider)
        base_url = llm_config.base_url or resolve_base_url(provider, params.base_url)
        llm = LLM(
            model=model,
            api_key=llm_config.api_key,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            base_url=base_url,
        )
        if hasattr(llm, "max_completion_tokens"):
            llm.max_completion_tokens = params.max_tokens
        return bind_crewai_call_adapter(llm, provider)

    async def _build_agent_async(
        self,
        role_spec: AgentRoleSpec,
        default_llm,
        llm_config: LLMConfig,
        tenant_id: str = "",
    ):
        from crewai import Agent

        tools = []
        for t in role_spec.tools:
            if t.source == "library":
                tools.append(get_tool(t.name, t.config))
            else:
                from app.builders.langchain.builder import _load_custom_tool
                tools.append(await _load_custom_tool(t.name, t.config, tenant_id))

        llm = default_llm
        if role_spec.model_params:
            llm = self._make_llm(role_spec.model_params, llm_config)

        return Agent(
            role=role_spec.role,
            goal=role_spec.goal,
            backstory=role_spec.backstory,
            tools=tools,
            llm=llm,
            allow_delegation=role_spec.allow_delegation,
            verbose=True,
            max_iter=10,
        )

    def _build_agent(self, role_spec: AgentRoleSpec, default_llm, api_key: str = ""):
        from crewai import Agent

        tools = [get_tool(t.name, t.config) for t in role_spec.tools if t.source == "library"]

        llm = default_llm
        if role_spec.model_params:
            llm = self._make_llm(role_spec.model_params, LLMConfig(provider="anthropic", api_key=api_key))

        return Agent(
            role=role_spec.role,
            goal=role_spec.goal,
            backstory=role_spec.backstory,
            tools=tools,
            llm=llm,
            allow_delegation=role_spec.allow_delegation,
            verbose=True,
            max_iter=10,
        )

    def _build_memory(self, design: AgentDesign):
        mem_type = design.spec.memory.type
        ttl = design.spec.memory.ttl_seconds
        max_msg = design.spec.memory.max_messages
        agent_id = str(design.agent_id)

        if mem_type == MemoryType.none:
            return InMemoryAdapter(max_messages=0)

        if mem_type == MemoryType.session and self._redis:
            return RedisAdapter(
                redis_client=self._redis,
                ttl_seconds=ttl or 3600,
                max_messages=max_msg,
            )

        if mem_type in (MemoryType.persistent, MemoryType.summary) and self._session_factory:
            return PostgreSQLAdapter(
                session_factory=self._session_factory,
                agent_id=agent_id,
                max_messages=max_msg,
            )

        return InMemoryAdapter(max_messages=max_msg)

    def _build_tasks(self, design: AgentDesign, crew_agents: dict) -> list:
        from crewai import Task

        """
        Genera Tasks desde el graph_blueprint.
        Nodos de tipo 'agent' se convierten en Tasks; el agente asignado
        se resuelve por nombre de rol.
        """
        tasks: list[Task] = []
        blueprint = design.graph_blueprint
        agent_nodes = [
            n for n in blueprint.get("nodes", [])
            if n.get("type") == "agent"
        ]

        for i, node in enumerate(agent_nodes):
            # Intentar asignar al agente por nombre o tomar el primero disponible
            assigned_agent = None
            node_label_lower = node.get("label", "").lower()
            for name, agent in crew_agents.items():
                if name.lower() in node_label_lower or node_label_lower in name.lower():
                    assigned_agent = agent
                    break
            if assigned_agent is None:
                # Asignar en round-robin si no hay match
                agent_list = list(crew_agents.values())
                assigned_agent = agent_list[i % len(agent_list)]

            task = Task(
                description=(
                    f"{node.get('description', node.get('label', ''))}\n\n"
                    f"Objetivo general: {design.spec.goal}\n"
                    f"Input del usuario: {{input}}"
                ),
                expected_output=f"Resultado del paso: {node.get('label', 'completado')}",
                agent=assigned_agent,
            )
            tasks.append(task)

        # Fallback: si no hay tareas en el blueprint, crear una tarea global
        if not tasks and crew_agents:
            first_agent = next(iter(crew_agents.values()))
            tasks.append(Task(
                description=f"{design.spec.goal}\n\nInput: {{input}}",
                expected_output="Respuesta completa al objetivo",
                agent=first_agent,
            ))

        return tasks
