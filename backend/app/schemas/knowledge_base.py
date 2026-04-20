from __future__ import annotations
from pydantic import BaseModel, Field

from app.schemas.agent import RAGSpec


class KnowledgeBaseIn(BaseModel):
    name: str
    description: str = ""
    rag_spec: RAGSpec = Field(default_factory=RAGSpec)


class KnowledgeBaseOut(KnowledgeBaseIn):
    id: str
    status: str
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "KnowledgeBaseOut":
        import json
        rag_raw = row.get("rag_spec_json", {})
        if isinstance(rag_raw, str):
            rag_raw = json.loads(rag_raw)
        return cls(
            id=str(row["id"]),
            name=row["name"],
            description=row.get("description") or "",
            rag_spec=RAGSpec(**rag_raw) if rag_raw else RAGSpec(),
            status=row["status"],
            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        )
