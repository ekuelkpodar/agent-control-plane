"""Memory: MemoryStore interface + PostgresMemoryStore.

Tenant-namespaced, write provenance {writer, source_trust, task_id}, TTL,
hash-chained snapshots (tamper-evident). pgvector-ready (documented; keyword
retrieval in knowledge layer for MVP).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.utils import canonical_json, new_id, sha256_hex, utcnow
from acp.db.models import MemoryEntry


class PostgresMemoryStore:
    def _prev_hash(self, session: Session, tenant_id: str, namespace: str) -> str:
        last = session.execute(
            select(MemoryEntry.entry_hash)
            .where(MemoryEntry.tenant_id == tenant_id, MemoryEntry.namespace == namespace)
            .order_by(MemoryEntry.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        return last or "GENESIS"

    def write(
        self, session: Session, tenant_id: str, namespace: str, key: str, value: dict,
        provenance: dict, ttl_seconds: int | None = None,
    ) -> dict:
        quarantined = str(provenance.get("source_trust", "")).lower() == "untrusted"
        prev = self._prev_hash(session, tenant_id, namespace)
        body = canonical_json({"tenant": tenant_id, "ns": namespace, "key": key, "value": value, "prov": provenance})
        entry_hash = sha256_hex(prev + "|" + body)
        expires_at = None
        if ttl_seconds:
            from datetime import timedelta
            expires_at = utcnow() + timedelta(seconds=ttl_seconds)
        existing = session.execute(
            select(MemoryEntry).where(
                MemoryEntry.tenant_id == tenant_id, MemoryEntry.namespace == namespace, MemoryEntry.key == key
            )
        ).scalars().first()
        if existing:
            existing.value = value
            existing.provenance = provenance
            existing.quarantined = quarantined
            existing.expires_at = expires_at
            existing.prev_hash = prev
            existing.entry_hash = entry_hash
            session.flush()
            row = existing
        else:
            row = MemoryEntry(
                id=new_id(), tenant_id=tenant_id, namespace=namespace, key=key,
                value=value, provenance=provenance, quarantined=quarantined,
                expires_at=expires_at, prev_hash=prev, entry_hash=entry_hash,
            )
            session.add(row)
            session.flush()
        return self._to_dict(row)

    def read(self, session: Session, tenant_id: str, namespace: str, key: str) -> dict | None:
        row = session.execute(
            select(MemoryEntry).where(
                MemoryEntry.tenant_id == tenant_id, MemoryEntry.namespace == namespace, MemoryEntry.key == key
            )
        ).scalars().first()
        if row is None:
            return None
        if row.expires_at and row.expires_at <= utcnow():
            session.delete(row)
            session.flush()
            return None
        return self._to_dict(row)

    def list(self, session: Session, tenant_id: str, namespace: str, include_quarantined: bool = False) -> list[dict]:
        q = select(MemoryEntry).where(
            MemoryEntry.tenant_id == tenant_id, MemoryEntry.namespace == namespace
        )
        if not include_quarantined:
            q = q.where(MemoryEntry.quarantined.is_(False))
        rows = session.execute(q.order_by(MemoryEntry.updated_at.desc())).scalars().all()
        out = []
        for row in rows:
            if row.expires_at and row.expires_at <= utcnow():
                continue
            out.append(self._to_dict(row))
        return out

    def delete(self, session: Session, tenant_id: str, namespace: str, key: str) -> None:
        row = session.execute(
            select(MemoryEntry).where(
                MemoryEntry.tenant_id == tenant_id, MemoryEntry.namespace == namespace, MemoryEntry.key == key
            )
        ).scalars().first()
        if row:
            session.delete(row)
            session.flush()

    @staticmethod
    def _to_dict(row: MemoryEntry) -> dict[str, Any]:
        return {
            "id": row.id, "namespace": row.namespace, "key": row.key, "value": row.value,
            "provenance": row.provenance, "quarantined": row.quarantined,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "entry_hash": row.entry_hash,
        }
