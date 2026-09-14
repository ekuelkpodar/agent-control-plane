"""Append-only, hash-chained, Ed25519-signed audit ledger.

Entry: {seq, tenant_id, timestamp, event_type, actor, action, inputs_digest,
policy{decision,version_hash}, risk{score,level}, delegation_chain, result,
prev_hash, entry_hash=SHA256(prev_hash || canonical(entry)), signature}.

Redact-before-write: secrets/PII are digested, never stored raw.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from acp.core.utils import canonical_json, digest, redact, sha256_hex, utcnow
from acp.db.models import AuditEntry

log = logging.getLogger(__name__)
GENESIS = "GENESIS" + "0" * 57  # 64-char genesis prev_hash


class AuditLedger:
    def __init__(self, signing_key: SigningKey | None = None):
        if signing_key is None:
            log.warning(
                "AUDIT LEDGER: no ACP_LEDGER_SIGNING_KEY_b64 configured — "
                "generated an EPHEMERAL Ed25519 key. Signatures will not verify "
                "across restarts. Set the env var in production."
            )
            signing_key = SigningKey.generate()
        self._signing_key = signing_key
        self.verify_key: VerifyKey = signing_key.verify_key

    @classmethod
    def from_env(cls, b64_seed: str | None) -> AuditLedger:
        if b64_seed:
            return cls(SigningKey(base64.b64decode(b64_seed)))
        return cls(None)

    def _prev_hash(self, session: Session, tenant_id: str) -> str:
        last = session.execute(
            select(AuditEntry.entry_hash)
            .where(AuditEntry.tenant_id == tenant_id)
            .order_by(AuditEntry.seq.desc())
            .limit(1)
        ).scalar_one_or_none()
        return last or GENESIS

    def append(
        self,
        session: Session,
        *,
        tenant_id: str,
        task_id: str | None = None,
        event_type: str,
        actor: dict[str, Any],
        action: str,
        inputs: Any = None,
        policy: dict[str, Any] | None = None,
        risk: dict[str, Any] | None = None,
        delegation_chain: list | None = None,
        result: str = "",
        flush: bool = True,
    ) -> AuditEntry:
        """Append one entry. Inputs are redacted BEFORE hashing/writing."""
        redacted_inputs = redact(inputs if inputs is not None else {})
        ts = utcnow()
        entry_body = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "timestamp": ts.isoformat(),
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "inputs_digest": digest(redacted_inputs),
            "policy": policy or {},
            "risk": risk or {},
            "delegation_chain": delegation_chain or [],
            "result": result,
        }
        prev_hash = self._prev_hash(session, tenant_id)
        entry_hash = sha256_hex(prev_hash + "|" + canonical_json(entry_body))
        signature = base64.b64encode(self._signing_key.sign(entry_hash.encode()).signature).decode()
        row = AuditEntry(
            tenant_id=tenant_id,
            task_id=task_id,
            timestamp=ts,
            event_type=event_type,
            actor=actor,
            action=action,
            inputs_digest=entry_body["inputs_digest"],
            policy=policy or {},
            risk=risk or {},
            delegation_chain=delegation_chain or [],
            result=result,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            signature=signature,
        )
        session.add(row)
        if flush:
            session.flush()
        return row

    def verify(self, session: Session, tenant_id: str | None = None) -> dict[str, Any]:
        """Recompute the chain oldest->newest; report the first break."""
        q = select(AuditEntry).order_by(AuditEntry.seq.asc())
        if tenant_id:
            q = q.where(AuditEntry.tenant_id == tenant_id)
        rows = list(session.execute(q).scalars().all())
        checked = 0
        expected_prev: dict[str, str] = {}
        for row in rows:
            exp_prev = expected_prev.get(row.tenant_id, GENESIS)
            if row.prev_hash != exp_prev:
                return {
                    "ok": False,
                    "checked": checked,
                    "first_break": {
                        "seq": row.seq,
                        "tenant_id": row.tenant_id,
                        "reason": "link-broken: prev_hash does not match previous entry_hash",
                    },
                }
            body = {
                "tenant_id": row.tenant_id,
                "task_id": row.task_id,
                # Must be byte-identical to append(): the DB round-trips the
                # naive UTC datetime exactly on SQLite and Postgres.
                "timestamp": row.timestamp.isoformat(),
                "event_type": row.event_type,
                "actor": row.actor,
                "action": row.action,
                "inputs_digest": row.inputs_digest,
                "policy": row.policy,
                "risk": row.risk,
                "delegation_chain": row.delegation_chain,
                "result": row.result,
            }
            recomputed = sha256_hex(row.prev_hash + "|" + canonical_json(body))
            if recomputed != row.entry_hash:
                return {
                    "ok": False,
                    "checked": checked,
                    "first_break": {
                        "seq": row.seq,
                        "tenant_id": row.tenant_id,
                        "reason": "content-altered: entry body hash does not match",
                    },
                }
            try:
                self.verify_key.verify(
                    row.entry_hash.encode(), base64.b64decode(row.signature)
                )
            except BadSignatureError:
                return {
                    "ok": False,
                    "checked": checked,
                    "first_break": {
                        "seq": row.seq,
                        "tenant_id": row.tenant_id,
                        "reason": "signature-invalid",
                    },
                }
            expected_prev[row.tenant_id] = row.entry_hash
            checked += 1
        return {"ok": True, "checked": checked, "first_break": None}
