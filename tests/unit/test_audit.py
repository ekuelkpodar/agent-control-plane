"""Unit: audit ledger — hash chain, signatures, redaction, verify."""

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from acp.core.utils import redact
from acp.db.models import AuditEntry, Base
from acp.governance.audit import AuditLedger


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _append(ledger, session, **kw):
    kw.setdefault("tenant_id", "t1")
    kw.setdefault("event_type", "TaskCreated")
    kw.setdefault("actor", {"principal": "tester"})
    kw.setdefault("action", "test")
    return ledger.append(session, **kw)


def test_chain_verifies(session):
    ledger = AuditLedger()
    for i in range(5):
        _append(ledger, session, inputs={"i": i})
    result = ledger.verify(session, "t1")
    assert result == {"ok": True, "checked": 5, "first_break": None}


def test_per_tenant_chains_independent(session):
    ledger = AuditLedger()
    _append(ledger, session, tenant_id="t1")
    _append(ledger, session, tenant_id="t2")
    _append(ledger, session, tenant_id="t1")
    assert ledger.verify(session, "t1")["checked"] == 2
    assert ledger.verify(session, "t2")["checked"] == 1
    assert ledger.verify(session)["checked"] == 3


def test_tamper_detected(session):
    ledger = AuditLedger()
    _append(ledger, session, inputs={"a": 1})
    row = _append(ledger, session, inputs={"a": 2})
    _append(ledger, session, inputs={"a": 3})
    session.execute(update(AuditEntry).where(AuditEntry.seq == row.seq).values(result="forged"))
    session.commit()
    result = ledger.verify(session, "t1")
    assert result["ok"] is False
    assert result["first_break"]["seq"] == row.seq
    assert "content-altered" in result["first_break"]["reason"]


def test_link_break_detected(session):
    ledger = AuditLedger()
    _append(ledger, session)
    row = _append(ledger, session)
    session.execute(update(AuditEntry).where(AuditEntry.seq == row.seq).values(prev_hash="0" * 64))
    session.commit()
    result = ledger.verify(session, "t1")
    assert result["ok"] is False
    assert "link-broken" in result["first_break"]["reason"]


def test_redact_before_write():
    out = redact({"api_key": "sk-live-abcdef123456", "nested": {"token": "abc"}, "ok": 1})
    assert out["api_key"]["__redacted__"] is True
    assert "sk-live-abcdef123456" not in str(out)
    assert out["nested"]["token"]["__redacted__"] is True
    assert out["ok"] == 1


def test_inline_secret_shapes_scrubbed():
    out = redact({"note": "call with Bearer supersecret-token-123 now"})
    assert "supersecret-token-123" not in out["note"]
    assert "redacted" in out["note"]


def test_inputs_stored_as_digest_only(session):
    ledger = AuditLedger()
    row = _append(ledger, session, inputs={"password": "hunter2-hunter2"})
    assert "hunter2" not in row.inputs_digest
    assert len(row.inputs_digest) == 64


def test_signature_verifies_origin(session):
    ledger = AuditLedger()
    row = _append(ledger, session)
    import base64

    ledger.verify_key.verify(row.entry_hash.encode(), base64.b64decode(row.signature))  # no raise
