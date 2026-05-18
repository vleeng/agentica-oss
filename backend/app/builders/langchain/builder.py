from __future__ import annotations

import logging

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

logger = logging.getLogger(__name__)


class LangChainAgentBuilder:
    """
    Toma un AgentDesign y produce un LangChainRuntime listo para ejecutar.
    No genera archivos: construye el ejecutor en memoria.
    """

    def __init__(self, redis_client=None, session_factory=None):
        self._redis = redis_client
        self._session_factory = session_factory

    async def build(self, design: AgentDesign, api_key: str = "", llm_config: LLMConfig | None = None) -> LangChainRuntime:
        spec = design.spec
        fw = design.framework
        graph_uses_knowledge_base = self._graph_uses_tool(design, "knowledge_base")

        llm_config = llm_config or LLMConfig(provider="anthropic", api_key=api_key)
        llm = create_chat_llm(spec.model_params, llm_config)

        selected_mode = getattr(spec, "single_agent_mode", None)
        selected_mode_value = getattr(selected_mode, "value", selected_mode)
        if fw.agent_type:
            agent_type = fw.agent_type
        elif selected_mode_value == "direct":
            agent_type = "direct"
        else:
            from app.services.selector.framework_selector import _supports_function_calling

            agent_type = (
                "openai_functions"
                if _supports_function_calling(spec.model_params.model)
                else "react"
            )

        memory = self._build_memory(design)

        if agent_type == "direct":
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

        if spec.rag.enabled or graph_uses_knowledge_base:
            from app.components.rag.rag_tool import RAGTool

            tools.append(
                instrument_tool(
                    RAGTool(
                        agent_id=str(design.agent_id),
                        top_k=spec.rag.top_k,
                        session_factory=self._session_factory,
                    ),
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

        tools_by_name = {tool.name: tool for tool in tools}
        logger.warning(
            "[LangChainBuilder] agent_id=%s mode=%s selected_mode=%s agent_type=%s rag_enabled=%s graph_uses_kb=%s graph_nodes=%s tools=%s",
            design.agent_id,
            spec.mode.value,
            selected_mode_value,
            agent_type,
            getattr(spec.rag, "enabled", False),
            graph_uses_knowledge_base,
            len((design.graph_blueprint or {}).get("nodes", []) if isinstance(design.graph_blueprint, dict) else []),
            sorted(tools_by_name.keys()),
        )

        if self._should_use_graph_runtime(design):
            logger.warning(
                "[LangChainBuilder] agent_id=%s using graph runtime",
                design.agent_id,
            )
            return LangChainRuntime(
                executor=None,
                memory_adapter=memory,
                spec=spec,
                agent_id=str(design.agent_id),
                session_factory=self._session_factory,
                graph_blueprint=design.graph_blueprint,
                llm=llm,
                system_prompt=design.system_prompt,
                tools_by_name=tools_by_name,
                graph_enabled=True,
            )

        if not tools:
            logger.warning(
                "[LangChainBuilder] agent_id=%s falling back to simple chain without tools",
                design.agent_id,
            )
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

        if agent_type == "openai_functions":
            prompt = self._build_prompt(design.system_prompt, has_tools=True)
            try:
                agent = create_tool_calling_agent(llm, tools, prompt)
            except Exception:
                prompt = self._build_react_prompt(design.system_prompt)
                agent = create_react_agent(llm, tools, prompt)
        else:
            prompt = self._build_react_prompt(design.system_prompt)
            agent = create_react_agent(llm, tools, prompt)

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=4,
            max_execution_time=60,
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

    def _should_use_graph_runtime(self, design: AgentDesign) -> bool:
        blueprint = design.graph_blueprint or {}
        nodes = blueprint.get("nodes", []) if isinstance(blueprint, dict) else []
        edges = blueprint.get("edges", []) if isinstance(blueprint, dict) else []
        if not nodes:
            return False

        agent_nodes = [node for node in nodes if self._normalize_node_type(node.get("type")) == "agent"]
        edge_count_by_source: dict[str, int] = {}
        branching = False
        for edge in edges:
            source = edge.get("from")
            if not source:
                continue
            edge_count_by_source[source] = edge_count_by_source.get(source, 0) + 1
            if edge_count_by_source[source] > 1:
                branching = True
                break

        return bool(
            len(agent_nodes) > 1
            or any(self._normalize_node_type(node.get("type")) in {"tool", "decision"} for node in nodes)
            or branching
        )

    @staticmethod
    def _graph_uses_tool(design: AgentDesign, tool_name: str) -> bool:
        blueprint = design.graph_blueprint or {}
        nodes = blueprint.get("nodes", []) if isinstance(blueprint, dict) else []
        normalized_target = str(tool_name or "").strip().lower()
        if not normalized_target:
            return False
        for node in nodes:
            if LangChainAgentBuilder._normalize_node_type(node.get("type")) != "tool":
                continue
            data = node.get("data") or {}
            candidate = str(data.get("tool_name") or "").strip().lower()
            if candidate == normalized_target:
                return True
            label = str(node.get("label") or "").strip().lower().replace(" ", "_")
            if normalized_target == "knowledge_base" and label in {"knowledge_base", "base_de_conocimientos"}:
                return True
        return False

    @staticmethod
    def _normalize_node_type(value: object) -> str:
        if value is None:
            return ""
        raw = getattr(value, "value", value)
        text = str(raw).strip()
        if "." in text:
            text = text.split(".")[-1]
        return text.lower()

    @staticmethod
    def _escape_prompt(system_prompt: str) -> str:
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
        react_system = (
            f"{self._escape_prompt(system_prompt)}\n\n"
            "Tenes acceso a las siguientes herramientas:\n\n"
            "{tools}\n\n"
            "REGLAS ESTRICTAS: segui EXACTAMENTE este formato, sin excepciones:\n\n"
            "Thought: [tu razonamiento]\n"
            "Action: [una de: {tool_names}]\n"
            "Action Input: [input para la herramienta]\n"
            "Observation: [resultado - lo agrega el sistema automaticamente]\n"
            "Thought: [razonamiento tras ver el resultado]\n"
            "Final Answer: [tu respuesta final completa]\n\n"
            "CRITICO:\n"
            "- Despues de cada 'Thought:' SIEMPRE escribi 'Action:' O 'Final Answer:'.\n"
            "- En cuanto tengas informacion suficiente de una herramienta, escribi 'Final Answer:' inmediatamente.\n"
            "- No repitas llamadas a herramientas si ya tienes lo necesario.\n"
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

        return InMemoryAdapter(max_messages=max_msg)


async def _load_custom_tool(name: str, config: dict, tenant_id: str):
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
        raise ValueError(f"Custom tool '{name}' esta desactivada")
    return build_tool_from_code(row["source_code"], config)
