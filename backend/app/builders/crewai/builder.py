from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from langchain_anthropic import ChatAnthropic

from app.components.tools.builtin import get_tool
from app.runtime.crewai.runtime import CrewAIRuntime
from app.schemas.agent import AgentDesign, AgentRoleSpec, CrewProcess


class CrewAIAgentBuilder:
    """
    Toma un AgentDesign con mode='crew' y produce un CrewAIRuntime.
    Mapea AgentRoleSpec → crewai.Agent y genera las Tasks
    desde el graph_blueprint del design.
    """

    async def build(self, design: AgentDesign, api_key: str = "") -> CrewAIRuntime:
        spec = design.spec
        llm  = self._make_llm(spec.model_params.model, spec.model_params.temperature, api_key)

        # 1. Construir agentes desde los roles del spec
        crew_agents: dict[str, Agent] = {}
        for role_spec in spec.agents:
            agent = await self._build_agent_async(role_spec, llm, api_key, design.tenant_id)
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
            manager_llm = self._make_llm(spec.manager_model, 0.1, api_key)

        crew = Crew(
            agents=list(crew_agents.values()),
            tasks=tasks,
            process=process,
            manager_llm=manager_llm,
            verbose=True,
            memory=spec.memory.type.value != "none",
        )

        return CrewAIRuntime(crew=crew, spec=spec)

    def _make_llm(self, model: str, temperature: float = 0.3, api_key: str = ""):
        if "gpt" in model:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
        return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)

    async def _build_agent_async(self, role_spec: AgentRoleSpec, default_llm, api_key: str = "", tenant_id: str = "") -> Agent:
        tools = []
        for t in role_spec.tools:
            if t.source == "library":
                tools.append(get_tool(t.name, t.config))
            else:
                from app.builders.langchain.builder import _load_custom_tool
                tools.append(await _load_custom_tool(t.name, t.config, tenant_id))

    def _build_agent(self, role_spec: AgentRoleSpec, default_llm, api_key: str = "") -> Agent:
        tools = [get_tool(t.name, t.config) for t in role_spec.tools if t.source == "library"]

        llm = default_llm
        if role_spec.model_params:
            llm = self._make_llm(
                role_spec.model_params.model,
                role_spec.model_params.temperature,
                api_key
            )

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

    def _build_tasks(self, design: AgentDesign, crew_agents: dict[str, Agent]) -> list[Task]:
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
