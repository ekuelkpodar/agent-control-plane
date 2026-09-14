# Memory Lifecycle

Vector databases solve *retrieval*, not memory. The ACP's differentiated
work is memory **lifecycle**: what to remember, what to forget, what to
consolidate — with tenant isolation, provenance, and privacy. The vector
index itself (pgvector in MVP, Qdrant later) sits behind a `MemoryStore`
interface.

## Entry model

Every memory entry records:

- `writer_agent_id`, `task_id`, `timestamp`
- `source_trust` (trusted / tenant / untrusted-external) and full provenance
- `tenant_id` — memory is tenant-scoped, no cross-tenant retrieval, ever
- `entry_hash` — entries are hash-chained like the audit ledger so tampering
  is detectable
- classification tag (public / internal / confidential / restricted)

## Lifecycle states

`written → active → consolidated → archived → expired | deleted`

- **Written:** provenance recorded; low-trust writes quarantined from
  high-stakes retrieval.
- **Active:** retrievable within tenant scope and classification bounds.
- **Consolidated:** periodic jobs merge redundant entries; consolidation is
  itself a versioned operation with provenance preserved.
- **Archived:** moved out of hot retrieval, still auditable.
- **Expired / deleted:** TTL policies enforce retention; tenant deletion ⇒
  cryptographic erasure via destruction of the tenant's data key.

## Defenses (T17: memory poisoning)

- **Write provenance** on every entry; entries derived from untrusted
  content are tagged and quarantined.
- **Signed snapshots:** memory checkpoints are hash-chained; restore is
  verify-then-load.
- **Anomaly detection on writes:** bulk writes, fact-contradiction, or
  writes from compromised-task contexts trigger quarantine + human review.
- **Freshness:** entries carry timestamps; stale entries are excluded from
  high-stakes retrieval or flagged as stale.

## What belongs in the ACP vs. the store

| ACP (ours) | Store (integration) |
|---|---|
| lifecycle, retention, tenancy, deletion | ANN recall, embeddings, index ops |
| provenance, trust tags, quarantine policy | chunking, reranking |
| consolidation policy, signed snapshots | — |

The retrieval interface stays in the ACP; the document pipeline and
GraphRAG are V1 integrations, not MVP.
