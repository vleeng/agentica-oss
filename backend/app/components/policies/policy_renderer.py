from __future__ import annotations
import json


def _load(v):
    return json.loads(v) if isinstance(v, str) else (v or [])


def render_policy(policy: dict) -> str:
    """
    Convierte una BehaviorPolicy (fila de DB) en un bloque de texto
    para agregar al final del system_prompt del agente.
    """
    parts = ["", "--- POLÍTICAS DE COMPORTAMIENTO ---"]

    tone = policy.get("tone")
    if tone and tone != "profesional":
        parts.append(f"Tono de comunicación: {tone}")
    else:
        parts.append("Tono de comunicación: profesional y claro")

    format_req = policy.get("format_requirements")
    if format_req:
        parts.append(f"Formato de respuesta: {format_req}")

    escalation = _load(policy.get("escalation_conditions_json"))
    if escalation:
        lines = "\n".join(f"  - {c}" for c in escalation)
        parts.append(f"Escalar a un humano cuando:\n{lines}")

    triggers = _load(policy.get("confirmation_triggers_json"))
    if triggers:
        lines = "\n".join(f"  - {t}" for t in triggers)
        parts.append(f"Solicitar confirmación explícita antes de:\n{lines}")

    custom = _load(policy.get("custom_rules_json"))
    if custom:
        lines = "\n".join(f"  - {r}" for r in custom)
        parts.append(f"Reglas adicionales:\n{lines}")

    return "\n".join(parts)
