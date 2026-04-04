from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

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
                VALUES (:id, :name, :desc, :mode, :fw, 'draft', :spec::jsonb, :design::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    design_json = EXCLUDED.design_json,
                    updated_at  = NOW()
            """),
            {
                "id":     agent_id,
                "name":   spec.name,
                "desc":   spec.description,
                "mode":   spec.mode.value,
                "fw":     design.framework.framework,
                "spec":   spec.model_dump_json(),
                "design": design.model_dump_json(),
            },
        )
        await self._db.commit()
        return {"agent_id": agent_id, "status": "draft"}

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
            text("UPDATE agents SET status = :status, updated_at = NOW() WHERE id = :id"),
            {"status": status, "id": agent_id},
        )
        await self._db.commit()

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

    # ── Eval runs ─────────────────────────────────────────────────────────────

    async def save_eval_run(self, agent_id: str, build_id: str, report: dict) -> str:
        run_id = str(uuid.uuid4())
        await self._db.execute(
            text("""
                INSERT INTO eval_runs (id, agent_id, build_id, score, passed, report_json)
                VALUES (:id, :agent_id, :build_id, :score, :passed, :report::jsonb)
            """),
            {
                "id":       run_id,
                "agent_id": agent_id,
                "build_id": build_id,
                "score":    report.get("overall_score", 0),
                "passed":   report.get("pass_threshold", False),
                "report":   json.dumps(report),
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
        result = await self._db.execute(
            text("""
                SELECT
                    COUNT(*) as calls,
                    COALESCE(SUM(tokens_in), 0)  as total_tokens_in,
                    COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                    COALESCE(SUM(cost_usd), 0)   as total_cost_usd
                FROM billing_events
                WHERE (:agent_id IS NULL OR agent_id = :agent_id::uuid)
            """),
            {"agent_id": agent_id},
        )
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
            text("SELECT * FROM custom_tools WHERE id = :id::uuid"),
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
                    (:name, :desc, :code, :schema::jsonb, :test)
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
        if config_schema is not None: sets.append("config_schema = :schema::jsonb"); params["schema"] = json.dumps(config_schema)
        if is_active    is not None: sets.append("is_active = :active");    params["active"] = is_active
        if test_input   is not None: sets.append("test_input = :test");     params["test"]   = test_input
        if last_error   is not None: sets.append("last_error = :err");      params["err"]    = last_error
        if not sets:
            return await self.get_custom_tool_by_id(tool_id)
        sets.append("updated_at = NOW()")
        result = await self._db.execute(
            text(f"""
                UPDATE custom_tools SET {', '.join(sets)}
                WHERE id = :id::uuid
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
            text("DELETE FROM custom_tools WHERE id = :id::uuid RETURNING id"),
            {"id": tool_id},
        )
        await self._db.commit()
        return result.fetchone() is not None
