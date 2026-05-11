from __future__ import annotations

from collections import defaultdict

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
        tasks, task_plan = self._build_tasks(design, crew_agents)

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
            task_plan=task_plan,
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

    def _build_tasks(self, design: AgentDesign, crew_agents: dict) -> tuple[list, list[dict]]:
        from crewai import Task

        """
        Genera Tasks desde el graph_blueprint.
        Usa edges como dependencias reales entre tasks y modela nodos
        decision como pasos de revision estructurada.
        """
        tasks: list[Task] = []
        task_plan: list[dict] = []
        blueprint = design.graph_blueprint
        nodes = blueprint.get("nodes", [])
        edges = blueprint.get("edges", [])
        nodes_by_id = {node["id"]: node for node in nodes if node.get("id")}
        if not nodes_by_id or not crew_agents:
            return self._build_fallback_tasks(design, crew_agents)

        outgoing: dict[str, list[dict]] = defaultdict(list)
        incoming: dict[str, list[dict]] = defaultdict(list)
        for edge in edges:
            src = edge.get("from")
            dst = edge.get("to")
            if not src or not dst or src not in nodes_by_id or dst not in nodes_by_id:
                continue
            outgoing[src].append(edge)
            incoming[dst].append(edge)

        ordered_node_ids = self._order_blueprint_nodes(nodes, outgoing)
        executable_types = {"agent", "decision"}
        executable_node_ids = [
            node_id
            for node_id in ordered_node_ids
            if nodes_by_id.get(node_id, {}).get("type") in executable_types
        ]
        if not executable_node_ids:
            return self._build_fallback_tasks(design, crew_agents)

        node_order = {node_id: index for index, node_id in enumerate(ordered_node_ids)}
        task_by_node: dict[str, Task] = {}
        plan_by_node: dict[str, dict] = {}
        agent_keys = list(crew_agents.keys())

        for index, node_id in enumerate(executable_node_ids):
            node = nodes_by_id[node_id]
            assigned_agent_name = self._select_agent_for_node(
                node=node,
                crew_agents=crew_agents,
                plan_by_node=plan_by_node,
                incoming=incoming,
                nodes_by_id=nodes_by_id,
                fallback_index=index,
            )
            assigned_agent = crew_agents[assigned_agent_name or agent_keys[index % len(agent_keys)]]
            upstream_node_ids = self._resolve_executable_predecessors(
                node_id=node_id,
                incoming=incoming,
                nodes_by_id=nodes_by_id,
                node_order=node_order,
                executable_types=executable_types,
            )
            context_tasks = [task_by_node[upstream_id] for upstream_id in upstream_node_ids if upstream_id in task_by_node]
            tool_hints = self._collect_tool_hints(node_id, incoming, outgoing, nodes_by_id)
            retry_targets = self._resolve_retry_targets(
                node_id=node_id,
                outgoing=outgoing,
                nodes_by_id=nodes_by_id,
                node_order=node_order,
                executable_types=executable_types,
            )

            if node.get("type") == "decision":
                description = self._build_decision_description(node, design, retry_targets)
                expected_output = (
                    "JSON valido con las claves approved (boolean), reason (string), "
                    "retry_from (string o null) y final_answer (string)."
                )
            else:
                description = self._build_agent_task_description(
                    node=node,
                    design=design,
                    upstream_node_ids=upstream_node_ids,
                    plan_by_node=plan_by_node,
                    tool_hints=tool_hints,
                    outgoing=outgoing,
                    nodes_by_id=nodes_by_id,
                )
                expected_output = self._build_expected_output(node, retry_targets)

            task_kwargs = {
                "description": description,
                "expected_output": expected_output,
                "agent": assigned_agent,
            }
            if context_tasks:
                task_kwargs["context"] = context_tasks
            task = Task(**task_kwargs)
            tasks.append(task)

            plan = {
                "node_id": node_id,
                "node_type": node.get("type", "agent"),
                "label": node.get("label", node_id),
                "agent_name": assigned_agent_name,
                "upstream_node_ids": upstream_node_ids,
                "retry_targets": retry_targets,
                "tool_hints": tool_hints,
            }
            task_plan.append(plan)
            task_by_node[node_id] = task
            plan_by_node[node_id] = plan

        # Fallback: si no hay tareas en el blueprint, crear una tarea global
        if not tasks and crew_agents:
            return self._build_fallback_tasks(design, crew_agents)

        return tasks, task_plan

    def _build_fallback_tasks(self, design: AgentDesign, crew_agents: dict) -> tuple[list, list[dict]]:
        from crewai import Task

        tasks: list[Task] = []
        task_plan: list[dict] = []
        if crew_agents:
            first_name, first_agent = next(iter(crew_agents.items()))
            tasks.append(Task(
                description=f"{design.spec.goal}\n\nInput: {{input}}",
                expected_output="Respuesta completa al objetivo",
                agent=first_agent,
            ))
            task_plan.append({
                "node_id": "fallback_agent",
                "node_type": "agent",
                "label": design.spec.name,
                "agent_name": first_name,
                "upstream_node_ids": [],
                "retry_targets": [],
                "tool_hints": [],
            })
        return tasks, task_plan

    @staticmethod
    def _order_blueprint_nodes(nodes: list[dict], outgoing: dict[str, list[dict]]) -> list[str]:
        starts = [node["id"] for node in nodes if node.get("type") == "start" and node.get("id")]
        if not starts and nodes:
            starts = [nodes[0]["id"]]

        ordered: list[str] = []
        visited: set[str] = set()

        def walk(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            ordered.append(node_id)
            for edge in outgoing.get(node_id, []):
                dst = edge.get("to")
                if dst:
                    walk(dst)

        for start_id in starts:
            walk(start_id)
        for node in nodes:
            node_id = node.get("id")
            if node_id and node_id not in visited:
                walk(node_id)
        return ordered

    def _select_agent_for_node(
        self,
        *,
        node: dict,
        crew_agents: dict,
        plan_by_node: dict[str, dict],
        incoming: dict[str, list[dict]],
        nodes_by_id: dict[str, dict],
        fallback_index: int,
    ) -> str:
        label = (node.get("label") or "").strip().lower()
        description = (node.get("description") or "").strip().lower()
        searchable = f"{label} {description}"

        def matches(agent_name: str, agent_obj) -> bool:
            role = str(getattr(agent_obj, "role", "")).strip().lower()
            return bool(
                label and (
                    agent_name.lower() in searchable
                    or role in searchable
                    or label in agent_name.lower()
                    or label in role
                )
            )

        for name, agent in crew_agents.items():
            if matches(name, agent):
                return name

        if node.get("type") == "decision":
            for reviewer_hint in ("verificador", "coordinador", "review", "reviewer", "qa", "calidad"):
                for name, agent in crew_agents.items():
                    role = str(getattr(agent, "role", "")).lower()
                    if reviewer_hint in name.lower() or reviewer_hint in role:
                        return name

            for edge in incoming.get(node["id"], []):
                src = edge.get("from")
                src_node = nodes_by_id.get(src or "")
                if not src_node:
                    continue
                plan = plan_by_node.get(src_node.get("id", ""))
                if plan and plan.get("agent_name"):
                    return plan["agent_name"]

        agent_names = list(crew_agents.keys())
        return agent_names[fallback_index % len(agent_names)]

    def _resolve_executable_predecessors(
        self,
        *,
        node_id: str,
        incoming: dict[str, list[dict]],
        nodes_by_id: dict[str, dict],
        node_order: dict[str, int],
        executable_types: set[str],
    ) -> list[str]:
        predecessors: list[str] = []
        visited: set[str] = set()

        def visit(current_id: str) -> None:
            for edge in incoming.get(current_id, []):
                src = edge.get("from")
                if not src or src in visited:
                    continue
                visited.add(src)
                src_node = nodes_by_id.get(src)
                if not src_node:
                    continue
                if src_node.get("type") in executable_types:
                    if node_order.get(src, -1) < node_order.get(node_id, -1):
                        predecessors.append(src)
                    continue
                visit(src)

        visit(node_id)
        ordered_unique: list[str] = []
        seen: set[str] = set()
        for predecessor in sorted(predecessors, key=lambda item: node_order.get(item, 0)):
            if predecessor not in seen:
                seen.add(predecessor)
                ordered_unique.append(predecessor)
        return ordered_unique

    def _collect_tool_hints(
        self,
        node_id: str,
        incoming: dict[str, list[dict]],
        outgoing: dict[str, list[dict]],
        nodes_by_id: dict[str, dict],
    ) -> list[str]:
        hints: list[str] = []
        seen: set[str] = set()
        adjacent_edges = incoming.get(node_id, []) + outgoing.get(node_id, [])
        for edge in adjacent_edges:
            for candidate_id in (edge.get("from"), edge.get("to")):
                if not candidate_id or candidate_id == node_id:
                    continue
                candidate = nodes_by_id.get(candidate_id)
                if candidate and candidate.get("type") == "tool":
                    label = candidate.get("label") or candidate_id
                    if label not in seen:
                        seen.add(label)
                        hints.append(label)
        return hints

    def _resolve_retry_targets(
        self,
        *,
        node_id: str,
        outgoing: dict[str, list[dict]],
        nodes_by_id: dict[str, dict],
        node_order: dict[str, int],
        executable_types: set[str],
    ) -> list[dict]:
        targets: list[dict] = []
        current_order = node_order.get(node_id, -1)

        for edge in outgoing.get(node_id, []):
            dst = edge.get("to")
            if not dst:
                continue
            dst_node = nodes_by_id.get(dst)
            if not dst_node:
                continue
            if dst_node.get("type") in executable_types and node_order.get(dst, -1) <= current_order:
                targets.append({
                    "node_id": dst,
                    "label": dst_node.get("label", dst),
                    "condition": edge.get("condition"),
                })
                continue
            if dst_node.get("type") == "tool":
                for nested in outgoing.get(dst, []):
                    nested_dst = nested.get("to")
                    nested_node = nodes_by_id.get(nested_dst or "")
                    if nested_node and nested_node.get("type") in executable_types and node_order.get(nested_dst, -1) <= current_order:
                        targets.append({
                            "node_id": nested_dst,
                            "label": nested_node.get("label", nested_dst),
                            "condition": edge.get("condition") or nested.get("condition"),
                        })
        return targets

    def _build_agent_task_description(
        self,
        *,
        node: dict,
        design: AgentDesign,
        upstream_node_ids: list[str],
        plan_by_node: dict[str, dict],
        tool_hints: list[str],
        outgoing: dict[str, list[dict]],
        nodes_by_id: dict[str, dict],
    ) -> str:
        parts = [
            node.get("description", node.get("label", "")),
            f"Objetivo general: {design.spec.goal}",
        ]
        if upstream_node_ids:
            upstream_labels = [plan_by_node[node_id]["label"] for node_id in upstream_node_ids if node_id in plan_by_node]
            if upstream_labels:
                parts.append("TomÃ¡ como contexto operativo los resultados previos de: " + ", ".join(upstream_labels))
        if tool_hints:
            parts.append("Si agrega valor al flujo, apoyate en estas herramientas o pasos asociados: " + ", ".join(tool_hints))

        downstream_conditions = [
            edge.get("condition")
            for edge in outgoing.get(node["id"], [])
            if edge.get("condition") and nodes_by_id.get(edge.get("to", ""), {}).get("type") != "end"
        ]
        if downstream_conditions:
            parts.append("PreparÃ¡ la salida para habilitar estas decisiones posteriores: " + "; ".join(str(item) for item in downstream_conditions))

        parts.append("Input del usuario: {input}")
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _build_expected_output(node: dict, retry_targets: list[dict]) -> str:
        expected = f"Resultado del paso: {node.get('label', 'completado')}"
        if retry_targets:
            labels = ", ".join(target["label"] for target in retry_targets)
            expected += f". Debe dejar evidencia suficiente para una posible iteracion con: {labels}"
        return expected

    @staticmethod
    def _build_decision_description(node: dict, design: AgentDesign, retry_targets: list[dict]) -> str:
        retry_lines = (
            "\n".join(
                f"- {target['node_id']}: {target['label']}"
                + (f" (condicion: {target['condition']})" if target.get("condition") else "")
                for target in retry_targets
            )
            if retry_targets
            else "- null: no hace falta re-trabajo"
        )
        return (
            f"{node.get('description', node.get('label', 'Revision del flujo'))}\n\n"
            f"Objetivo general: {design.spec.goal}\n"
            "Revisa cuidadosamente el contexto recibido y decide si el resultado esta listo para el usuario.\n"
            "Si esta aprobado, devolve approved=true y una respuesta final lista para entregar en final_answer.\n"
            "Si no esta aprobado, devolve approved=false, explica el motivo en reason y elige retry_from usando uno de estos node_id:\n"
            f"{retry_lines}\n\n"
            "RespondÃ© SOLO con JSON valido, sin markdown."
        )
