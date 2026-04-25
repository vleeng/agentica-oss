from __future__ import annotations

from langchain.agents import AgentExecutor, create_openai_functions_agent, create_react_agent
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.components.memory.adapters import (
    InMemoryAdapter,
    MemoryAdapter,
    PostgreSQLAdapter,
    RedisAdapter,
)
from app.components.tools.builtin import get_tool
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
                tool = get_tool(tool_ref.name, tool_ref.config)
            else:
                tool = await _load_custom_tool(tool_ref.name, tool_ref.config, design.tenant_id)
            tools.append(tool)

        # RAG tool — inyectada automáticamente si rag.enabled
        if spec.rag.enabled:
            from app.components.rag.rag_tool import RAGTool
            tools.append(RAGTool(agent_id=str(design.agent_id), top_k=spec.rag.top_k))

        extra_tools = getattr(design, "_extra_lc_tools", [])
        if extra_tools:
            tools.extend(extra_tools)

        # 3. Prompt + 4. AgentExecutor según agent_type
        agent_type = fw.agent_type or "openai_functions"
        if agent_type == "openai_functions":
            prompt = self._build_prompt(design.system_prompt, has_tools=bool(tools))
            agent = create_openai_functions_agent(llm, tools, prompt)
        else:
            prompt = self._build_react_prompt(design.system_prompt)
            agent = create_react_agent(llm, tools, prompt)

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=10,
            max_execution_time=120,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

        # 5. Memory adapter
        memory = self._build_memory(design)

        return LangChainRuntime(
            executor=executor,
            memory_adapter=memory,
            spec=spec,
            agent_id=str(design.agent_id),
            session_factory=self._session_factory,
        )

    def _build_prompt(self, system_prompt: str, has_tools: bool) -> ChatPromptTemplate:
        messages = [
            ("system", system_prompt),
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
            f"{system_prompt}\n\n"
            "Tenés acceso a las siguientes herramientas:\n\n"
            "{tools}\n\n"
            "Usá el siguiente formato:\n"
            "Thought: siempre pensá qué debés hacer\n"
            "Action: la acción a tomar, debe ser una de [{tool_names}]\n"
            "Action Input: el input de la acción\n"
            "Observation: el resultado de la acción\n"
            "... (este ciclo puede repetirse N veces)\n"
            "Thought: ya sé la respuesta final\n"
            "Final Answer: la respuesta final a la pregunta original"
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
