from __future__ import annotations
import asyncio
import json
import shutil
from fastapi import APIRouter, HTTPException, Response, UploadFile, File, Form
from pathlib import Path

from app.api.deps import TenantRepo
from app.core.security import CurrentContext
from app.core.config import get_settings
from app.components.rag.knowledge_builder import KnowledgeBuilderService
from app.schemas.knowledge_base import KnowledgeBaseIn, KnowledgeBaseOut
from app.schemas.agent import RAGSpec

router = APIRouter()
_kb_builder = KnowledgeBuilderService()
_settings = get_settings()


def _kb_storage_dir(kb_id: str) -> Path:
    return Path(_settings.builds_path) / "knowledge_bases" / kb_id


def _kb_rag_spec(row: dict) -> RAGSpec:
    rag_raw = row.get("rag_spec_json", {})
    rag_spec_dict = json.loads(rag_raw) if isinstance(rag_raw, str) else rag_raw
    return RAGSpec(**rag_spec_dict)


async def _save_kb_rag_spec(repo: TenantRepo, kb_id: str, row: dict, rag_spec: RAGSpec, *, status: str | None = None) -> None:
    payload: dict[str, str] = {"rag_spec_json": json.dumps(rag_spec.model_dump())}
    if status is not None:
        payload["status"] = status
    await repo.update_knowledge_base(kb_id, payload)


def _is_managed_kb_source(kb_id: str, source: str) -> bool:
    try:
        source_path = Path(source).resolve()
        managed_root = _kb_storage_dir(kb_id).resolve()
        return managed_root == source_path or managed_root in source_path.parents
    except Exception:
        return False


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
        "access_mode": body.access_mode,
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
        "access_mode": body.access_mode,
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
    try:
        shutil.rmtree(_kb_storage_dir(kb_id), ignore_errors=True)
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

    rag_spec = _kb_rag_spec(row)

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
    row = await repo.get_knowledge_base(kb_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge base no encontrada")
    rag_spec = _kb_rag_spec(row)

    safe_filename = Path(file.filename or "upload.bin").name
    storage_dir = _kb_storage_dir(kb_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / safe_filename
    stored_path.write_bytes(await file.read())
    stored_source = str(stored_path)

    updated_sources = [src for src in rag_spec.sources if src != stored_source]
    updated_sources.append(stored_source)
    rag_spec = rag_spec.model_copy(
        update={
            "enabled": True,
            "sources": updated_sources,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
    )
    await _save_kb_rag_spec(repo, kb_id, row, rag_spec, status="indexing")

    async def _run():
        try:
            try:
                await _kb_builder.delete_source(kb_id, stored_source)
            except Exception:
                pass
            await _kb_builder.ingest(
                kb_id,
                rag_spec.model_copy(update={"sources": [stored_source]}),
            )
            await repo.update_knowledge_base(kb_id, {"status": "ready"})
        except Exception:
            await repo.update_knowledge_base(kb_id, {"status": "error"})

    asyncio.create_task(_run())
    return {"status": "indexing", "kb_id": kb_id, "filename": file.filename, "source": stored_source}


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
    rag_spec = _kb_rag_spec(row)
    if source in rag_spec.sources:
        rag_spec = rag_spec.model_copy(update={"sources": [src for src in rag_spec.sources if src != source]})
        await _save_kb_rag_spec(repo, kb_id, row, rag_spec)
    if _is_managed_kb_source(kb_id, source):
        try:
            Path(source).unlink(missing_ok=True)
        except Exception:
            pass
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
    if (kb.get("access_mode") or "restricted") == "global":
        return Response(status_code=204)
    await repo.assign_kb_to_agent(agent_id, kb_id)
    return Response(status_code=204)


@router.delete("/agents/{agent_id}/knowledge-bases/{kb_id}", status_code=204)
async def unassign_kb(agent_id: str, kb_id: str, repo: TenantRepo, ctx: CurrentContext):
    ctx.require_developer()
    kb = await repo.get_knowledge_base(kb_id)
    if kb and (kb.get("access_mode") or "restricted") == "global":
        raise HTTPException(status_code=400, detail="Una knowledge base global no puede desasignarse desde un agente")
    await repo.unassign_kb_from_agent(agent_id, kb_id)
    return Response(status_code=204)
