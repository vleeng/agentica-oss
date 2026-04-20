from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, HTTPException, Response, UploadFile, File, Form

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.components.rag.knowledge_builder import KnowledgeBuilderService
from app.schemas.knowledge_base import KnowledgeBaseIn, KnowledgeBaseOut

router = APIRouter()
_kb_builder = KnowledgeBuilderService()


@router.get("/knowledge-bases/", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.list_knowledge_bases()
    return [KnowledgeBaseOut.from_row(r) for r in rows]


@router.post("/knowledge-bases/", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(body: KnowledgeBaseIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "description": body.description,
        "rag_spec_json": json.dumps(body.rag_spec.model_dump()),
    }
    row = await repo.create_knowledge_base(data)
    return KnowledgeBaseOut.from_row(row)


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    return KnowledgeBaseOut.from_row(row)


@router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(kb_id: str, body: KnowledgeBaseIn, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    data = {
        "name": body.name,
        "description": body.description,
        "rag_spec_json": json.dumps(body.rag_spec.model_dump()),
    }
    row = await repo.update_knowledge_base(kb_id, data)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    return KnowledgeBaseOut.from_row(row)


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_knowledge_base(kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    # Eliminar colección Qdrant antes de borrar el registro
    try:
        await _kb_builder.delete_collection(kb_id)
    except Exception:
        pass
    deleted = await repo.delete_knowledge_base(kb_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    return Response(status_code=204)


@router.post("/knowledge-bases/{kb_id}/ingest", status_code=202)
async def ingest_knowledge_base(kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    """Inicia la ingesta de fuentes definidas en el rag_spec de la KB."""
    ctx.require_developer()
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")

    rag_raw = row.get("rag_spec_json", {})
    rag_spec_dict = json.loads(rag_raw) if isinstance(rag_raw, str) else rag_raw

    from app.schemas.agent import RAGSpec
    rag_spec = RAGSpec(**rag_spec_dict)

    await repo.update_knowledge_base(kb_id, {"status": "indexing"})

    async def _run():
        try:
            await _kb_builder.ingest(kb_id, rag_spec)
            await repo.update_knowledge_base(kb_id, {"status": "ready"})
        except Exception as e:
            await repo.update_knowledge_base(kb_id, {"status": "error"})

    asyncio.create_task(_run())
    return {"status": "indexing", "kb_id": kb_id}


@router.post("/knowledge-bases/{kb_id}/ingest/file", status_code=202)
async def ingest_file_to_kb(
    kb_id: str,
    repo: TenantRepo,
    ctx: CurrentContext,
    file: UploadFile = File(...),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
):
    ctx.require_developer()
    import tempfile, os
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")

    suffix = os.path.splitext(file.filename or "")[1] or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    from app.schemas.agent import RAGSpec
    rag_spec = RAGSpec(enabled=True, sources=[tmp_path], chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    await repo.update_knowledge_base(kb_id, {"status": "indexing"})

    async def _run():
        try:
            await _kb_builder.ingest(kb_id, rag_spec)
            await repo.update_knowledge_base(kb_id, {"status": "ready"})
        except Exception:
            await repo.update_knowledge_base(kb_id, {"status": "error"})
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    asyncio.create_task(_run())
    return {"status": "indexing", "kb_id": kb_id, "filename": file.filename}


@router.get("/knowledge-bases/{kb_id}/sources")
async def get_kb_sources(kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    sources = await _kb_builder.get_sources(kb_id)
    stats = await _kb_builder.collection_stats(kb_id)
    return {"kb_id": kb_id, "sources": sources, "stats": stats}


@router.delete("/knowledge-bases/{kb_id}/sources")
async def delete_kb_source(kb_id: str, source: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    await _kb_builder.delete_source(kb_id, source)
    return {"deleted": source}


# ── Asignación a agentes ──────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/knowledge-bases", response_model=list[KnowledgeBaseOut])
async def get_agent_knowledge_bases(agent_id: str, repo: TenantRepo, ctx: CurrentContext):
    rows = await repo.get_agent_knowledge_bases(agent_id)
    return [KnowledgeBaseOut.from_row(r) for r in rows]


@router.post("/agents/{agent_id}/knowledge-bases/{kb_id}", status_code=204)
async def assign_kb(agent_id: str, kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    kb = await repo.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    await repo.assign_kb_to_agent(agent_id, kb_id)
    return Response(status_code=204)


@router.delete("/agents/{agent_id}/knowledge-bases/{kb_id}", status_code=204)
async def unassign_kb(agent_id: str, kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    await repo.unassign_kb_from_agent(agent_id, kb_id)
    return Response(status_code=204)
