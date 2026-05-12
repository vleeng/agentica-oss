from __future__ import annotations

"""
Component Library - Built-in tools.

Las tools se instancian como BaseTool de LangChain y, cuando hace falta,
exponen adaptadores mas simples para CrewAI.
"""

import asyncio
import json
from typing import Any, Optional, Type

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.mailer import MailerNotConfiguredError, is_mailer_configured, send_email
from app.components.tools.policies import (
    extract_search_payload,
    is_private_host,
    query_uses_allowed_tables,
)


class WebSearchInput(BaseModel):
    query: str = Field(description="Consulta de busqueda en lenguaje natural")
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Busca informacion actualizada en internet. "
        "Usala cuando necesites datos recientes o verificar hechos."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    api_key: str = ""

    def _run(self, query: str, max_results: int = 5) -> str:
        return asyncio.run(self._arun(query=query, max_results=max_results))

    async def _arun(self, query: str, max_results: int = 5) -> str:
        if not self.api_key:
            return (
                "[web_search no disponible: no hay clave Tavily configurada. "
                "Responde con tu conocimiento existente sin usar esta herramienta.]"
            )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": self.api_key, "query": query, "max_results": max_results},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                return "\n\n".join(
                    f"**{r['title']}**\n{r['content']}\nFuente: {r['url']}"
                    for r in results
                ) or "Sin resultados."
        except Exception as e:
            return f"[web_search error: {e}. Responde con tu conocimiento existente.]"


class CrewAIWebSearchInput(BaseModel):
    query: str = Field(
        description=(
            "Consulta de busqueda en lenguaje natural. "
            "Tambien acepta JSON serializado con una clave 'query'."
        )
    )


class CrewAIWebSearchTool(BaseTool):
    """
    CrewAI trabaja con mas estabilidad con tools de un solo argumento y
    ejecucion sincronica.
    """

    name: str = "web_search"
    description: str = (
        "Busca informacion actualizada en internet. "
        "Recibe una consulta simple y devuelve hallazgos resumidos."
    )
    args_schema: Type[BaseModel] = CrewAIWebSearchInput
    api_key: str = ""

    def _run(self, query: str) -> str:
        normalized_query, max_results = _extract_search_payload(query)
        if not normalized_query:
            return "[web_search error: consulta vacia. Pedi una busqueda concreta.]"
        return asyncio.run(self._arun(normalized_query, max_results=max_results))

    async def _arun(self, query: str, max_results: int = 5) -> str:
        delegate = WebSearchTool(api_key=self.api_key)
        return await delegate._arun(query=query, max_results=max_results)


class SQLQueryInput(BaseModel):
    query: str = Field(description="Query SQL SELECT de solo lectura")


class SQLQueryTool(BaseTool):
    name: str = "sql_query"
    description: str = (
        "Ejecuta consultas SQL de solo lectura sobre la base de datos configurada. "
        "Usala para obtener datos estructurados. Solo permite SELECT."
    )
    args_schema: Type[BaseModel] = SQLQueryInput
    dsn: str = ""
    allowed_tables: list[str] = Field(default_factory=list)

    def _run(self, query: str) -> str:
        return asyncio.run(self._arun(query))

    async def _arun(self, query: str) -> str:
        if not self.dsn:
            return (
                "[sql_query no disponible: no hay datasource configurado. "
                "Defini un DSN seguro antes de usar esta herramienta.]"
            )

        q_upper = query.strip().upper()
        if not q_upper.startswith("SELECT"):
            return "Error: solo se permiten consultas SELECT."

        if not query_uses_allowed_tables(query, self.allowed_tables):
            allowed = ", ".join(self.allowed_tables) or "ninguna"
            return f"Error: la consulta referencia tablas fuera de la allowlist. Tablas permitidas: {allowed}."

        import asyncpg

        try:
            conn = await asyncpg.connect(self.dsn)
            rows = await conn.fetch(query)
            await conn.close()
            if not rows:
                return "La consulta no devolvio resultados."
            cols = list(rows[0].keys())
            lines = [" | ".join(cols)]
            lines += [" | ".join(str(r[c]) for c in cols) for r in rows[:50]]
            if len(rows) > 50:
                lines.append(f"... ({len(rows) - 50} filas adicionales omitidas)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error en SQL: {e}"


class RESTAPIInput(BaseModel):
    url: str = Field(description="URL completa del endpoint")
    method: str = Field(default="GET", description="HTTP method: GET, POST, PUT, DELETE")
    body: Optional[dict] = Field(default=None, description="Body JSON para POST o PUT")
    headers: Optional[dict] = Field(default=None, description="Headers adicionales")


class RESTAPITool(BaseTool):
    name: str = "rest_api_call"
    description: str = (
        "Realiza llamadas HTTP a APIs externas. "
        "Usala para integrar con servicios web o APIs REST."
    )
    args_schema: Type[BaseModel] = RESTAPIInput
    allowed_domains: list[str] = Field(default_factory=list)
    default_headers: dict = Field(default_factory=dict)
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    allow_unrestricted: bool = False

    def _run(self, **kwargs: Any) -> str:
        return asyncio.run(self._arun(**kwargs))

    async def _arun(
        self,
        url: str,
        method: str = "GET",
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        normalized_method = (method or "GET").upper()
        if normalized_method not in {m.upper() for m in self.allowed_methods}:
            allowed = ", ".join(self.allowed_methods)
            return f"Error: metodo HTTP no permitido. Metodos habilitados: {allowed}."

        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "Error: la URL debe ser http(s) valida."

        hostname = parsed.hostname or ""
        if not self.allow_unrestricted:
            if not self.allowed_domains:
                return (
                    "[rest_api_call no disponible: faltan dominios permitidos. "
                    "Defini allowed_domains o habilita explicitamente un modo unrestricted.]"
                )
            if not any(hostname == d or hostname.endswith(f".{d}") for d in self.allowed_domains):
                return f"Error: dominio {hostname} no permitido."
            if is_private_host(hostname):
                return f"Error: no se permiten destinos privados o locales ({hostname})."

        merged_headers = {**self.default_headers, **(headers or {})}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(normalized_method, url, json=body, headers=merged_headers)
            try:
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)
            except Exception:
                return resp.text[:2000]


class CalculatorInput(BaseModel):
    expression: str = Field(description="Expresion matematica a evaluar, ej: 2 + 2 * 10")


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "Evalua expresiones matematicas con precision. "
        "Soporta +, -, *, /, **, sqrt(), log(), round(), etc."
    )
    args_schema: Type[BaseModel] = CalculatorInput

    def _run(self, expression: str) -> str:
        import math

        safe_globals = {
            "__builtins__": {},
            "sqrt": math.sqrt,
            "log": math.log,
            "log10": math.log10,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e,
            "round": round,
            "abs": abs,
            "pow": pow,
        }
        try:
            result = eval(expression, safe_globals)  # noqa: S307
            return str(result)
        except Exception as ex:
            return f"Error al evaluar '{expression}': {ex}"

    async def _arun(self, expression: str) -> str:
        return self._run(expression)


class SendEmailInput(BaseModel):
    to: str = Field(description="Direccion de email del destinatario")
    subject: str = Field(description="Asunto del email")
    body: str = Field(description="Cuerpo del email en texto plano o HTML")
    html: bool = Field(default=False, description="Si True, el body se envia como HTML")


class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = (
        "Envia un email al destinatario especificado. "
        "Usala para notificaciones, reportes o comunicaciones automatizadas."
    )
    args_schema: Type[BaseModel] = SendEmailInput

    def _run(self, to: str, subject: str, body: str, html: bool = False) -> str:
        return asyncio.run(self._arun(to=to, subject=subject, body=body, html=html))

    async def _arun(self, to: str, subject: str, body: str, html: bool = False) -> str:
        if not is_mailer_configured():
            return (
                "[send_email no disponible: el mailer global no esta configurado. "
                "Pedile a un administrador que complete SMTP en la configuracion del servidor.]"
            )

        try:
            await send_email(
                to_email=to,
                subject=subject,
                text_body=body,
                html_body=body if html else None,
            )
            return f"Email enviado exitosamente a {to}."
        except MailerNotConfiguredError:
            return (
                "[send_email no disponible: el mailer global no esta configurado. "
                "Pedile a un administrador que complete SMTP en la configuracion del servidor.]"
            )
        except Exception as e:
            return f"[Error al enviar email: {e}. Informa al usuario y sugeri alternativas.]"


TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    "web_search": WebSearchTool,
    "sql_query": SQLQueryTool,
    "rest_api_call": RESTAPITool,
    "calculator": CalculatorTool,
    "send_email": SendEmailTool,
}


def get_tool(name: str, config: dict, framework: str = "langchain") -> BaseTool:
    """Instancia una tool por nombre con su configuracion."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' no encontrada en la Component Library.")

    hydrated_config = dict(config or {})
    settings = get_settings()

    if name == "web_search" and not hydrated_config.get("api_key"):
        hydrated_config["api_key"] = settings.tavily_api_key or ""

    if framework == "crewai" and name == "web_search":
        return CrewAIWebSearchTool(**hydrated_config)

    cls = TOOL_REGISTRY[name]
    return cls(**hydrated_config)
