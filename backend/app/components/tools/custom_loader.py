from __future__ import annotations

"""
Custom Tool Loader — carga tools Python subidas por el usuario.

Flujo:
  1. validate_tool_code(source) — análisis AST, rechaza módulos peligrosos
  2. build_tool_from_code(source, config) → BaseTool listo para LangChain/CrewAI
  3. Timeout de 30 s por invocación para evitar tools colgadas
"""

import ast
import asyncio
import types
import logging
from typing import Any, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Módulos prohibidos ────────────────────────────────────────────────────────

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "importlib", "builtins", "socket", "multiprocessing",
    "threading", "ctypes", "signal", "pty", "atexit",
    "gc", "inspect", "traceback",
}

FORBIDDEN_BUILTINS = {"exec", "eval", "compile", "__import__", "open", "breakpoint"}

REQUIRED_NAMES = {"TOOL_NAME", "TOOL_DESCRIPTION", "run"}

CUSTOM_TOOL_TIMEOUT = 30.0   # segundos


# ── Validación AST ────────────────────────────────────────────────────────────

def validate_tool_code(source_code: str) -> tuple[bool, str]:
    """
    Valida el código Python del usuario antes de ejecutarlo.
    Retorna (is_valid, error_message).
    """
    # 1. Parsear — detecta errores de sintaxis
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return False, f"Error de sintaxis en línea {e.lineno}: {e.msg}"

    # 2. Recorrer el AST buscando patrones prohibidos
    for node in ast.walk(tree):

        # Imports prohibidos
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in FORBIDDEN_MODULES:
                    return False, (
                        f"Import prohibido: '{alias.name}'.\n"
                        f"Módulos no permitidos: {sorted(FORBIDDEN_MODULES)}"
                    )

        if isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in FORBIDDEN_MODULES:
                return False, f"Import prohibido: '{node.module}'"

        # Funciones built-in prohibidas
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in FORBIDDEN_BUILTINS:
                return False, f"Función no permitida: '{name}()'"

    # 3. Verificar presencia de TOOL_NAME, TOOL_DESCRIPTION, run()
    top_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    top_names.add(t.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_names.add(node.name)

    missing = REQUIRED_NAMES - top_names
    if missing:
        return False, (
            f"Faltan definiciones obligatorias: {sorted(missing)}.\n"
            "El código debe tener TOOL_NAME, TOOL_DESCRIPTION y async def run(...)."
        )

    # 4. run() debe ser async
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            return False, (
                "La función 'run' debe ser asíncrona: 'async def run(...)'"
            )

    return True, ""


# ── Builder dinámico ──────────────────────────────────────────────────────────

def build_tool_from_code(source_code: str, config: dict) -> BaseTool:
    """
    Compila el código del usuario y retorna un BaseTool de LangChain.
    Lanza ValueError si el código no pasa la validación.
    """
    valid, error = validate_tool_code(source_code)
    if not valid:
        raise ValueError(f"Código de tool inválido: {error}")

    # Compilar en módulo en memoria con builtins seguros
    safe_builtins = {
        k: v for k, v in __builtins__.items()   # type: ignore[attr-defined]
        if k not in FORBIDDEN_BUILTINS
    } if isinstance(__builtins__, dict) else {
        k: getattr(__builtins__, k)
        for k in dir(__builtins__)
        if k not in FORBIDDEN_BUILTINS
    }

    module_globals: dict[str, Any] = {"__builtins__": safe_builtins}
    module = types.ModuleType("custom_tool")
    module.__dict__.update(module_globals)

    try:
        exec(compile(source_code, "<custom_tool>", "exec"), module.__dict__)  # noqa: S102
    except Exception as e:
        raise ValueError(f"Error al compilar la tool: {e}") from e

    tool_name = str(module.__dict__.get("TOOL_NAME", "custom_tool"))
    tool_desc = str(module.__dict__.get("TOOL_DESCRIPTION", "Custom tool"))
    user_run  = module.__dict__.get("run")

    if not callable(user_run):
        raise ValueError("'run' no es una función callable")

    # Capturar config en closure
    _config = config

    # ── Clase dinámica ────────────────────────────────────────────────────────

    class _DynamicInput(BaseModel):
        input: str = Field(description="Input para la tool")

    class _DynamicTool(BaseTool):
        name: str = tool_name
        description: str = tool_desc
        args_schema: Type[BaseModel] = _DynamicInput

        def _run(self, input: str) -> str:  # noqa: A002
            raise NotImplementedError("Usar _arun()")

        async def _arun(self, input: str) -> str:  # noqa: A002
            try:
                result = await asyncio.wait_for(
                    user_run(input=input, config=_config),
                    timeout=CUSTOM_TOOL_TIMEOUT,
                )
                return str(result)
            except asyncio.TimeoutError:
                return f"Error: la tool '{tool_name}' superó el tiempo límite de {CUSTOM_TOOL_TIMEOUT}s"
            except Exception as e:
                logger.error(f"[CustomTool:{tool_name}] Error en ejecución: {e}")
                return f"Error al ejecutar la tool: {e}"

    return _DynamicTool()
