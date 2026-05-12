from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def instrument_tool(tool: Any, *, framework: str, source: str) -> Any:
    """
    Envuelve _run/_arun para dejar trazas homogéneas de uso y error.

    Es idempotente para evitar doble wrapping cuando una tool pasa por
    varias capas de construcción.
    """
    if getattr(tool, "__agentica_observed__", False):
        return tool

    tool_name = getattr(tool, "name", tool.__class__.__name__)
    original_run = getattr(tool, "_run", None)
    original_arun = getattr(tool, "_arun", None)

    if callable(original_run):
        def logged_run(*args, **kwargs):
            start = time.monotonic()
            logger.info(
                "[Tool] start name=%s framework=%s source=%s mode=sync",
                tool_name,
                framework,
                source,
            )
            try:
                result = original_run(*args, **kwargs)
                logger.info(
                    "[Tool] success name=%s framework=%s source=%s mode=sync duration_ms=%.2f",
                    tool_name,
                    framework,
                    source,
                    (time.monotonic() - start) * 1000,
                )
                return result
            except Exception:
                logger.exception(
                    "[Tool] failure name=%s framework=%s source=%s mode=sync duration_ms=%.2f",
                    tool_name,
                    framework,
                    source,
                    (time.monotonic() - start) * 1000,
                )
                raise

        object.__setattr__(tool, "_run", logged_run)

    if callable(original_arun):
        async def logged_arun(*args, **kwargs):
            start = time.monotonic()
            logger.info(
                "[Tool] start name=%s framework=%s source=%s mode=async",
                tool_name,
                framework,
                source,
            )
            try:
                result = await original_arun(*args, **kwargs)
                logger.info(
                    "[Tool] success name=%s framework=%s source=%s mode=async duration_ms=%.2f",
                    tool_name,
                    framework,
                    source,
                    (time.monotonic() - start) * 1000,
                )
                return result
            except Exception:
                logger.exception(
                    "[Tool] failure name=%s framework=%s source=%s mode=async duration_ms=%.2f",
                    tool_name,
                    framework,
                    source,
                    (time.monotonic() - start) * 1000,
                )
                raise

        object.__setattr__(tool, "_arun", logged_arun)

    object.__setattr__(tool, "__agentica_observed__", True)
    return tool
