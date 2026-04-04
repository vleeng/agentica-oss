from __future__ import annotations

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

    def _run(self, query: str) -> str:
        raise NotImplementedError("Usar arun()")

    async def _arun(self, query: str) -> str:
        from app.components.rag.knowledge_builder import KnowledgeBuilderService
        kb = KnowledgeBuilderService()
        context = await kb.retrieve_as_context(self.agent_id, query, self.top_k)
        return context or "No se encontró información relevante en la base de conocimiento."
