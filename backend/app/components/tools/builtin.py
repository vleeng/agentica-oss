from __future__ import annotations

"""
Component Library — Tools built-in v1.
Cada tool es una LangChain BaseTool lista para ser inyectada en cualquier AgentExecutor.
También son compatibles con CrewAI a través del adaptador en builders/crewai/.
"""

import json
from typing import Any, Optional, Type

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


# ── 1. Web Search (Tavily) ────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    query: str = Field(description="Consulta de búsqueda en lenguaje natural")
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Busca información actualizada en internet. "
        "Úsala cuando necesites datos recientes o verificar hechos."
    )
    args_schema: Type[BaseModel] = WebSearchInput
    api_key: str = ""

    def _run(self, query: str, max_results: int = 5) -> str:
        raise NotImplementedError("Usar arun() para operaciones async")

    async def _arun(self, query: str, max_results: int = 5) -> str:
        if not self.api_key:
            return (
                "[web_search no disponible: no hay clave Tavily configurada. "
                "Respondé con tu conocimiento existente sin usar esta herramienta.]"
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
            return f"[web_search error: {e}. Respondé con tu conocimiento existente.]"


# ── 2. SQL Query ──────────────────────────────────────────────────────────────

class SQLQueryInput(BaseModel):
    query: str = Field(description="Query SQL SELECT (solo lectura)")


class SQLQueryTool(BaseTool):
    name: str = "sql_query"
    description: str = (
        "Ejecuta consultas SQL de solo lectura sobre la base de datos configurada. "
        "Úsala para obtener datos estructurados. Solo permite SELECT."
    )
    args_schema: Type[BaseModel] = SQLQueryInput
    dsn: str = ""
    allowed_tables: list[str] = Field(default_factory=list)

    def _run(self, query: str) -> str:
        raise NotImplementedError("Usar arun()")

    async def _arun(self, query: str) -> str:
        q_upper = query.strip().upper()
        if not q_upper.startswith("SELECT"):
            return "Error: solo se permiten consultas SELECT."

        import asyncpg
        try:
            conn = await asyncpg.connect(self.dsn)
            rows = await conn.fetch(query)
            await conn.close()
            if not rows:
                return "La consulta no devolvió resultados."
            cols = list(rows[0].keys())
            lines = [" | ".join(cols)]
            lines += [" | ".join(str(r[c]) for c in cols) for r in rows[:50]]
            if len(rows) > 50:
                lines.append(f"... ({len(rows) - 50} filas adicionales omitidas)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error en SQL: {str(e)}"


# ── 3. REST API Call ──────────────────────────────────────────────────────────

class RESTAPIInput(BaseModel):
    url: str = Field(description="URL completa del endpoint")
    method: str = Field(default="GET", description="HTTP method: GET, POST, PUT, DELETE")
    body: Optional[dict] = Field(default=None, description="Body JSON para POST/PUT")
    headers: Optional[dict] = Field(default=None, description="Headers adicionales")


class RESTAPITool(BaseTool):
    name: str = "rest_api_call"
    description: str = (
        "Realiza llamadas HTTP a APIs externas. "
        "Úsala para integrar con servicios web o APIs REST."
    )
    args_schema: Type[BaseModel] = RESTAPIInput
    allowed_domains: list[str] = Field(default_factory=list)  # vacío = sin restricción
    default_headers: dict = Field(default_factory=dict)

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Usar arun()")

    async def _arun(
        self,
        url: str,
        method: str = "GET",
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> str:
        if self.allowed_domains:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            if not any(domain.endswith(d) for d in self.allowed_domains):
                return f"Error: dominio {domain} no permitido."

        merged_headers = {**self.default_headers, **(headers or {})}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.request(method, url, json=body, headers=merged_headers)
            try:
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)
            except Exception:
                return resp.text[:2000]


# ── 4. Calculator ─────────────────────────────────────────────────────────────

class CalculatorInput(BaseModel):
    expression: str = Field(description="Expresión matemática a evaluar, ej: 2 + 2 * 10")


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "Evalúa expresiones matemáticas con precisión. "
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


# ── 5. Send Email ─────────────────────────────────────────────────────────────

class SendEmailInput(BaseModel):
    to: str = Field(description="Dirección de email del destinatario")
    subject: str = Field(description="Asunto del email")
    body: str = Field(description="Cuerpo del email en texto plano o HTML")
    html: bool = Field(default=False, description="Si True, el body se envía como HTML")


class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = (
        "Envía un email al destinatario especificado. "
        "Úsala para notificaciones, reportes o comunicaciones automatizadas."
    )
    args_schema: Type[BaseModel] = SendEmailInput
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_address: str = ""

    def _run(self, to: str, subject: str, body: str, html: bool = False) -> str:
        raise NotImplementedError("Usar arun()")

    async def _arun(self, to: str, subject: str, body: str, html: bool = False) -> str:
        if not self.smtp_user or not self.smtp_password:
            return (
                "[send_email no disponible: credenciales SMTP no configuradas. "
                "Indicale al usuario que esta funcionalidad requiere configuración adicional "
                "y ofrecé alternativas manuales si corresponde.]"
            )
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["From"]    = self.from_address or self.smtp_user
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            return f"Email enviado exitosamente a {to}."
        except Exception as e:
            return f"[Error al enviar email: {e}. Informá al usuario y sugerí alternativas.]"


# ── Registry — mapeo nombre → clase ──────────────────────────────────────────

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    "web_search":    WebSearchTool,
    "sql_query":     SQLQueryTool,
    "rest_api_call": RESTAPITool,
    "calculator":    CalculatorTool,
    "send_email":    SendEmailTool,
}


def get_tool(name: str, config: dict) -> BaseTool:
    """Instancia una tool por nombre con su configuración."""
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' no encontrada en la Component Library.")
    cls = TOOL_REGISTRY[name]
    return cls(**config)
