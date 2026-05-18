from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.session import PublicSessionFactory
from app.services.model_catalog import normalize_provider_models
from app.schemas.wizard_chat import WizardChatMessage, WizardChatSessionResponse
from app.services.llm_client import TextGenerationClient


WIZARD_CHAT_DEFAULTS: dict[str, Any] = {
    "step": 0,
    "mode": None,
    "name": "",
    "description": "",
    "goal": "",
    "channels": ["web_chat"],
    "single_agent_mode": "react",
    "tools": [],
    "memory": {
        "type": "session",
        "max_messages": 50,
    },
    "rag": {
        "enabled": False,
        "pack": "GenericDocsRAG",
        "sources": [],
        "chunk_size": 500,
        "chunk_overlap": 50,
        "top_k": 4,
        "embedding_model": "text-embedding-3-small",
    },
    "model_params": {
        "model": "claude-sonnet-4-5",
        "temperature": 0.3,
        "max_tokens": 2048,
        "top_p": 1.0,
    },
    "constraints": [],
    "autonomy_level": "reactive",
    "knowledge_base_ids": [],
    "agents": [],
    "process": "sequential",
}

TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "web_search": ("web", "internet", "buscar", "busqueda", "google", "web search"),
    "knowledge_base": ("base de conocimiento", "conocimiento interno", "documentos", "rag", "kb"),
    "send_email": ("email", "mail", "correo", "enviar mail", "enviar email"),
    "calculator": ("calcular", "calculadora", "formula", "matemat"),
    "rest_api_call": ("api", "endpoint", "rest"),
    "sql_query": ("sql", "base de datos", "query", "consulta db"),
}

CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "web_chat": ("web", "chat web", "widget"),
    "whatsapp": ("whatsapp",),
    "telegram": ("telegram",),
    "slack": ("slack",),
    "rest_api": ("api", "rest api", "rest"),
}

FOCUS_ORDER = ("intro", "name", "behavior", "knowledge", "channels", "review")


@dataclass
class WizardChatSession:
    session_id: str
    draft_state: dict[str, Any] = field(default_factory=lambda: deepcopy(WIZARD_CHAT_DEFAULTS))
    messages: list[WizardChatMessage] = field(default_factory=list)
    current_focus: str = "intro"
    reviewed: set[str] = field(default_factory=set)


class WizardChatService:
    def __init__(self, client: TextGenerationClient | None = None):
        self._client = client or TextGenerationClient()
        self._sessions: dict[str, WizardChatSession] = {}

    async def start(self, *, tenant_id: str, initial_mode: str | None = None) -> WizardChatSessionResponse:
        session_id = str(uuid4())
        draft_state = deepcopy(WIZARD_CHAT_DEFAULTS)
        if initial_mode in {"single", "crew"}:
            draft_state["mode"] = initial_mode
        draft_state["model_params"] = await self._resolve_initial_model_params(tenant_id)
        session = WizardChatSession(session_id=session_id, draft_state=draft_state)
        assistant = (
            "Te ayudo a crear el agente por chat. Contame que queres resolver, "
            "si va a responder solo por chat o tambien usar herramientas y datos, "
            "y cual es el objetivo principal."
        )
        session.messages.append(WizardChatMessage(role="assistant", content=assistant))
        self._sessions[session_id] = session
        return self._as_response(session)

    async def message(self, session_id: str, user_message: str) -> WizardChatSessionResponse:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(session_id)

        content = user_message.strip()
        session.messages.append(WizardChatMessage(role="user", content=content))
        if session.current_focus:
            session.reviewed.add(session.current_focus)

        updates = await self._extract_updates(session, content)
        self._merge_state(session.draft_state, updates)
        self._fill_inferred_defaults(session.draft_state)

        next_focus = self._next_focus(session.draft_state, session.reviewed)
        session.current_focus = next_focus or "review"
        assistant = self._build_followup(session.draft_state, next_focus)
        session.messages.append(WizardChatMessage(role="assistant", content=assistant))
        return self._as_response(session)

    def get(self, session_id: str) -> WizardChatSessionResponse:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError(session_id)
        return self._as_response(session)

    def _as_response(self, session: WizardChatSession) -> WizardChatSessionResponse:
        completion = self._completion(session.draft_state, session.reviewed)
        next_focus = self._next_focus(session.draft_state, session.reviewed)
        return WizardChatSessionResponse(
            session_id=session.session_id,
            messages=session.messages,
            draft_state=session.draft_state,
            ready_to_create=next_focus is None,
            completion=completion,
            next_focus=next_focus,
        )

    async def _resolve_initial_model_params(self, tenant_id: str) -> dict[str, Any]:
        params = deepcopy(WIZARD_CHAT_DEFAULTS["model_params"])
        async with PublicSessionFactory() as db:
            result = await db.execute(
                text(
                    """
                    SELECT id, provider, models
                    FROM llm_provider_keys
                    WHERE tenant_id = CAST(:tid AS uuid) AND is_default = TRUE
                    ORDER BY created_at ASC
                    """
                ),
                {"tid": tenant_id},
            )
            rows = result.fetchall()

        if not rows:
            return params

        row = None
        selected_model_id = ""
        for candidate in rows:
            models = normalize_provider_models(candidate.models)
            if models:
                row = candidate
                selected_model_id = models[0].id
                break

        if row is None:
            row = rows[0]
            selected_model_id = self._fallback_model_for_provider(str(row.provider or "").strip().lower())

        params["provider"] = row.provider
        params["llm_key_id"] = str(row.id)
        if selected_model_id:
            params["model"] = selected_model_id
        return params

    def _fallback_model_for_provider(self, provider: str) -> str:
        return {
            "anthropic": "claude-sonnet-4-5",
            "openai": "gpt-4o-mini",
            "openrouter": "openai/gpt-4o-mini",
            "google": "google/gemini-2.0-flash-001",
            "deepseek": "deepseek-chat",
            "qwen": "qwen-plus",
            "moonshot": "moonshot-v1-8k",
            "zhipu": "glm-4-plus",
        }.get(provider, WIZARD_CHAT_DEFAULTS["model_params"]["model"])

    async def _extract_updates(self, session: WizardChatSession, user_message: str) -> dict[str, Any]:
        fallback = self._rule_based_extract(session.draft_state, session.current_focus, user_message)
        try:
            raw = await self._client.complete(
                prompt=self._build_extraction_prompt(session, user_message, fallback),
                max_tokens=1200,
                temperature=0.1,
            )
            parsed = self._extract_json(raw)
            if isinstance(parsed, dict):
                return self._sanitize_updates(parsed, fallback)
        except Exception:
            pass
        return fallback

    def _build_extraction_prompt(
        self,
        session: WizardChatSession,
        user_message: str,
        fallback: dict[str, Any],
    ) -> str:
        payload = {
            "current_focus": session.current_focus,
            "draft_state": session.draft_state,
            "user_message": user_message,
            "allowed_modes": ["single", "crew"],
            "allowed_single_agent_modes": ["direct", "react"],
            "allowed_channels": list(CHANNEL_ALIASES.keys()),
            "allowed_tools": list(TOOL_ALIASES.keys()),
            "fallback_guess": fallback,
        }
        return f"""
Sos el asistente conversacional del wizard de Agentica. A partir del mensaje del usuario,
extrae solamente los cambios estructurados del draft.

Responde solo JSON valido, sin markdown.

Schema:
{{
  "mode": "single" | "crew" | null,
  "name": "string o vacio",
  "description": "string o vacio",
  "goal": "string o vacio",
  "single_agent_mode": "direct" | "react" | null,
  "channels": ["web_chat"],
  "tools": ["web_search"],
  "rag_enabled": true | false | null,
  "constraints": ["string"],
  "agents": [{{"name": "researcher", "role": "Researcher", "goal": "string", "backstory": "string", "tools": [], "allow_delegation": false}}]
}}

Reglas:
- No inventes herramientas fuera de allowed_tools.
- Si el usuario no menciono un campo, devolvelo vacio o null.
- Si menciona un equipo, intenta proponer de 2 a 4 roles utiles.
- Escribi en espanol claro.

Contexto:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    def _extract_json(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _sanitize_updates(self, parsed: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        updates = deepcopy(fallback)
        for key in ("mode", "name", "description", "goal", "single_agent_mode"):
            value = parsed.get(key)
            if isinstance(value, str):
                updates[key] = value.strip()
        rag_enabled = parsed.get("rag_enabled")
        if isinstance(rag_enabled, bool):
            updates["rag"] = {"enabled": rag_enabled}
        channels = parsed.get("channels")
        if isinstance(channels, list):
            updates["channels"] = [item for item in channels if item in CHANNEL_ALIASES]
        tools = parsed.get("tools")
        if isinstance(tools, list):
            updates["tools"] = [item for item in tools if item in TOOL_ALIASES]
        constraints = parsed.get("constraints")
        if isinstance(constraints, list):
            updates["constraints"] = [str(item).strip() for item in constraints if str(item).strip()]
        agents = parsed.get("agents")
        if isinstance(agents, list):
            updates["agents"] = [item for item in agents if isinstance(item, dict)]
        return updates

    def _rule_based_extract(
        self,
        draft_state: dict[str, Any],
        current_focus: str,
        user_message: str,
    ) -> dict[str, Any]:
        text = user_message.strip()
        lower = text.lower()
        updates: dict[str, Any] = {}

        mode = None
        if any(token in lower for token in ("equipo", "crew", "varios agentes", "multiagente", "muchos agentes")):
            mode = "crew"
        elif any(token in lower for token in ("agente simple", "uno solo", "single", "un agente")):
            mode = "single"
        elif current_focus == "intro" and not draft_state.get("mode"):
            mode = "single"
        if mode:
            updates["mode"] = mode

        if any(token in lower for token in ("react", "herramient", "tools", "buscar", "consultar", "web", "datos externos", "documentos", "base de conocimiento", "rag", "calcular", "ejecutar")):
            updates["single_agent_mode"] = "react"
        elif any(token in lower for token in ("directo", "inmediata", "sin tools", "sin herramientas", "solo responda", "solo responder", "solo chat", "solo contestar")):
            updates["single_agent_mode"] = "direct"

        detected_channels = [
            channel
            for channel, aliases in CHANNEL_ALIASES.items()
            if any(alias in lower for alias in aliases)
        ]
        if detected_channels:
            updates["channels"] = detected_channels

        detected_tools = [
            tool
            for tool, aliases in TOOL_ALIASES.items()
            if any(alias in lower for alias in aliases)
        ]
        if detected_tools:
            updates["tools"] = detected_tools

        if "base de conocimiento" in lower or "document" in lower or "rag" in lower:
            updates["rag"] = {"enabled": True}
        elif current_focus == "knowledge" and any(token in lower for token in ("no", "sin", "ninguna")):
            updates["rag"] = {"enabled": False}

        if current_focus == "name":
            updates["name"] = self._clean_sentence(text)
        elif current_focus == "intro":
            updates["goal"] = text
        elif current_focus == "behavior" and draft_state.get("mode") == "crew":
            role_names = [
                self._to_role_name(chunk)
                for chunk in re.split(r"[,;\n]", text)
                if chunk.strip()
            ]
            if role_names:
                updates["agents"] = [
                    {
                        "name": self._slugify(role),
                        "role": role,
                        "goal": f"Resolver la parte de {role.lower()} dentro del objetivo general.",
                        "backstory": f"Especialista en {role.lower()} para el equipo del agente.",
                        "tools": [],
                        "allow_delegation": False,
                    }
                    for role in role_names[:4]
                ]
        elif current_focus == "knowledge" and "rag" not in updates:
            updates["rag"] = {"enabled": not any(token in lower for token in ("no", "sin"))}

        if not draft_state.get("goal") and current_focus != "intro" and len(text) > 20:
            updates.setdefault("goal", text)

        return updates

    def _merge_state(self, draft_state: dict[str, Any], updates: dict[str, Any]) -> None:
        if "mode" in updates and updates["mode"] in {"single", "crew"}:
            draft_state["mode"] = updates["mode"]
        if "name" in updates and updates["name"]:
            draft_state["name"] = updates["name"]
        if "description" in updates and updates["description"]:
            draft_state["description"] = updates["description"]
        if "goal" in updates and updates["goal"]:
            draft_state["goal"] = updates["goal"]
        if "single_agent_mode" in updates and updates["single_agent_mode"] in {"direct", "react"}:
            draft_state["single_agent_mode"] = updates["single_agent_mode"]
        if "channels" in updates and updates["channels"]:
            draft_state["channels"] = updates["channels"]
        if "tools" in updates:
            tool_names = [item for item in updates["tools"] if item in TOOL_ALIASES]
            draft_state["tools"] = [
                {"name": name, "source": "library", "config": {}}
                for name in tool_names
            ]
        if "constraints" in updates and updates["constraints"]:
            draft_state["constraints"] = updates["constraints"]
        if "agents" in updates and updates["agents"]:
            draft_state["agents"] = updates["agents"]
        rag_update = updates.get("rag")
        if isinstance(rag_update, dict) and "enabled" in rag_update:
            draft_state.setdefault("rag", deepcopy(WIZARD_CHAT_DEFAULTS["rag"]))
            draft_state["rag"]["enabled"] = bool(rag_update["enabled"])

    def _fill_inferred_defaults(self, draft_state: dict[str, Any]) -> None:
        goal = str(draft_state.get("goal") or "").strip()
        if goal and not draft_state.get("description"):
            draft_state["description"] = self._build_description(goal)
        if goal and not draft_state.get("name"):
            draft_state["name"] = self._suggest_name(goal, draft_state.get("mode"))
        if draft_state.get("single_agent_mode") == "direct":
            draft_state["tools"] = []
            draft_state.setdefault("rag", deepcopy(WIZARD_CHAT_DEFAULTS["rag"]))
            draft_state["rag"]["enabled"] = False
        if draft_state.get("mode") == "crew" and draft_state.get("single_agent_mode") not in {"direct", "react"}:
            draft_state["single_agent_mode"] = "react"

    def _next_focus(self, draft_state: dict[str, Any], reviewed: set[str]) -> str | None:
        if not draft_state.get("mode"):
            return "intro"
        if not str(draft_state.get("goal") or "").strip():
            return "intro"
        if not str(draft_state.get("name") or "").strip():
            return "name"
        if draft_state.get("mode") == "crew" and not draft_state.get("agents"):
            return "behavior"
        if draft_state.get("mode") == "single" and "behavior" not in reviewed:
            return "behavior"
        if "knowledge" not in reviewed:
            return "knowledge"
        if "channels" not in reviewed:
            return "channels"
        return None

    def _completion(self, draft_state: dict[str, Any], reviewed: set[str]) -> int:
        checks = [
            bool(draft_state.get("mode")),
            bool(str(draft_state.get("goal") or "").strip()),
            bool(str(draft_state.get("name") or "").strip()),
            bool(str(draft_state.get("description") or "").strip()),
            "behavior" in reviewed or draft_state.get("mode") == "crew" and bool(draft_state.get("agents")),
            "knowledge" in reviewed,
            "channels" in reviewed,
        ]
        completed = sum(1 for item in checks if item)
        return round((completed / len(checks)) * 100)

    def _build_followup(self, draft_state: dict[str, Any], next_focus: str | None) -> str:
        if next_focus is None:
            mode = "agente simple" if draft_state.get("mode") == "single" else "equipo de agentes"
            channels = ", ".join(draft_state.get("channels") or ["web_chat"])
            return (
                f"Ya tengo un borrador listo para crear un {mode}. "
                f"Nombre: {draft_state.get('name')}. Canal principal: {channels}. "
                "Si queres, ya podes crear el agente o seguir refinando tools, restricciones y tono."
            )

        if next_focus == "intro":
            return (
                "Perfecto. Ahora contame mejor el objetivo y decime si esto lo resuelve "
                "un solo agente o si necesitas varios roles colaborando."
            )
        if next_focus == "name":
            return "Bien. Como queres llamarlo en Agentica? Podes usar un nombre operativo corto."
        if next_focus == "behavior":
            if draft_state.get("mode") == "crew":
                return (
                    "Para el equipo, decime que roles queres. Por ejemplo: Researcher, Planner, Writer."
                )
            return (
                "Necesitas que solo responda, o tambien que use herramientas para buscar, consultar datos, "
                "calcular o ejecutar acciones? Si queres, decime cuales."
            )
        if next_focus == "knowledge":
            return (
                "Va a consumir conocimiento propio, documentos internos o una base de conocimiento? "
                "Si la respuesta es si, despues vas a tener que asociarle al menos una base."
            )
        if next_focus == "channels":
            return (
                "Por que canales lo vas a usar? Hoy puedo dejarlo listo para web_chat, WhatsApp, Telegram, Slack o REST API."
            )
        return "Contame que otra configuracion queres ajustar."

    def _build_description(self, goal: str) -> str:
        trimmed = self._clean_sentence(goal)
        return f"Agente orientado a {trimmed[:140].rstrip('.') }."

    def _suggest_name(self, goal: str, mode: str | None) -> str:
        words = re.findall(r"[A-Za-z0-9]+", goal)
        if not words:
            return "Nuevo agente"
        base = " ".join(word.capitalize() for word in words[:3])
        suffix = "Team" if mode == "crew" else "Agent"
        return f"{base} {suffix}".strip()

    def _clean_sentence(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" .")
        return cleaned[:160]

    def _slugify(self, text: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return base or "agent_role"

    def _to_role_name(self, text: str) -> str:
        cleaned = self._clean_sentence(text)
        return " ".join(part.capitalize() for part in cleaned.split())
