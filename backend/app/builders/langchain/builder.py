from __future__ import annotations

from langchain.agents import AgentExecutor, create_react_agent, create_tool_calling_agent
from langchain.tools import BaseTool
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.components.memory.adapters import (
    InMemoryAdapter,
    MemoryAdapter,
    PostgreSQLAdapter,
    RedisAdapter,
)
from app.components.tools.builtin import get_tool
from app.components.tools.observability import instrument_tool
from app.runtime.langchain.runtime import LangChainRuntime
from app.runtime.llm import LLMConfig, create_chat_llm
from app.schemas.agent import AgentDesign, MemoryType


class LangChainAgentBuilder:
    """
    Toma un AgentDesign y produce un LangChainRuntime listo para ejecutar.
    No genera archivos — construye el ejecutor en memoria.
    (La generación de archivos para deploy ocurre en builders/langchain/codegen.py)
    """

    def __init__(self, redis_client=None, session_factory=None):
        self._redis = redis_client
        self._session_factory = session_factory

    async def build(self, design: AgentDesign, api_key: str = "", llm_config: LLMConfig | None = None) -> LangChainRuntime:
        spec   = design.spec
        fw     = design.framework

        # 1. LLM
        llm_config = llm_config or LLMConfig(provider="anthropic", api_key=api_key)
        llm = create_chat_llm(spec.model_params, llm_config)

        # 2. Tools (library + custom)
        tools: list[BaseTool] = []
        for tool_ref in spec.tools:
            if tool_ref.source == "library":
                tool = instrument_tool(
                    get_tool(tool_ref.name, tool_ref.config),
                    framework="langchain",
                    source="library",
                )
            else:
                tool = instrument_tool(
                    await _load_custom_tool(tool_ref.name, tool_ref.config, design.tenant_id),
                    framework="langchain",
                    source="custom",
                )
            tools.append(tool)

        # RAG tool — inyectada automáticamente si rag.enabled
        if spec.rag.enabled:
            from app.components.rag.rag_tool import RAGTool
            tools.append(
                instrument_tool(
                    RAGTool(agent_id=str(design.agent_id), top_k=spec.rag.top_k),
                    framework="langchain",
                    source="rag",
                )
            )

        extra_tools = getattr(design, "_extra_lc_tools", [])
        if extra_tools:
            tools.extend(
                instrument_tool(tool, framework="langchain", source="mcp")
                for tool in extra_tools
            )

        # 3. Prompt + 4. Runtime según presencia de tools
        # Re-evaluar siempre el agent_type según capacidades del modelo actual,
        # ignorando el valor guardado en el design (puede ser stale de antes del fix).
        from app.services.selector.framework_selector import _supports_function_calling
        agent_type = (
            "openai_functions"
            if _supports_function_calling(spec.model_params.model)
            else (fw.agent_type or "react")
        )

        # Memory adapter
        memory = self._build_memory(design)

        # ── Sin tools → chain simple (mucho más robusto y rápido) ────────────
        if not tools:
            prompt = ChatPromptTemplate.from_messages([
                ("system", self._escape_prompt(design.system_prompt)),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ])
            chain = prompt | llm | StrOutputParser()
            return LangChainRuntime(
                executor=chain,
                memory_adapter=memory,
                spec=spec,
                agent_id=str(design.agent_id),
                session_factory=self._session_factory,
                is_simple_chain=True,
            )

        # ── Con tools → AgentExecutor ────────────────────────────────────────
        if agent_type == "openai_functions":
            prompt = self._build_prompt(design.system_prompt, has_tools=True)
            try:
                agent = create_tool_calling_agent(llm, tools, prompt)
            except Exception:
                # Fallback a react si el modelo no soporta tool calling
                prompt = self._build_react_prompt(design.system_prompt)
                agent = create_react_agent(llm, tools, prompt)
        else:
            prompt = self._build_react_prompt(design.system_prompt)
            agent = create_react_agent(llm, tools, prompt)

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=4,        # límite bajo para evitar loops largos con tools que fallan
            max_execution_time=60,   # 60s max por ejecución de agente
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

        return LangChainRuntime(
            executor=executor,
            memory_adapter=memory,
            spec=spec,
            agent_id=str(design.agent_id),
            session_factory=self._session_factory,
        )

    @staticmethod
    def _escape_prompt(system_prompt: str) -> str:
        """Escapa llaves del system prompt para que LangChain no las interprete como variables."""
        return system_prompt.replace("{", "{{").replace("}", "}}")

    def _build_prompt(self, system_prompt: str, has_tools: bool) -> ChatPromptTemplate:
        messages = [
            ("system", self._escape_prompt(system_prompt)),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
        if has_tools:
            messages.append(MessagesPlaceholder("agent_scratchpad"))
        return ChatPromptTemplate.from_messages(messages)

    def _build_react_prompt(self, system_prompt: str) -> ChatPromptTemplate:
        """Prompt para create_react_agent — requiere {tools}, {tool_names}, {input} y {agent_scratchpad}.
        Nota: agent_scratchpad es un string en react (no lista), por eso va en human message."""
        react_system = (
            f"{self._escape_prompt(system_prompt)}\n\n"
            "Tenés acceso a las siguientes herramientas:\n\n"
            "{tools}\n\n"
            "REGLAS ESTRICTAS — seguí EXACTAMENTE este formato, sin excepciones:\n\n"
            "Thought: [tu razonamiento]\n"
            "Action: [una de: {tool_names}]\n"
            "Action Input: [input para la herramienta]\n"
            "Observation: [resultado — lo agrega el sistema automáticamente]\n"
            "Thought: [razonamiento tras ver el resultado]\n"
            "Final Answer: [tu respuesta final completa]\n\n"
            "CRÍTICO:\n"
            "- Después de cada 'Thought:' SIEMPRE escribí 'Action:' O 'Final Answer:'. NUNCA otro texto.\n"
            "- En cuanto tengas información suficiente de una herramienta, escribí 'Final Answer:' inmediatamente.\n"
            "- NUNCA respondas directamente sin usar 'Final Answer:'.\n"
            "- Si la herramienta devolvió contexto relevante, úsalo para armar la 'Final Answer:' de inmediato.\n"
            "- NO repitas llamadas a herramientas si ya tenés la información necesaria."
        )
        return ChatPromptTemplate.from_messages([
            ("system", react_system),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}\n\n{agent_scratchpad}"),
        ])

    def _build_memory(self, design: AgentDesign) -> MemoryAdapter:
        mem_type = design.spec.memory.type
        ttl = design.spec.memory.ttl_seconds
        max_msg = design.spec.memory.max_messages
        agent_id = str(design.agent_id)

        if mem_type == MemoryType.none:
            return InMemoryAdapter(max_messages=0)

        if mem_type == MemoryType.session and self._redis:
            return RedisAdapter(
                redis_client=self._redis,
                ttl_seconds=ttl or 3600,
                max_messages=max_msg,
            )

        if mem_type in (MemoryType.persistent, MemoryType.summary) and self._session_factory:
            return PostgreSQLAdapter(
                session_factory=self._session_factory,
                agent_id=agent_id,
                max_messages=max_msg,
            )

        # Fallback seguro
        return InMemoryAdapter(max_messages=max_msg)


async def _load_custom_tool(name: str, config: dict, tenant_id: str):
    """Carga una custom tool desde la DB del tenant."""
    from app.db.session import get_tenant_session_factory
    from app.db.repository import AgentRepository
    from app.components.tools.custom_loader import build_tool_from_code

    factory = get_tenant_session_factory(tenant_id)
    async with factory() as db:
        repo = AgentRepository(db)
        row = await repo.get_custom_tool(name)
    if not row:
        raise ValueError(f"Custom tool '{name}' no encontrada para el tenant")
    if not row["is_active"]:
        raise ValueError(f"Custom tool '{name}' está desactivada")
    return build_tool_from_code(row["source_code"], config)
