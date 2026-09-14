# Knowledge / RAG

The ACP keeps the **retrieval interface**; document pipelines are V1
integrations. Retrieval is governed: every retrieved chunk carries
provenance and trust level, because indirect prompt injection (T6) enters
through exactly this path.

## MVP scope

- `KnowledgeSource` registry: name, source type, trust level
  (verified-publisher / tenant-internal / untrusted-external).
- pgvector-backed retrieval behind the `MemoryStore` interface (MVP);
  documented step-up to Qdrant (10M–1B vectors) or Weaviate (native hybrid
  search). Milvus only past ~100M vectors.
- Chunk-level provenance: `{source, trust_level, retrieved_at, hash}` on
  every retrieved span.

## Trust-weighted retrieval

- The planner and policy engine see provenance; the model sees content.
- Content from untrusted sources is processed by a minimally-privileged
  reader first (quarantine pattern); only structured, validated extracts
  cross into the privileged context.
- **Tool-call policy binding:** tool invocations proposed on the basis of
  untrusted content re-enter policy evaluation with the content's trust
  level as an input — high-impact actions from low-trust content ⇒ human
  approval.

## Non-goals (MVP)

- Document ingestion/chunking pipelines (V1 integration).
- GraphRAG (V2 knowledge-layer concern).
- A dedicated vector database on day one — premature optimization for an
  MVP whose memory story is lifecycle and tenancy, not ANN recall.

## V1 direction

Retrieval interface stays; add ingestion pipeline, hybrid search, and
cross-source trust scoring. Cryptographic content authentication for
high-value sources (signed feeds, verified publishers) so the policy
engine can distinguish "untrusted web" from "trusted-but-external" —
ecosystem support pending; the provenance field is designed to carry it.
