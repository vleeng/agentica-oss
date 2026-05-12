from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.components.tools.observability import instrument_tool  # noqa: E402


class DummyTool:
    name = "dummy_tool"

    def __init__(self):
        self.sync_calls = 0
        self.async_calls = 0

    def _run(self, payload: str) -> str:
        self.sync_calls += 1
        if payload == "boom":
            raise ValueError("sync failure")
        return payload.upper()

    async def _arun(self, payload: str) -> str:
        self.async_calls += 1
        if payload == "boom":
            raise ValueError("async failure")
        return payload.lower()


class ToolObservabilityTest(unittest.TestCase):
    def test_instrument_tool_is_idempotent(self):
        tool = DummyTool()
        wrapped = instrument_tool(tool, framework="langchain", source="library")
        wrapped_again = instrument_tool(wrapped, framework="langchain", source="library")
        self.assertIs(wrapped, wrapped_again)

    def test_instrument_tool_logs_sync_success(self):
        tool = instrument_tool(DummyTool(), framework="langchain", source="library")
        with self.assertLogs("app.components.tools.observability", level="INFO") as captured:
            result = tool._run("hola")
        self.assertEqual(result, "HOLA")
        self.assertTrue(any("[Tool] start name=dummy_tool" in line for line in captured.output))
        self.assertTrue(any("[Tool] success name=dummy_tool" in line for line in captured.output))

    def test_instrument_tool_logs_sync_failure(self):
        tool = instrument_tool(DummyTool(), framework="langchain", source="library")
        with self.assertLogs("app.components.tools.observability", level="ERROR") as captured:
            with self.assertRaises(ValueError):
                tool._run("boom")
        self.assertTrue(any("[Tool] failure name=dummy_tool" in line for line in captured.output))

    def test_instrument_tool_logs_async_success(self):
        tool = instrument_tool(DummyTool(), framework="crewai", source="rag")

        async def execute():
            return await tool._arun("HOLA")

        with self.assertLogs("app.components.tools.observability", level="INFO") as captured:
            result = asyncio.run(execute())
        self.assertEqual(result, "hola")
        self.assertTrue(any("mode=async" in line for line in captured.output))
        self.assertTrue(any("[Tool] success name=dummy_tool" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
