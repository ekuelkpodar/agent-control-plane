"""Knowledge: KnowledgeSource + RAG retriever interfaces with a simple in-DB
implementation for MVP (keyword/hybrid scoring). Provenance on every chunk.
pgvector is the documented scale-out path.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.utils import new_id
from acp.db.models import KnowledgeChunk, KnowledgeSource


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class KnowledgeService:
    def add_source(self, session: Session, tenant_id: str, name: str, uri: str = "",
                   trust_level: str = "untrusted") -> dict:
        src = KnowledgeSource(id=new_id(), tenant_id=tenant_id, name=name, uri=uri, trust_level=trust_level)
        session.add(src)
        session.flush()
        return {"id": src.id, "name": name, "uri": uri, "trust_level": trust_level}

    def add_chunk(self, session: Session, tenant_id: str, source_id: str, content: str,
                  provenance: dict | None = None) -> dict:
        src = session.execute(
            select(KnowledgeSource).where(
                KnowledgeSource.id == source_id, KnowledgeSource.tenant_id == tenant_id
            )
        ).scalars().first()
        if src is None:
            from acp.core.errors import NotFound
            raise NotFound("knowledge source not found")
        prov = dict(provenance or {})
        prov.setdefault("source_id", source_id)
        prov.setdefault("source_trust", src.trust_level)
        chunk = KnowledgeChunk(id=new_id(), tenant_id=tenant_id, source_id=source_id,
                              content=content, provenance=prov)
        session.add(chunk)
        session.flush()
        return {"id": chunk.id, "provenance": prov}

    def retrieve(self, session: Session, tenant_id: str, query: str, top_k: int = 5,
                 min_trust: str | None = None) -> list[dict[str, Any]]:
        """Keyword-overlap retrieval (MVP). V1: pgvector ANN behind this interface."""
        q = select(KnowledgeChunk).where(KnowledgeChunk.tenant_id == tenant_id)
        chunks = session.execute(q).scalars().all()
        qtok = _tokens(query)
        scored = []
        for c in chunks:
            ctok = _tokens(c.content)
            overlap = len(qtok & ctok)
            if overlap:
                scored.append((overlap / max(len(qtok), 1), c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": c.id, "content": c.content, "score": round(s, 4), "provenance": c.provenance}
            for s, c in scored[:top_k]
        ]
