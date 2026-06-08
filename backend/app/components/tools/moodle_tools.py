from __future__ import annotations

import asyncio
import json
import logging
import os
import httpx
import hashlib
from typing import Any, Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

from app.core.config import get_settings
from app.core.product_profile import get_product_profile_state
from app.runtime.store import get_runtime_store
import contextvars

logger = logging.getLogger(__name__)

# ContextVar to hold the Moodle user context for the current request/session.
# Fail closed unless a trusted request sets it explicitly.
moodle_user_context = contextvars.ContextVar("moodle_user_context", default=None)

DEFAULT_TTLS = {
    "get_courses": 600,
    "get_course": 600,
    "get_course_participants": 300,
    "get_assignments": 900,
    "get_course_completion": 900,
}

_moodle_catalog_cache: dict[str, dict] = {}


def is_moodle_integration_enabled() -> bool:
    return get_product_profile_state().features.moodle_integration


def resolve_moodle_user_id(agentica_user_id: str | None) -> Optional[str]:
    if not agentica_user_id:
        return None

    raw_map = os.getenv("MOODLE_USER_MAP_JSON", "{}")
    try:
        mapping = json.loads(raw_map)
    except json.JSONDecodeError:
        logger.warning("MOODLE_USER_MAP_JSON no es valido; se ignora el mapeo.")
        mapping = {}

    if isinstance(mapping, dict):
        mapped = mapping.get(agentica_user_id)
        if mapped is None:
            mapped = mapping.get(str(agentica_user_id))
        if mapped is not None:
            mapped_str = str(mapped).strip()
            return mapped_str or None

    fallback = os.getenv("MOODLE_DEFAULT_USER_ID", "").strip()
    return fallback or None


def get_moodle_ttl(tool_id: str) -> int:
    return DEFAULT_TTLS.get(tool_id, 300)


def json_schema_to_pydantic(schema_dict: dict | None, model_name: str) -> Type[BaseModel]:
    if not schema_dict or not isinstance(schema_dict, dict):
        return create_model(model_name)

    properties = schema_dict.get("properties", {})
    required = schema_dict.get("required", [])

    fields = {}
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        prop_type = prop.get("type", "string")
        desc = prop.get("description", "")

        if prop_type == "integer":
            py_type = int
        elif prop_type == "number":
            py_type = float
        elif prop_type == "boolean":
            py_type = bool
        elif prop_type == "array":
            py_type = list
        else:
            py_type = str

        if name in required:
            fields[name] = (py_type, Field(..., description=desc))
        else:
            default_val = prop.get("default", None)
            fields[name] = (Optional[py_type], Field(default=default_val, description=desc))

    return create_model(model_name, **fields)


def discover_moodle_tools_sync(moodle_url: str, api_key: str, timeout: int = 5) -> list[dict]:
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json"
    }
    with httpx.Client(timeout=timeout) as client:
        try:
            resp = client.get(f"{moodle_url.rstrip('/')}/local/aiquery/api/catalog.php", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.warning(f"Moodle discover_tools_sync failed at {moodle_url}: {e}")
            return []


async def call_moodle_tool(
    moodle_url: str,
    api_key: str,
    tool_id: str,
    parameters: dict,
    user_id: str,
    timeout: int = 30
) -> str:
    if not user_id:
        return "Error: el contexto Moodle no está configurado para esta petición."

    headers = {
        "X-API-KEY": api_key,
        "X-MOODLE-USER-ID": str(user_id),
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{moodle_url.rstrip('/')}/local/aiquery/api/execute.php",
            json={"tool_id": tool_id, "parameters": parameters},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return json.dumps(data.get("data", []), ensure_ascii=False, indent=2)
        else:
            return f"Error: {data.get('error', 'Unknown error execution')}"


def build_moodle_tool(tool_meta: dict) -> BaseTool:
    tool_name = tool_meta["tool_id"]
    tool_description = tool_meta.get("description", tool_name)
    schema_dict = tool_meta.get("parameters_schema", {})

    args_model = json_schema_to_pydantic(schema_dict, f"Moodle_{tool_name}_Input")

    class _MoodleTool(BaseTool):
        name: str = Field(default=tool_name)
        description: str = Field(default=tool_description)
        args_schema: Type[BaseModel] = args_model

        def _run(self, **kwargs: Any) -> str:
            return asyncio.run(self._arun(**kwargs))

        async def _arun(self, **kwargs: Any) -> str:
            if not is_moodle_integration_enabled():
                return "Error: la integración con Moodle está deshabilitada para este perfil."

            settings = get_settings()
            moodle_url = getattr(settings, "moodle_url", "http://localhost:8080")
            moodle_api_key = getattr(settings, "moodle_api_key", "moodle-ai-query-secret-key-2026")

            user_id = moodle_user_context.get()
            if not user_id:
                return "Error: no hay un usuario Moodle asociado a esta sesión."

            try:
                store = get_runtime_store()
                redis = store.redis_client
            except Exception:
                redis = None

            cache_key = None
            if redis:
                try:
                    param_str = json.dumps(kwargs, sort_keys=True)
                    param_hash = hashlib.md5(param_str.encode()).hexdigest()
                    cache_key = f"moodle_cache:{user_id}:{tool_name}:{param_hash}"

                    cached = await redis.get(cache_key)
                    if cached:
                        logger.info(f"Moodle cache hit for {tool_name} with params {kwargs}")
                        return cached
                except Exception as e:
                    logger.warning(f"Failed to read from Redis cache: {e}")

            try:
                result = await call_moodle_tool(moodle_url, moodle_api_key, tool_name, kwargs, user_id)

                if redis and cache_key and not result.startswith("Error:"):
                    try:
                        ttl = get_moodle_ttl(tool_name)
                        await redis.setex(cache_key, ttl, result)
                    except Exception as e:
                        logger.warning(f"Failed to save to Redis cache: {e}")

                return result
            except Exception as e:
                logger.error(f"Failed to call Moodle tool {tool_name}: {e}")
                return f"Error al ejecutar la herramienta: {e}"

    _MoodleTool.__name__ = f"MoodleTool_{tool_name}"
    return _MoodleTool()


def get_moodle_tool(name: str) -> Optional[BaseTool]:
    global _moodle_catalog_cache
    if not is_moodle_integration_enabled():
        return None

    settings = get_settings()
    moodle_url = getattr(settings, "moodle_url", "http://localhost:8080")
    moodle_api_key = getattr(settings, "moodle_api_key", "moodle-ai-query-secret-key-2026")

    if name in _moodle_catalog_cache:
        return build_moodle_tool(_moodle_catalog_cache[name])

    catalog = discover_moodle_tools_sync(moodle_url, moodle_api_key)
    for tool_meta in catalog:
        tool_id = tool_meta.get("tool_id")
        if tool_id:
            _moodle_catalog_cache[tool_id] = tool_meta

    if name in _moodle_catalog_cache:
        return build_moodle_tool(_moodle_catalog_cache[name])

    return None
