from __future__ import annotations
import json
from app.schemas.agent import ToolRef


def expand_skill(skill_row: dict) -> tuple[list[ToolRef], str]:
    """
    Convierte un skill en (tools a inyectar, fragmento de prompt).
    Llamado en RuntimeFactory.build() para cada skill asignada al agente.
    """
    tools_raw = skill_row.get("tools_json", [])
    if isinstance(tools_raw, str):
        tools_raw = json.loads(tools_raw)

    guardrails_raw = skill_row.get("guardrails_json", [])
    if isinstance(guardrails_raw, str):
        guardrails_raw = json.loads(guardrails_raw)

    tools = [ToolRef(**t) for t in tools_raw]

    parts = [f"--- SKILL: {skill_row['name']} ---"]
    if skill_row.get("objective"):
        parts.append(f"Objetivo: {skill_row['objective']}")
    if skill_row.get("usage_conditions"):
        parts.append(f"Condiciones de uso: {skill_row['usage_conditions']}")
    if skill_row.get("procedure"):
        parts.append(f"Procedimiento: {skill_row['procedure']}")
    if skill_row.get("quality_rules"):
        parts.append(f"Reglas de calidad: {skill_row['quality_rules']}")
    if skill_row.get("output_format"):
        parts.append(f"Formato de salida: {skill_row['output_format']}")
    if guardrails_raw:
        parts.append(f"Límites: {', '.join(guardrails_raw)}")

    prompt_fragment = "\n".join(parts)
    return tools, prompt_fragment
