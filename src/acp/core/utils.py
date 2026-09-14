"""Shared primitives: canonical JSON, hashing, UUIDs, secret redaction."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

# Keys whose values must never be written to the audit ledger / logs in raw form.
_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|apikey|authorization|credential|"
    r"private[_-]?key|client[_-]?secret|ssn|dob|date_of_birth|account_id|iban)",
    re.IGNORECASE,
)
# Inline secret shapes inside free text (bearer tokens, sk- keys, basic auth).
_SECRET_VALUE_RES = [
    re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-._~+/=]{8,}"),
    re.compile(r"\bsk-(live|test)-[A-Za-z0-9]{8,}\b"),
    re.compile(r"(?i)\b(api[_-]?key\s*[:=]\s*)([A-Za-z0-9\-._~+/=]{8,})"),
]


def new_id() -> str:
    """Portable UUID as String(36) — keeps SQL portable across SQLite/Postgres."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def digest(obj: Any) -> str:
    """Stable digest of an object (for inputs_digest fields)."""
    return sha256_hex(canonical_json(obj))


def _scrub_string(s: str) -> str:
    for rx in _SECRET_VALUE_RES:
        s = rx.sub(lambda m: m.group(1) + "<redacted:" + sha256_hex(m.group(0))[:12] + ">", s)
    return s


def redact(obj: Any) -> Any:
    """Redact-before-write: replace secret/PII values with digests, never raw values."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEY_RE.search(str(k)):
                out[k] = {"__redacted__": True, "digest": sha256_hex(canonical_json(v))}
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return _scrub_string(obj)
    return obj
