from __future__ import annotations
import json
import re
from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    allowed: bool
    action: str          # 'allow' | 'block' | 'warn'
    reason: str = ""
    transformed: str = ""


def _load_json(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def _apply_rule(text: str, rule: dict) -> GuardrailResult:
    cond = _load_json(rule.get("condition_json", {}))
    rtype = rule["rule_type"]
    action = rule.get("action", "block")

    if rtype == "input_block" or rtype == "output_filter":
        keywords = cond.get("keywords", [])
        if keywords and any(kw.lower() in text.lower() for kw in keywords):
            return GuardrailResult(allowed=False, action=action, reason=f"Keyword bloqueada: {keywords}")
        pattern = cond.get("regex")
        if pattern and re.search(pattern, text, re.IGNORECASE):
            return GuardrailResult(allowed=False, action=action, reason=f"Patrón bloqueado: {pattern}")

    elif rtype == "length_limit":
        max_chars = cond.get("max_chars", 10000)
        if len(text) > max_chars:
            return GuardrailResult(
                allowed=False,
                action=action,
                reason=f"Texto demasiado largo: {len(text)} > {max_chars} caracteres",
            )

    elif rtype == "topic_restrict":
        topics = cond.get("topics", [])
        if topics and any(t.lower() in text.lower() for t in topics):
            return GuardrailResult(allowed=False, action=action, reason=f"Tema restringido detectado")

    return GuardrailResult(allowed=True, action="allow")


async def check_input(text: str, rules: list[dict]) -> GuardrailResult:
    """
    Ejecuta reglas de tipo input_block y length_limit sobre el input del usuario.
    Retorna el primer resultado bloqueante (mayor prioridad primero).
    """
    applicable = [r for r in rules if r.get("is_active") and r["rule_type"] in ("input_block", "length_limit", "topic_restrict")]
    applicable.sort(key=lambda r: -r.get("priority", 0))
    for rule in applicable:
        result = _apply_rule(text, rule)
        if result.action in ("block", "warn"):
            return result
    return GuardrailResult(allowed=True, action="allow")


async def check_output(text: str, rules: list[dict]) -> GuardrailResult:
    """
    Ejecuta reglas de tipo output_filter y length_limit sobre la respuesta del LLM.
    """
    applicable = [r for r in rules if r.get("is_active") and r["rule_type"] in ("output_filter", "length_limit")]
    applicable.sort(key=lambda r: -r.get("priority", 0))
    for rule in applicable:
        result = _apply_rule(text, rule)
        if result.action in ("block", "warn"):
            return result
    return GuardrailResult(allowed=True, action="allow")
