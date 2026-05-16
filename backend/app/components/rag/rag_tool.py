from __future__ import annotations

import asyncio
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class RAGQueryInput(BaseModel):
    query: str = Field(description="Pregunta o búsqueda para consultar la base de conocimiento")


class RAGTool(BaseTool):
    """
    Tool de LangChain que conecta el agente con su base de conocimiento RAG.
    Se inyecta automáticamente en el AgentBuilder cuando rag.enabled=True.
    """
    name: str = "knowledge_base"
    description: str = (
        "Consulta la base de conocimiento interna del agente. "
        "Úsala cuando necesites información específica del dominio, "
        "documentos subidos, o contexto propio del negocio."
    )
    args_schema: Type[BaseModel] = RAGQueryInput
    agent_id: str = ""
    top_k: int = 4
    session_factory: object | None = None

    def _run(self, query: str) -> str:
        raise NotImplementedError("Usar arun()")

    async def _arun(self, query: str) -> str:
        try:
            from app.components.rag.knowledge_builder import KnowledgeBuilderService
            kb = KnowledgeBuilderService()
            extra_owner_ids = await self._accessible_kb_ids()
            context = await kb.retrieve_as_context(
                self.agent_id,
                query,
                self.top_k,
                extra_owner_ids=extra_owner_ids,
                include_agent_source=not extra_owner_ids,
            )
            return context or "No se encontró información relevante en la base de conocimiento."
        except ValueError as e:
            # Clave de embeddings no configurada — devolver aviso en lugar de crashear el agente
            return f"[RAG no disponible: {e}]"
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[RAGTool] Error en retrieval: {e}")
            return "No se pudo consultar la base de conocimiento en este momento."

    async def _accessible_kb_ids(self) -> list[str]:
        if not self.session_factory or not self.agent_id:
            return []
        try:
            from app.db.repository import AgentRepository

            async with self.session_factory() as session:
                repo = AgentRepository(session)
                rows = await repo.get_agent_knowledge_bases(self.agent_id)
        except Exception:
            return []

        kb_ids: list[str] = []
        for row in rows:
            kb_id = str(row.get("id") or "").strip()
            if kb_id:
                kb_ids.append(kb_id)
        return kb_ids


class CrewAIRAGTool(BaseTool):
    """
    Adaptador sincrónico para CrewAI.

    CrewAI usa el ciclo de herramientas en modo sincrónico con más
    confiabilidad cuando la tool expone un único argumento.
    """

    name: str = "knowledge_base"
    description: str = (
        "Consulta la base de conocimiento interna del agente. "
        "Usala cuando necesites contexto del negocio o documentos ya cargados."
    )
    args_schema: Type[BaseModel] = RAGQueryInput
    agent_id: str = ""
    top_k: int = 4
    session_factory: object | None = None

    def _run(self, query: str) -> str:
        return asyncio.run(self._arun(query))

    async def _arun(self, query: str) -> str:
        delegate = RAGTool(agent_id=self.agent_id, top_k=self.top_k, session_factory=self.session_factory)
        return await delegate._arun(query)
