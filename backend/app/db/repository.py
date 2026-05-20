from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent import AgentDesign, AgentMode
from app.schemas.build import BuildStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentRepository:
    """
    Acceso a datos de agentes en el schema del tenant.
    Todos los métodos reciben la session ya configurada con el search_path correcto.
    """

    def __init__(self, session: AsyncSession):
        self._db = session

    # ── Agents ────────────────────────────────────────────────────────────────

    async def create_agent(self, design: AgentDesign) -> dict:
        spec = design.spec
        agent_id = str(design.agent_id)

        await self._db.execute(
            text("""
                INSERT INTO agents (id, name, description, mode, framework, status, spec_json, design_json)
                VALUES (:id, :name, :desc, :mode, :fw, :status, CAST(:spec AS jsonb), CAST(:design AS jsonb))
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    mode = EXCLUDED.mode,
                    framework = EXCLUDED.framework,
                    status = EXCLUDED.status,
                    spec_json = EXCLUDED.spec_json,
                    design_json = EXCLUDED.design_json,
                    updated_at  = NOW()
            """),
            {
                "id":     agent_id,
                "name":   spec.name,
                "desc":   spec.description,
                "mode":   spec.mode.value,
                "fw":     design.framework.framework,
                "status": design.status,
                "spec":   spec.model_dump_json(),
                "design": design.model_dump_json(),
            },
        )
        await self._db.commit()
        return {"agent_id": agent_id, "status": design.status}

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT id, name, mode, framework, status, design_json FROM agents WHERE id = :id"),
            {"id": agent_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "agent_id":   str(row.id),
            "name":       row.name,
            "mode":       row.mode,
            "framework":  row.framework,
            "status":     row.status,
            "design":     row.design_json,
        }

    async def list_agents(self, limit: int = 50) -> list[dict]:
        result = await self._db.execute(
            text("SELECT id, name, mode, framework, status, created_at FROM agents ORDER BY created_at DESC LIMIT :limit"),
            {"limit": limit},
        )
        return [
            {
                "agent_id":   str(r.id),
                "name":       r.name,
                "mode":       r.mode,
                "framework":  r.framework,
                "status":     r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in result.fetchall()
        ]

    async def update_agent_status(self, agent_id: str, status: str) -> None:
        await self._db.execute(
            text("""
                UPDATE agents
                SET
                    status = :status,
                    design_json = jsonb_set(
                        COALESCE(design_json, '{}'::jsonb),
                        '{status}',
                        to_jsonb(CAST(:status AS text)),
                        true
                    ),
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"status": status, "id": agent_id},
        )
        await self._db.commit()

    async def delete_agent(self, agent_id: str) -> bool:
        res = await self._db.execute(
            text("DELETE FROM agents WHERE id = CAST(:id AS uuid)"),
            {"id": agent_id},
        )
        await self._db.commit()
        return res.rowcount > 0

    async def update_agent_core(self, agent_id: str, patch: dict) -> Optional[dict]:
        """
        Aplica un patch sobre name / system_prompt / model_params del design_json
        y persiste name + spec_json + design_json en la fila de agents.
        Retorna el design_dict actualizado, o None si no existe.
        """
        result = await self._db.execute(
            text("SELECT design_json FROM agents WHERE id = CAST(:id AS uuid)"),
            {"id": agent_id},
        )
        row = result.fetchone()
        if not row:
            return None

        design_dict = row.design_json if isinstance(row.design_json, dict) else json.loads(row.design_json)
        spec = design_dict.get("spec", {})

        # Campos de alto nivel del spec
        if patch.get("name"):
            spec["name"] = patch["name"]

        # system_prompt vive en AgentDesign (no en AgentSpec)
        if "system_prompt" in patch and patch["system_prompt"] is not None:
            design_dict["system_prompt"] = patch["system_prompt"]

        # model_params
        model_params = spec.get("model_params", {})
        for field in ("model", "provider", "base_url", "llm_key_id", "temperature", "max_tokens"):
            if field in patch and patch[field] is not None:
                model_params[field] = patch[field]
        spec["model_params"] = model_params
        design_dict["spec"] = spec

        await self._db.execute(
            text("""
                UPDATE agents
                SET name       = :name,
                    spec_json  = CAST(:spec AS jsonb),
                    design_json = CAST(:design AS jsonb),
                    updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id":     agent_id,
                "name":   spec.get("name", ""),
                "spec":   json.dumps(spec),
                "design": json.dumps(design_dict),
            },
        )
        await self._db.commit()
        return design_dict

    async def update_agent_graph(self, agent_id: str, *, graph_blueprint: dict, mermaid_diagram: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT design_json FROM agents WHERE id = CAST(:id AS uuid)"),
            {"id": agent_id},
        )
        row = result.fetchone()
        if not row:
            return None

        design_dict = row.design_json if isinstance(row.design_json, dict) else json.loads(row.design_json)
        design_dict["graph_blueprint"] = graph_blueprint
        design_dict["mermaid_diagram"] = mermaid_diagram

        await self._db.execute(
            text("""
                UPDATE agents
                SET design_json = CAST(:design AS jsonb),
                    updated_at = NOW()
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id": agent_id,
                "design": json.dumps(design_dict),
            },
        )
        await self._db.commit()
        return design_dict

    # ── Builds ────────────────────────────────────────────────────────────────

    async def create_build(self, agent_id: str, version: int) -> str:
        build_id = str(uuid.uuid4())
        await self._db.execute(
            text("""
                INSERT INTO agent_builds (id, agent_id, version, status)
                VALUES (:id, :agent_id, :version, 'pending')
            """),
            {"id": build_id, "agent_id": agent_id, "version": version},
        )
        await self._db.commit()
        return build_id

    async def update_build(self, build_id: str, status: str, code_path: str = None, error: str = None) -> None:
        await self._db.execute(
            text("""
                UPDATE agent_builds
                SET status = :status, code_path = :path, error = :error
                WHERE id = :id
            """),
            {"status": status, "path": code_path, "error": error, "id": build_id},
        )
        await self._db.commit()

    async def get_latest_build(self, agent_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("""
                SELECT id, version, status, code_path, error, created_at
                FROM agent_builds
                WHERE agent_id = :agent_id
                ORDER BY version DESC LIMIT 1
            """),
            {"agent_id": agent_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "build_id":   str(row.id),
            "version":    row.version,
            "status":     row.status,
            "code_path":  row.code_path,
            "error":      row.error,
            "created_at": row.created_at.isoformat(),
        }

    # ── Deployments ───────────────────────────────────────────────────────────

    async def create_deployment(
        self,
        agent_id: str,
        build_id: str,
        endpoint_url: str,
        ws_url: str,
        container_id: str,
    ) -> str:
        deploy_id = str(uuid.uuid4())
        await self._db.execute(
            text("""
                INSERT INTO deployments (id, agent_id, build_id, endpoint_url, ws_url, container_id, status)
                VALUES (:id, :agent_id, :build_id, :endpoint, :ws, :container, 'active')
            """),
            {
                "id":         deploy_id,
                "agent_id":   agent_id,
                "build_id":   build_id,
                "endpoint":   endpoint_url,
                "ws":         ws_url,
                "container":  container_id,
            },
        )
        await self._db.commit()
        return deploy_id

    async def get_active_deployment(self, agent_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("""
                SELECT id, endpoint_url, ws_url, container_id, status
                FROM deployments
                WHERE agent_id = :agent_id AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """),
            {"agent_id": agent_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "deploy_id":    str(row.id),
            "endpoint_url": row.endpoint_url,
            "ws_url":       row.ws_url,
            "container_id": row.container_id,
            "status":       row.status,
        }

    # ── Conversaciones y mensajes ─────────────────────────────────────────────

    async def upsert_conversation(self, agent_id: str, session_id: str, channel: str, user_ref: str = "") -> str:
        conv_id = str(uuid.uuid4())
        await self._db.execute(
            text("""
                INSERT INTO conversations (id, agent_id, session_id, channel, user_ref)
                VALUES (:id, :agent_id, :session_id, :channel, :user_ref)
                ON CONFLICT (session_id, agent_id) DO NOTHING
            """),
            {"id": conv_id, "agent_id": agent_id, "session_id": session_id,
             "channel": channel, "user_ref": user_ref},
        )
        result = await self._db.execute(
            text("SELECT id FROM conversations WHERE agent_id = :a AND session_id = :s"),
            {"a": agent_id, "s": session_id},
        )
        row = result.fetchone()
        await self._db.commit()
        return str(row.id)

    async def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> None:
        await self._db.execute(
            text("""
                INSERT INTO messages (id, conversation_id, role, content, tokens_in, tokens_out)
                VALUES (gen_random_uuid(), :conv_id, :role, :content, :ti, :to)
            """),
            {
                "conv_id":  conversation_id,
                "role":     role,
                "content":  content,
                "ti":       tokens_in,
                "to":       tokens_out,
            },
        )
        await self._db.commit()

    async def get_conversation_history(self, agent_id: str, session_id: str, limit: int = 50) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT m.role, m.content, m.created_at
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.agent_id = :agent_id AND c.session_id = :session_id
                ORDER BY m.created_at DESC LIMIT :limit
            """),
            {"agent_id": agent_id, "session_id": session_id, "limit": limit},
        )
        rows = result.fetchall()
        return [
            {"role": r.role, "content": r.content, "created_at": r.created_at.isoformat()}
            for r in reversed(rows)
        ]

    async def save_conversation_event(
        self,
        conversation_id: str,
        event_type: str,
        *,
        phase: str | None = None,
        actor: str | None = None,
        kind: str | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._db.execute(
            text("""
                INSERT INTO conversation_events
                    (id, conversation_id, event_type, phase, actor, kind, message, payload_json)
                VALUES
                    (gen_random_uuid(), CAST(:conversation_id AS uuid), :event_type, :phase, :actor, :kind, :message, CAST(:payload AS jsonb))
            """),
            {
                "conversation_id": conversation_id,
                "event_type": event_type,
                "phase": phase,
                "actor": actor,
                "kind": kind,
                "message": message,
                "payload": json.dumps(payload or {}, default=str),
            },
        )
        await self._db.commit()

    async def list_agent_runs(self, agent_id: str, limit: int = 25) -> list[dict]:
        result = await self._db.execute(
            text("""
                WITH event_counts AS (
                    SELECT
                        ce.conversation_id,
                        COUNT(*) AS event_count,
                        COUNT(*) FILTER (
                            WHERE ce.event_type = 'progress'
                              AND COALESCE(ce.actor, '') NOT IN ('knowledge_base', 'web_search')
                              AND COALESCE(ce.kind, '') = 'tool'
                        ) AS tool_events,
                        COUNT(*) FILTER (
                            WHERE COALESCE(ce.actor, '') = 'knowledge_base'
                               OR COALESCE(ce.kind, '') IN ('rag_result', 'rag_preview')
                        ) AS kb_events,
                        COUNT(*) FILTER (
                            WHERE COALESCE(ce.actor, '') = 'web_search'
                               OR COALESCE(ce.kind, '') LIKE 'web_%'
                        ) AS web_events,
                        MAX(ce.created_at) AS last_event_at
                    FROM conversation_events ce
                    GROUP BY ce.conversation_id
                ),
                message_counts AS (
                    SELECT
                        m.conversation_id,
                        COUNT(*) AS message_count,
                        MAX(m.created_at) AS last_message_at
                    FROM messages m
                    GROUP BY m.conversation_id
                )
                SELECT
                    c.id,
                    c.session_id,
                    c.channel,
                    c.user_ref,
                    c.created_at,
                    GREATEST(
                        c.created_at,
                        COALESCE(mc.last_message_at, c.created_at),
                        COALESCE(ec.last_event_at, c.created_at)
                    ) AS last_activity_at,
                    COALESCE(mc.message_count, 0) AS message_count,
                    COALESCE(ec.event_count, 0) AS event_count,
                    COALESCE(ec.tool_events, 0) AS tool_events,
                    COALESCE(ec.kb_events, 0) AS kb_events,
                    COALESCE(ec.web_events, 0) AS web_events,
                    (
                        SELECT m.content
                        FROM messages m
                        WHERE m.conversation_id = c.id AND m.role = 'user'
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) AS last_user_message,
                    (
                        SELECT m.content
                        FROM messages m
                        WHERE m.conversation_id = c.id AND m.role = 'assistant'
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) AS last_assistant_message
                FROM conversations c
                LEFT JOIN message_counts mc ON mc.conversation_id = c.id
                LEFT JOIN event_counts ec ON ec.conversation_id = c.id
                WHERE c.agent_id = CAST(:agent_id AS uuid)
                ORDER BY last_activity_at DESC
                LIMIT :limit
            """),
            {"agent_id": agent_id, "limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "conversation_id": str(r.id),
                "session_id": r.session_id,
                "channel": r.channel,
                "user_ref": r.user_ref,
                "created_at": r.created_at.isoformat(),
                "last_activity_at": r.last_activity_at.isoformat() if r.last_activity_at else r.created_at.isoformat(),
                "message_count": int(r.message_count or 0),
                "event_count": int(r.event_count or 0),
                "tool_events": int(r.tool_events or 0),
                "kb_events": int(r.kb_events or 0),
                "web_events": int(r.web_events or 0),
                "last_user_message": r.last_user_message or "",
                "last_assistant_message": r.last_assistant_message or "",
            }
            for r in rows
        ]

    async def get_run_summary(self, agent_id: str, conversation_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("""
                SELECT
                    c.id,
                    c.session_id,
                    c.channel,
                    c.user_ref,
                    c.created_at,
                    (
                        SELECT MAX(created_at)
                        FROM conversation_events ce
                        WHERE ce.conversation_id = c.id
                    ) AS last_event_at,
                    (
                        SELECT MAX(created_at)
                        FROM messages m
                        WHERE m.conversation_id = c.id
                    ) AS last_message_at
                FROM conversations c
                WHERE c.agent_id = CAST(:agent_id AS uuid)
                  AND c.id = CAST(:conversation_id AS uuid)
            """),
            {"agent_id": agent_id, "conversation_id": conversation_id},
        )
        row = result.fetchone()
        if not row:
            return None
        last_activity = max(
            [value for value in (row.created_at, row.last_event_at, row.last_message_at) if value is not None],
            default=row.created_at,
        )
        return {
            "conversation_id": str(row.id),
            "session_id": row.session_id,
            "channel": row.channel,
            "user_ref": row.user_ref,
            "created_at": row.created_at.isoformat(),
            "last_activity_at": last_activity.isoformat() if last_activity else row.created_at.isoformat(),
        }

    async def get_run_events(self, conversation_id: str, limit: int = 500) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT id, event_type, phase, actor, kind, message, payload_json, created_at
                FROM conversation_events
                WHERE conversation_id = CAST(:conversation_id AS uuid)
                ORDER BY created_at ASC
                LIMIT :limit
            """),
            {"conversation_id": conversation_id, "limit": limit},
        )
        rows = result.fetchall()
        events: list[dict] = []
        for row in rows:
            payload = row.payload_json
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            events.append(
                {
                    "id": str(row.id),
                    "event_type": row.event_type,
                    "phase": row.phase,
                    "actor": row.actor,
                    "kind": row.kind,
                    "message": row.message,
                    "payload": payload or {},
                    "created_at": row.created_at.isoformat(),
                }
            )
        return events

    async def get_run_messages(self, conversation_id: str, limit: int = 200) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = CAST(:conversation_id AS uuid)
                ORDER BY created_at ASC
                LIMIT :limit
            """),
            {"conversation_id": conversation_id, "limit": limit},
        )
        rows = result.fetchall()
        return [
            {
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    # ── Eval runs ─────────────────────────────────────────────────────────────

    async def save_eval_run(self, agent_id: str, build_id: str, report: dict) -> str:
        run_id = str(uuid.uuid4())
        await self._db.execute(
            text("""
                INSERT INTO eval_runs (id, agent_id, build_id, score, passed, report_json)
                VALUES (:id, :agent_id, :build_id, :score, :passed, CAST(:report AS jsonb))
            """),
            {
                "id":       run_id,
                "agent_id": agent_id,
                "build_id": build_id,
                "score":    report.get("overall_score", 0),
                "passed":   report.get("pass_threshold", False),
                "report":   json.dumps(report, default=str),
            },
        )
        await self._db.commit()
        return run_id

    # ── Billing ───────────────────────────────────────────────────────────────

    async def record_billing_event(
        self,
        agent_id: str,
        conversation_id: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        await self._db.execute(
            text("""
                INSERT INTO billing_events (id, agent_id, conversation_id, tokens_in, tokens_out, cost_usd)
                VALUES (gen_random_uuid(), :agent_id, :conv_id, :ti, :to, :cost)
            """),
            {
                "agent_id": agent_id,
                "conv_id":  conversation_id,
                "ti":       tokens_in,
                "to":       tokens_out,
                "cost":     cost_usd,
            },
        )
        await self._db.commit()

    async def get_billing_summary(self, agent_id: str | None = None) -> dict:
        if agent_id is None:
            sql = text("""
                SELECT
                    COUNT(*) as calls,
                    COALESCE(SUM(tokens_in), 0)  as total_tokens_in,
                    COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                    COALESCE(SUM(cost_usd), 0)   as total_cost_usd
                FROM billing_events
            """)
            result = await self._db.execute(sql)
        else:
            sql = text("""
                SELECT
                    COUNT(*) as calls,
                    COALESCE(SUM(tokens_in), 0)  as total_tokens_in,
                    COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                    COALESCE(SUM(cost_usd), 0)   as total_cost_usd
                FROM billing_events
                WHERE agent_id = CAST(:agent_id AS uuid)
            """)
            result = await self._db.execute(sql, {"agent_id": agent_id})
        row = result.fetchone()
        return {
            "calls":            row.calls,
            "total_tokens_in":  row.total_tokens_in,
            "total_tokens_out": row.total_tokens_out,
            "total_cost_usd":   float(row.total_cost_usd),
        }


    # ── Custom Tools ──────────────────────────────────────────────────────────

    async def list_custom_tools(self) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT id, name, description, config_schema,
                       is_active, test_input, last_error, created_at, updated_at
                FROM custom_tools
                ORDER BY created_at DESC
            """)
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_custom_tool(self, name: str) -> dict | None:
        result = await self._db.execute(
            text("SELECT * FROM custom_tools WHERE name = :name"),
            {"name": name},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def get_custom_tool_by_id(self, tool_id: str) -> dict | None:
        result = await self._db.execute(
            text("SELECT * FROM custom_tools WHERE id = CAST(:id AS uuid)"),
            {"id": tool_id},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def create_custom_tool(
        self,
        name: str,
        description: str,
        source_code: str,
        config_schema: dict,
        test_input: str = "",
    ) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO custom_tools
                    (name, description, source_code, config_schema, test_input)
                VALUES
                    (:name, :desc, :code, CAST(:schema AS jsonb), :test)
                RETURNING id, name, description, config_schema,
                          is_active, test_input, created_at, updated_at
            """),
            {
                "name":   name,
                "desc":   description,
                "code":   source_code,
                "schema": __import__("json").dumps(config_schema),
                "test":   test_input,
            },
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def update_custom_tool(
        self,
        tool_id: str,
        description: str | None = None,
        source_code: str | None = None,
        config_schema: dict | None = None,
        is_active: bool | None = None,
        test_input: str | None = None,
        last_error: str | None = None,
    ) -> dict | None:
        import json
        sets, params = [], {"id": tool_id}
        if description  is not None: sets.append("description = :desc");    params["desc"]   = description
        if source_code  is not None: sets.append("source_code = :code");    params["code"]   = source_code
        if config_schema is not None: sets.append("config_schema = CAST(:schema AS jsonb)"); params["schema"] = json.dumps(config_schema)
        if is_active    is not None: sets.append("is_active = :active");    params["active"] = is_active
        if test_input   is not None: sets.append("test_input = :test");     params["test"]   = test_input
        if last_error   is not None: sets.append("last_error = :err");      params["err"]    = last_error
        if not sets:
            return await self.get_custom_tool_by_id(tool_id)
        sets.append("updated_at = NOW()")
        result = await self._db.execute(
            text(f"""
                UPDATE custom_tools SET {', '.join(sets)}
                WHERE id = CAST(:id AS uuid)
                RETURNING id, name, description, config_schema,
                          is_active, test_input, last_error, created_at, updated_at
            """),
            params,
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def delete_custom_tool(self, tool_id: str) -> bool:
        result = await self._db.execute(
            text("DELETE FROM custom_tools WHERE id = CAST(:id AS uuid) RETURNING id"),
            {"id": tool_id},
        )
        await self._db.commit()
        return result.fetchone() is not None

    # ── Skills ────────────────────────────────────────────────────────────────

    async def list_skills(self) -> list[dict]:
        result = await self._db.execute(
            text("SELECT * FROM skills ORDER BY created_at DESC")
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_skill(self, skill_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT * FROM skills WHERE id = CAST(:id AS uuid)"), {"id": skill_id}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def create_skill(self, data: dict) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO skills
                    (name, description, objective, usage_conditions, tools_json,
                     procedure, quality_rules, output_format, guardrails_json)
                VALUES
                    (:name, :description, :objective, :usage_conditions, CAST(:tools_json AS jsonb),
                     :procedure, :quality_rules, :output_format, CAST(:guardrails_json AS jsonb))
                RETURNING *
            """),
            data,
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def update_skill(self, skill_id: str, data: dict) -> Optional[dict]:
        sets, params = [], {"id": skill_id}
        for field in ("name", "description", "objective", "usage_conditions",
                      "procedure", "quality_rules", "output_format", "is_active"):
            if field in data:
                sets.append(f"{field} = :{field}")
                params[field] = data[field]
        for jfield in ("tools_json", "guardrails_json"):
            if jfield in data:
                sets.append(f"{jfield} = CAST(:{jfield} AS jsonb)")
                params[jfield] = data[jfield]
        if not sets:
            return await self.get_skill(skill_id)
        sets.append("updated_at = NOW()")
        result = await self._db.execute(
            text(f"UPDATE skills SET {', '.join(sets)} WHERE id = CAST(:id AS uuid) RETURNING *"),
            params,
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def delete_skill(self, skill_id: str) -> bool:
        result = await self._db.execute(
            text("DELETE FROM skills WHERE id = CAST(:id AS uuid) RETURNING id"), {"id": skill_id}
        )
        await self._db.commit()
        return result.fetchone() is not None

    async def assign_skill_to_agent(self, agent_id: str, skill_id: str) -> None:
        await self._db.execute(
            text("""
                INSERT INTO agent_skills (agent_id, skill_id)
                VALUES (CAST(:agent_id AS uuid), CAST(:skill_id AS uuid))
                ON CONFLICT DO NOTHING
            """),
            {"agent_id": agent_id, "skill_id": skill_id},
        )
        await self._db.commit()

    async def unassign_skill_from_agent(self, agent_id: str, skill_id: str) -> None:
        await self._db.execute(
            text("DELETE FROM agent_skills WHERE agent_id = CAST(:a AS uuid) AND skill_id = CAST(:s AS uuid)"),
            {"a": agent_id, "s": skill_id},
        )
        await self._db.commit()

    async def get_agent_skills(self, agent_id: str) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT s.* FROM skills s
                JOIN agent_skills asg ON asg.skill_id = s.id
                WHERE asg.agent_id = CAST(:agent_id AS uuid) AND s.is_active = TRUE
                ORDER BY asg.assigned_at
            """),
            {"agent_id": agent_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    # ── MCP Servers ───────────────────────────────────────────────────────────

    async def list_mcp_servers(self) -> list[dict]:
        result = await self._db.execute(
            text("SELECT * FROM mcp_servers ORDER BY created_at DESC")
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_mcp_server(self, server_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT * FROM mcp_servers WHERE id = CAST(:id AS uuid)"), {"id": server_id}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def create_mcp_server(self, data: dict) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO mcp_servers
                    (name, endpoint, transport, auth_type, auth_config_json, discovered_tools_json)
                VALUES
                    (:name, :endpoint, :transport, :auth_type, CAST(:auth_config_json AS jsonb), CAST(:discovered_tools_json AS jsonb))
                RETURNING *
            """),
            data,
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def update_mcp_server(self, server_id: str, data: dict) -> Optional[dict]:
        sets, params = [], {"id": server_id}
        for field in ("name", "endpoint", "transport", "auth_type", "is_active", "last_tested_at"):
            if field in data:
                sets.append(f"{field} = :{field}")
                params[field] = data[field]
        for jfield in ("auth_config_json", "discovered_tools_json"):
            if jfield in data:
                sets.append(f"{jfield} = CAST(:{jfield} AS jsonb)")
                params[jfield] = data[jfield]
        if not sets:
            return await self.get_mcp_server(server_id)
        result = await self._db.execute(
            text(f"UPDATE mcp_servers SET {', '.join(sets)} WHERE id = CAST(:id AS uuid) RETURNING *"),
            params,
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def delete_mcp_server(self, server_id: str) -> bool:
        result = await self._db.execute(
            text("DELETE FROM mcp_servers WHERE id = CAST(:id AS uuid) RETURNING id"), {"id": server_id}
        )
        await self._db.commit()
        return result.fetchone() is not None

    async def assign_mcp_to_agent(self, agent_id: str, server_id: str) -> None:
        await self._db.execute(
            text("""
                INSERT INTO agent_mcp_servers (agent_id, mcp_server_id)
                VALUES (CAST(:agent_id AS uuid), CAST(:server_id AS uuid))
                ON CONFLICT DO NOTHING
            """),
            {"agent_id": agent_id, "server_id": server_id},
        )
        await self._db.commit()

    async def unassign_mcp_from_agent(self, agent_id: str, server_id: str) -> None:
        await self._db.execute(
            text("DELETE FROM agent_mcp_servers WHERE agent_id = CAST(:a AS uuid) AND mcp_server_id = CAST(:s AS uuid)"),
            {"a": agent_id, "s": server_id},
        )
        await self._db.commit()

    async def get_agent_mcp_servers(self, agent_id: str) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT m.* FROM mcp_servers m
                JOIN agent_mcp_servers ams ON ams.mcp_server_id = m.id
                WHERE ams.agent_id = CAST(:agent_id AS uuid) AND m.is_active = TRUE
                ORDER BY ams.assigned_at
            """),
            {"agent_id": agent_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    # ── Knowledge Bases ───────────────────────────────────────────────────────

    async def list_knowledge_bases(self) -> list[dict]:
        result = await self._db.execute(
            text("SELECT * FROM knowledge_bases ORDER BY created_at DESC")
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_knowledge_base(self, kb_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT * FROM knowledge_bases WHERE id = CAST(:id AS uuid)"), {"id": kb_id}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def create_knowledge_base(self, data: dict) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO knowledge_bases (name, description, access_mode, rag_spec_json)
                VALUES (:name, :description, :access_mode, CAST(:rag_spec_json AS jsonb))
                RETURNING *
            """),
            data,
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def update_knowledge_base(self, kb_id: str, data: dict) -> Optional[dict]:
        sets, params = [], {"id": kb_id}
        for field in ("name", "description", "status", "access_mode"):
            if field in data:
                sets.append(f"{field} = :{field}")
                params[field] = data[field]
        if "rag_spec_json" in data:
            sets.append("rag_spec_json = CAST(:rag_spec_json AS jsonb)")
            params["rag_spec_json"] = data["rag_spec_json"]
        if not sets:
            return await self.get_knowledge_base(kb_id)
        sets.append("updated_at = NOW()")
        result = await self._db.execute(
            text(f"UPDATE knowledge_bases SET {', '.join(sets)} WHERE id = CAST(:id AS uuid) RETURNING *"),
            params,
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def delete_knowledge_base(self, kb_id: str) -> bool:
        result = await self._db.execute(
            text("DELETE FROM knowledge_bases WHERE id = CAST(:id AS uuid) RETURNING id"), {"id": kb_id}
        )
        await self._db.commit()
        return result.fetchone() is not None

    async def assign_kb_to_agent(self, agent_id: str, kb_id: str) -> None:
        await self._db.execute(
            text("""
                INSERT INTO agent_knowledge_bases (agent_id, kb_id)
                VALUES (CAST(:agent_id AS uuid), CAST(:kb_id AS uuid))
                ON CONFLICT DO NOTHING
            """),
            {"agent_id": agent_id, "kb_id": kb_id},
        )
        await self._db.commit()

    async def unassign_kb_from_agent(self, agent_id: str, kb_id: str) -> None:
        await self._db.execute(
            text("DELETE FROM agent_knowledge_bases WHERE agent_id = CAST(:a AS uuid) AND kb_id = CAST(:k AS uuid)"),
            {"a": agent_id, "k": kb_id},
        )
        await self._db.commit()

    async def get_agent_knowledge_bases(self, agent_id: str) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT kb.*
                FROM knowledge_bases kb
                WHERE kb.access_mode = 'global'
                   OR EXISTS (
                        SELECT 1
                        FROM agent_knowledge_bases akb
                        WHERE akb.kb_id = kb.id
                          AND akb.agent_id = CAST(:agent_id AS uuid)
                   )
                ORDER BY
                    CASE WHEN kb.access_mode = 'global' THEN 0 ELSE 1 END,
                    kb.created_at DESC
            """),
            {"agent_id": agent_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    # ── Behavior Policies ─────────────────────────────────────────────────────

    async def get_agent_policy(self, agent_id: str) -> Optional[dict]:
        result = await self._db.execute(
            text("SELECT * FROM behavior_policies WHERE agent_id = CAST(:agent_id AS uuid)"),
            {"agent_id": agent_id},
        )
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def upsert_agent_policy(self, agent_id: str, data: dict) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO behavior_policies
                    (agent_id, tone, escalation_conditions_json, confirmation_triggers_json,
                     format_requirements, custom_rules_json)
                VALUES
                    (CAST(:agent_id AS uuid), :tone, CAST(:escalation_conditions_json AS jsonb),
                     CAST(:confirmation_triggers_json AS jsonb), :format_requirements, CAST(:custom_rules_json AS jsonb))
                ON CONFLICT (agent_id) DO UPDATE SET
                    tone = EXCLUDED.tone,
                    escalation_conditions_json = EXCLUDED.escalation_conditions_json,
                    confirmation_triggers_json = EXCLUDED.confirmation_triggers_json,
                    format_requirements = EXCLUDED.format_requirements,
                    custom_rules_json = EXCLUDED.custom_rules_json,
                    updated_at = NOW()
                RETURNING *
            """),
            {"agent_id": agent_id, **data},
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def delete_agent_policy(self, agent_id: str) -> None:
        await self._db.execute(
            text("DELETE FROM behavior_policies WHERE agent_id = CAST(:agent_id AS uuid)"),
            {"agent_id": agent_id},
        )
        await self._db.commit()

    # ── Guardrail Rules ───────────────────────────────────────────────────────

    async def list_guardrail_rules(self, agent_id: str) -> list[dict]:
        result = await self._db.execute(
            text("""
                SELECT * FROM guardrail_rules
                WHERE agent_id = CAST(:agent_id AS uuid)
                ORDER BY priority DESC, created_at
            """),
            {"agent_id": agent_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    async def create_guardrail_rule(self, agent_id: str, data: dict) -> dict:
        result = await self._db.execute(
            text("""
                INSERT INTO guardrail_rules
                    (agent_id, name, rule_type, condition_json, action, priority)
                VALUES
                    (CAST(:agent_id AS uuid), :name, :rule_type, CAST(:condition_json AS jsonb), :action, :priority)
                RETURNING *
            """),
            {"agent_id": agent_id, **data},
        )
        await self._db.commit()
        return dict(result.fetchone()._mapping)

    async def update_guardrail_rule(self, rule_id: str, data: dict) -> Optional[dict]:
        sets, params = [], {"id": rule_id}
        for field in ("name", "rule_type", "action", "priority", "is_active"):
            if field in data:
                sets.append(f"{field} = :{field}")
                params[field] = data[field]
        if "condition_json" in data:
            sets.append("condition_json = CAST(:condition_json AS jsonb)")
            params["condition_json"] = data["condition_json"]
        if not sets:
            return None
        result = await self._db.execute(
            text(f"UPDATE guardrail_rules SET {', '.join(sets)} WHERE id = CAST(:id AS uuid) RETURNING *"),
            params,
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def toggle_guardrail_rule(self, rule_id: str, is_active: bool) -> Optional[dict]:
        result = await self._db.execute(
            text("UPDATE guardrail_rules SET is_active = :active WHERE id = CAST(:id AS uuid) RETURNING *"),
            {"active": is_active, "id": rule_id},
        )
        await self._db.commit()
        row = result.fetchone()
        return dict(row._mapping) if row else None

    async def delete_guardrail_rule(self, rule_id: str) -> bool:
        result = await self._db.execute(
            text("DELETE FROM guardrail_rules WHERE id = CAST(:id AS uuid) RETURNING id"),
            {"id": rule_id},
        )
        await self._db.commit()
        return result.fetchone() is not None
