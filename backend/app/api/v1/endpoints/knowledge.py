from __future__ import annotations

import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.api.deps import TenantRepo
from app.components.rag.knowledge_builder import KnowledgeBuilderService
from app.core.security import CurrentContext
from app.schemas.agent import RAGSpec

router = APIRouter()
kb_svc = KnowledgeBuilderService()


class IngestRequest(BaseModel):
    agent_id: str
    rag_spec: RAGSpec


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 4


class DeleteSourceRequest(BaseModel):
    source: str


@router.post("/{agent_id}/ingest", status_code=202)
async def ingest_knowledge(
    agent_id: str,
    body: IngestRequest,
    ctx: CurrentContext,
    repo: TenantRepo,
) -> dict:
    """
    Ingiere las fuentes del RAGSpec en la base de conocimiento del agente.
    Operación async — retorna inmediatamente con task_id.
    """
    ctx.require_developer()

    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")

    # Correr en background para no bloquear el request
    asyncio.create_task(_run_ingestion(agent_id, body.rag_spec))

    return {
        "agent_id": agent_id,
        "status":   "ingesting",
        "sources":  len(body.rag_spec.sources),
        "message":  "Ingesta iniciada en background. Consultá /stats para ver el progreso.",
    }


async def _run_ingestion(agent_id: str, rag_spec: RAGSpec) -> None:
    try:
        stats = await kb_svc.ingest(agent_id, rag_spec)
        print(f"[RAG] Ingesta completada: {stats}")
    except Exception as e:
        print(f"[RAG] Error en ingesta: {e}")


@router.get("/{agent_id}/stats")
async def get_kb_stats(agent_id: str, ctx: CurrentContext) -> dict:
    """Estadísticas de la colección RAG del agente."""
    return await kb_svc.collection_stats(agent_id)


@router.post("/{agent_id}/retrieve")
async def retrieve_from_kb(
    agent_id: str,
    body: RetrieveRequest,
    ctx: CurrentContext,
) -> dict:
    """Búsqueda manual en la knowledge base (útil para debug)."""
    results = await kb_svc.retrieve(agent_id, body.query, body.top_k)
    return {"agent_id": agent_id, "query": body.query, "results": results}


@router.delete("/{agent_id}", status_code=204)
async def delete_kb(agent_id: str, ctx: CurrentContext) -> None:
    """Elimina la colección RAG completa del agente."""
    ctx.require_developer()
    await kb_svc.delete_collection(agent_id)

@router.get("/{agent_id}/sources")
async def get_kb_sources(agent_id: str, ctx: CurrentContext) -> dict:
    ctx.require_developer()
    sources = await kb_svc.get_sources(agent_id)
    return {"agent_id": agent_id, "sources": sources}

@router.delete("/{agent_id}/source", status_code=204)
async def delete_kb_source(agent_id: str, body: DeleteSourceRequest, ctx: CurrentContext) -> None:
    ctx.require_developer()
    await kb_svc.delete_source(agent_id, body.source)

@router.post("/{agent_id}/ingest/file", status_code=202)
async def ingest_knowledge_file(
    agent_id: str,
    ctx: CurrentContext,
    repo: TenantRepo,
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
) -> dict:
    ctx.require_developer()
    agent = await repo.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Agente '{agent_id}' no encontrado")
        
    temp_path = Path("/tmp") / file.filename
    temp_path.write_bytes(await file.read())

    rag_spec = RAGSpec(
        sources=[str(temp_path)],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    asyncio.create_task(_run_ingestion(agent_id, rag_spec))

    return {
        "agent_id": agent_id,
        "status":   "ingesting",
        "file": file.filename,
        "message":  "Ingesta de archivo iniciada en background."
    }

