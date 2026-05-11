from __future__ import annotations

import json
import re
from uuid import uuid4

from app.core.config import get_settings
from app.schemas.agent import AgentDesign, AgentSpec, FrameworkSelection, GraphBlueprint
from app.services.llm_client import TextGenerationClient

settings = get_settings()


class DesignGeneratorService:
    """
    Genera el AgentDesign completo: system prompt, graph blueprint,
    test cases y diagrama Mermaid. Usa Claude Sonnet como motor.
    """

    def __init__(self):
        self._client = TextGenerationClient()

    async def generate(
        self,
        spec: AgentSpec,
        framework: FrameworkSelection,
    ) -> AgentDesign:
        system_prompt = await self._generate_system_prompt(spec)
        graph_blueprint = await self._generate_graph_blueprint(spec, framework)
        test_cases = await self._generate_test_cases(spec)
        mermaid = self.blueprint_to_mermaid(graph_blueprint, spec)

        return AgentDesign(
            agent_id=uuid4(),
            tenant_id=spec.tenant_id,
            spec=spec,
            framework=framework,
            system_prompt=system_prompt,
            graph_blueprint=graph_blueprint,
            test_cases=test_cases,
            mermaid_diagram=mermaid,
            version=1,
        )

    # ── Generación del system prompt ─────────────────────────────────────────

    async def _generate_system_prompt(self, spec: AgentSpec) -> str:
        tools_desc = "\n".join(
            f"- {t.name}: {t.config.get('description', 'herramienta disponible')}"
            for t in spec.tools
        ) or "Sin herramientas específicas."

        roles_desc = ""
        if spec.agents:
            roles_desc = "\n".join(
                f"- {a.role}: {a.goal}" for a in spec.agents
            )

        prompt = f"""Generá un system prompt profesional en español para un agente de IA con las siguientes características.
El system prompt debe ser directo, claro y orientado a la tarea. No uses formato markdown excesivo.

NOMBRE: {spec.name}
OBJETIVO: {spec.goal}
DESCRIPCIÓN: {spec.description}
MODO: {'Agente único' if spec.mode.value == 'single' else 'Equipo de agentes'}
HERRAMIENTAS DISPONIBLES:
{tools_desc}
{f'ROLES DEL EQUIPO:{chr(10)}{roles_desc}' if roles_desc else ''}
RESTRICCIONES: {', '.join(spec.constraints) if spec.constraints else 'ninguna especificada'}
NIVEL DE AUTONOMÍA: {spec.autonomy_level.value if hasattr(spec, 'autonomy_level') else 'reactive'}

Respondé únicamente con el system prompt, sin explicaciones adicionales."""

        return await self._client.complete(
            prompt,
            max_tokens=800,
            temperature=settings.builder_temperature,
        )

    # ── Generación del graph blueprint ───────────────────────────────────────

    async def _generate_graph_blueprint(
        self,
        spec: AgentSpec,
        framework: FrameworkSelection,
    ) -> dict:
        prompt = f"""Generá un blueprint JSON para el flujo de ejecución de este agente.
El JSON debe tener esta estructura exacta:
{{
  "nodes": [
    {{"id": "string", "type": "start|agent|tool|decision|end", "label": "string", "description": "string"}}
  ],
  "edges": [
    {{"from": "node_id", "to": "node_id", "condition": "string o null"}}
  ]
}}

AGENTE: {spec.name}
OBJETIVO: {spec.goal}
MODO: {spec.mode.value}
FRAMEWORK: {framework.framework}
HERRAMIENTAS: {[t.name for t in spec.tools]}
AGENTES/ROLES: {[a.role for a in spec.agents] if spec.agents else []}
PROCESO: {framework.process.value if framework.process else 'N/A'}

Respondé SOLO con el JSON válido, sin markdown, sin explicaciones."""

        content = await self._client.complete(prompt, max_tokens=1000, temperature=0.1)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback a blueprint mínimo si el LLM no devuelve JSON válido
            return {
                "nodes": [
                    {"id": "start", "type": "start", "label": "Inicio", "description": ""},
                    {"id": "agent", "type": "agent", "label": spec.name, "description": spec.goal},
                    {"id": "end", "type": "end", "label": "Respuesta", "description": ""},
                ],
                "edges": [
                    {"from": "start", "to": "agent", "condition": None},
                    {"from": "agent", "to": "end", "condition": None},
                ],
            }

    # ── Generación de test cases ──────────────────────────────────────────────

    async def _generate_test_cases(self, spec: AgentSpec) -> list[dict]:
        prompt = f"""Generá exactamente 5 casos de prueba en JSON para este agente.
Cada caso debe tener:
- "id": número del 1 al 5
- "description": qué prueba este caso (string)
- "input": el mensaje de entrada del usuario (string)
- "expected_behavior": qué debería hacer el agente (string)
- "expected_tools": lista de tools que debería usar (lista de strings, puede ser vacía)
- "pass_criteria": cómo saber si pasó (string)

AGENTE: {spec.name}
OBJETIVO: {spec.goal}
HERRAMIENTAS: {[t.name for t in spec.tools]}
INPUTS ESPERADOS: {spec.expected_inputs}
OUTPUTS ESPERADOS: {spec.expected_outputs}

Respondé SOLO con el JSON array, sin markdown."""

        content = await self._client.complete(prompt, max_tokens=1200, temperature=0.3)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return [
                {
                    "id": 1,
                    "description": "Test básico de respuesta",
                    "input": f"Hola, necesito ayuda con {spec.goal.lower()}",
                    "expected_behavior": "El agente debe responder de forma relevante al objetivo",
                    "expected_tools": [],
                    "pass_criteria": "La respuesta contiene información relevante al objetivo",
                }
            ]

    # ── Conversión blueprint → Mermaid ────────────────────────────────────────

    def blueprint_to_mermaid(self, blueprint: dict | GraphBlueprint, spec: AgentSpec) -> str:
        if isinstance(blueprint, GraphBlueprint):
            blueprint = blueprint.as_dict()
        lines = ["flowchart TD"]
        node_id_map = {
            node["id"]: self._mermaid_node_id(node["id"])
            for node in blueprint.get("nodes", [])
            if node.get("id")
        }
        for node in blueprint.get("nodes", []):
            node_id = node_id_map.get(node["id"], self._mermaid_node_id(node["id"]))
            label = node["label"]
            node_type = node.get("type", "agent")
            if node_type == "start":
                lines.append(f'    {node_id}(["{label}"])')
            elif node_type == "end":
                lines.append(f'    {node_id}(["{label}"])')
            elif node_type == "decision":
                lines.append(f'    {node_id}{{"{label}"}}')
            else:
                lines.append(f'    {node_id}["{label}"]')

        for edge in blueprint.get("edges", []):
            src = node_id_map.get(edge["from"], self._mermaid_node_id(edge["from"]))
            dst = node_id_map.get(edge["to"], self._mermaid_node_id(edge["to"]))
            cond = edge.get("condition")
            if cond:
                lines.append(f'    {src} -->|"{cond}"| {dst}')
            else:
                lines.append(f'    {src} --> {dst}')

        return "\n".join(lines)

    @staticmethod
    def _mermaid_node_id(raw_id: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]", "_", raw_id or "").strip("_")
        if not normalized:
            normalized = "node"
        if normalized[0].isdigit():
            normalized = f"n_{normalized}"
        return f"node_{normalized.lower()}"
