from __future__ import annotations

from collections import defaultdict, deque

from app.schemas.agent import (
    AgentDesign,
    FlowNode,
    FlowNodePosition,
    GraphBlueprint,
    GraphValidationIssue,
    GraphValidationReport,
)


def normalize_graph_blueprint(design: AgentDesign, blueprint: GraphBlueprint) -> GraphBlueprint:
    normalized_nodes: list[FlowNode] = []
    seen_node_ids: set[str] = set()

    for index, node in enumerate(blueprint.nodes):
        node_id = (node.id or "").strip()
        if not node_id:
            node_id = f"{node.type}_{index + 1}"
        base_id = node_id
        suffix = 2
        while node_id in seen_node_ids:
            node_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_node_ids.add(node_id)

        label = (node.label or "").strip() or node_id.replace("_", " ").title()
        description = (node.description or "").strip()
        position = node.position or FlowNodePosition(x=120 + (index % 3) * 240, y=120 + (index // 3) * 140)
        data = node.data.model_copy(deep=True)
        data.description = (data.description or description or "").strip() or None
        if design.spec.mode.value == "crew" and not data.assigned_agent and node.type.value == "agent" and design.spec.agents:
            matching_agent = next(
                (role.name for role in design.spec.agents if role.name == label or role.role == label),
                None,
            )
            data.assigned_agent = matching_agent

        normalized_nodes.append(
            node.model_copy(
                update={
                    "id": node_id,
                    "label": label,
                    "description": description,
                    "position": position,
                    "data": data,
                }
            )
        )

    valid_node_ids = {node.id for node in normalized_nodes}
    normalized_edges = []
    seen_edge_ids: set[str] = set()
    for index, edge in enumerate(blueprint.edges):
        edge_from = (edge.from_ or "").strip()
        edge_to = (edge.to or "").strip()
        edge_id = (edge.id or "").strip() or f"edge_{index + 1}"
        base_id = edge_id
        suffix = 2
        while edge_id in seen_edge_ids:
            edge_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_edge_ids.add(edge_id)

        if edge_from not in valid_node_ids or edge_to not in valid_node_ids:
            continue

        normalized_edges.append(
            edge.model_copy(
                update={
                    "id": edge_id,
                    "from_": edge_from,
                    "to": edge_to,
                    "condition": (edge.condition or "").strip() or None,
                }
            )
        )

    meta = blueprint.meta.model_copy(update={"version": max(1, blueprint.meta.version)})
    normalized = GraphBlueprint(nodes=normalized_nodes, edges=normalized_edges, meta=meta)
    return _ensure_rag_knowledge_node(design, normalized)


def validate_graph_blueprint(design: AgentDesign, blueprint: GraphBlueprint) -> GraphValidationReport:
    errors: list[GraphValidationIssue] = []
    warnings: list[GraphValidationIssue] = []

    if not blueprint.nodes:
        errors.append(GraphValidationIssue(level="error", code="empty_graph", message="El flujo no tiene nodos."))
        return GraphValidationReport(ok=False, errors=errors, warnings=warnings)

    nodes_by_id = {node.id: node for node in blueprint.nodes}
    node_ids = [node.id for node in blueprint.nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append(GraphValidationIssue(level="error", code="duplicate_node_id", message="Hay nodos con el mismo id."))

    starts = [node for node in blueprint.nodes if node.type.value == "start"]
    ends = [node for node in blueprint.nodes if node.type.value == "end"]
    agents = [node for node in blueprint.nodes if node.type.value == "agent"]
    decisions = [node for node in blueprint.nodes if node.type.value == "decision"]

    if len(starts) != 1:
        errors.append(GraphValidationIssue(level="error", code="invalid_start_count", message="Debe existir exactamente un nodo Start."))
    if not ends:
        errors.append(GraphValidationIssue(level="error", code="missing_end", message="Debe existir al menos un nodo End."))
    if not agents:
        errors.append(GraphValidationIssue(level="error", code="missing_agent", message="Debe existir al menos un nodo Agent."))

    outgoing: dict[str, list] = defaultdict(list)
    incoming: dict[str, list] = defaultdict(list)
    edge_ids: set[str] = set()

    for edge in blueprint.edges:
        if edge.id in edge_ids:
            errors.append(GraphValidationIssue(level="error", code="duplicate_edge_id", message="Hay conexiones con el mismo id.", edge_id=edge.id))
        edge_ids.add(edge.id)

        if edge.from_ not in nodes_by_id or edge.to not in nodes_by_id:
            errors.append(
                GraphValidationIssue(
                    level="error",
                    code="dangling_edge",
                    message="La conexión apunta a un nodo inexistente.",
                    edge_id=edge.id,
                )
            )
            continue
        outgoing[edge.from_].append(edge)
        incoming[edge.to].append(edge)

    if starts:
        start_id = starts[0].id
        reachable = _reachable_nodes(start_id, outgoing)
        for node in blueprint.nodes:
            if node.id not in reachable:
                errors.append(
                    GraphValidationIssue(
                        level="error",
                        code="unreachable_node",
                        message=f'El nodo "{node.label}" no es alcanzable desde Start.',
                        node_id=node.id,
                    )
                )

    available_role_names = {role.name for role in design.spec.agents} | {role.role for role in design.spec.agents}
    available_tool_names = {tool.name for tool in design.spec.tools}
    if design.spec.mode.value == "single" and design.spec.rag.enabled:
        available_tool_names.add("knowledge_base")

    for node in agents:
        if design.spec.mode.value == "crew":
            assigned = (node.data.assigned_agent or "").strip()
            if not assigned:
                errors.append(
                    GraphValidationIssue(
                        level="error",
                        code="unassigned_agent",
                        message=f'El nodo "{node.label}" no tiene agente asignado.',
                        node_id=node.id,
                    )
                )
            elif assigned not in available_role_names:
                errors.append(
                    GraphValidationIssue(
                        level="error",
                        code="unknown_assigned_agent",
                        message=f'El agente asignado "{assigned}" no existe en el crew.',
                        node_id=node.id,
                    )
                )
        elif not (node.description or node.data.description):
            warnings.append(
                GraphValidationIssue(
                    level="warning",
                    code="thin_agent_description",
                    message=f'El nodo "{node.label}" no tiene una descripción de trabajo.',
                    node_id=node.id,
                )
            )

    for node in decisions:
        branch_count = len(outgoing.get(node.id, []))
        if branch_count == 0:
            errors.append(
                GraphValidationIssue(
                    level="error",
                    code="decision_without_branches",
                    message=f'La decisión "{node.label}" no tiene salidas.',
                    node_id=node.id,
                )
            )
        elif branch_count == 1:
            warnings.append(
                GraphValidationIssue(
                    level="warning",
                    code="decision_single_branch",
                    message=f'La decisión "{node.label}" tiene una sola salida.',
                    node_id=node.id,
                )
            )

    for node in blueprint.nodes:
        if node.type.value == "tool":
            tool_name = (node.data.tool_name or "").strip()
            if design.spec.mode.value == "single":
                if not tool_name:
                    errors.append(
                        GraphValidationIssue(
                            level="error",
                            code="tool_without_name",
                            message=f'El nodo tool "{node.label}" no tiene tool_name.',
                            node_id=node.id,
                        )
                    )
                elif tool_name not in available_tool_names:
                    warnings.append(
                        GraphValidationIssue(
                            level="warning",
                            code="unknown_tool_name",
                            message=f'La tool "{tool_name}" no aparece en las tools declaradas del agente.',
                            node_id=node.id,
                        )
                    )
            elif not tool_name:
                warnings.append(
                    GraphValidationIssue(
                        level="warning",
                        code="tool_hint_without_name",
                        message=f'El nodo tool "{node.label}" no especifica tool_name.',
                        node_id=node.id,
                    )
                )

        if node.type.value != "start" and not incoming.get(node.id):
            warnings.append(
                GraphValidationIssue(
                    level="warning",
                    code="node_without_incoming",
                    message=f'El nodo "{node.label}" no tiene entradas.',
                    node_id=node.id,
                )
            )
        if node.type.value != "end" and not outgoing.get(node.id):
            warnings.append(
                GraphValidationIssue(
                    level="warning",
                    code="node_without_outgoing",
                    message=f'El nodo "{node.label}" no tiene salidas.',
                    node_id=node.id,
                )
            )

    return GraphValidationReport(ok=not errors, errors=errors, warnings=warnings)


def _reachable_nodes(start_id: str, outgoing: dict[str, list]) -> set[str]:
    visited: set[str] = set()
    queue: deque[str] = deque([start_id])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for edge in outgoing.get(current, []):
            if edge.to not in visited:
                queue.append(edge.to)
    return visited


def _ensure_rag_knowledge_node(design: AgentDesign, blueprint: GraphBlueprint) -> GraphBlueprint:
    if design.spec.mode.value != "single" or not design.spec.rag.enabled:
        return blueprint

    existing_rag = next(
        (
            node for node in blueprint.nodes
            if node.type.value == "tool" and (node.data.tool_name or "").strip() == "knowledge_base"
        ),
        None,
    )
    if existing_rag:
        return blueprint

    start_node = next((node for node in blueprint.nodes if node.type.value == "start"), None)
    if start_node is None:
        return blueprint

    nodes = list(blueprint.nodes)
    edges = list(blueprint.edges)
    rag_node_id = _next_node_id({node.id for node in nodes}, "knowledge_base")
    start_position = start_node.position or FlowNodePosition(x=120, y=120)
    rag_node = FlowNode.model_validate(
        {
            "id": rag_node_id,
            "type": "tool",
            "label": "Base de conocimientos",
            "description": "Consulta la base de conocimientos del agente antes de continuar el flujo.",
            "position": {
                "x": start_position.x + 240,
                "y": start_position.y,
            },
            "data": {
                "tool_name": "knowledge_base",
                "description": "Consulta la base de conocimientos del agente antes de continuar el flujo.",
            },
        }
    )
    nodes.append(rag_node)

    outgoing_from_start = [edge for edge in edges if edge.from_ == start_node.id]
    remaining_edges = [edge for edge in edges if edge.from_ != start_node.id]
    existing_edge_ids = {edge.id for edge in edges if edge.id}

    start_to_rag = {
        "id": _next_edge_id(existing_edge_ids, "edge_start_rag"),
        "from": start_node.id,
        "to": rag_node_id,
        "condition": None,
    }
    existing_edge_ids.add(start_to_rag["id"])

    next_edges = []
    if outgoing_from_start:
        for edge in outgoing_from_start:
            next_edge = {
                "id": _next_edge_id(existing_edge_ids, edge.id or f"{rag_node_id}_{edge.to}"),
                "from": rag_node_id,
                "to": edge.to,
                "condition": edge.condition,
            }
            existing_edge_ids.add(next_edge["id"])
            next_edges.append(next_edge)
    else:
        fallback_target = next(
            (node.id for node in nodes if node.id not in {start_node.id, rag_node_id} and node.type.value != "start"),
            None,
        )
        if fallback_target:
            next_edge = {
                "id": _next_edge_id(existing_edge_ids, f"{rag_node_id}_{fallback_target}"),
                "from": rag_node_id,
                "to": fallback_target,
                "condition": None,
            }
            existing_edge_ids.add(next_edge["id"])
            next_edges.append(next_edge)

    rebuilt_edges = [
        FlowEdge.model_validate(start_to_rag),
        *[FlowEdge.model_validate(edge) for edge in next_edges],
        *remaining_edges,
    ]

    return GraphBlueprint(nodes=nodes, edges=rebuilt_edges, meta=blueprint.meta)


def _next_node_id(existing_ids: set[str], base_id: str) -> str:
    candidate = base_id
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    return candidate


def _next_edge_id(existing_ids: set[str], base_id: str) -> str:
    candidate = base_id
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base_id}_{suffix}"
        suffix += 1
    return candidate
