# Model Integrations

**Route, don't proxy.** The ACP selects models; it does not sit in the
token path. Bulk data (tokens) flows model↔runtime directly; the control
plane sees metadata and policy checkpoints.

## Adapter interface

```python
class ModelProvider(Protocol):
    name: str
    def capabilities(self) -> ModelCapabilities: ...   # tools, vision, ctx window, …
    def cost(self) -> CostMetadata: ...                 # per-1k in/out, latency p50/p95
    def stream(self, request) -> Iterator[Chunk]: ...   # streaming supported
```

MVP adapters: OpenAI, Anthropic, Google, Bedrock, OpenRouter, Ollama.
Existing gateways (OpenRouter-class, LiteLLM-class) are valid *backends*
behind the interface — do not build a model gateway.

## Router inputs

Selection is capability×quality×latency×cost×risk×availability×policy:

- capability match (tool use, context length, modality)
- historical quality for this task class
- latency SLO
- cost budget (remaining envelope)
- data residency (model region vs. tenant constraint)
- tenant model **allowlist** (only approved model IDs are routable)
- policy constraints (e.g. "no external-provider models for restricted data")

Routing decisions are audit events with the selected model, provider, and
the scoring inputs — decision provenance, not just a choice.

## Guardrails

- **Model allowlisting** per tenant; an unlisted model is unroutable
  (fail closed).
- **Output verification** for high-stakes tasks: second-model or
  deterministic checker before side-effecting actions on unverified model
  output.
- **Prompt versioning:** system prompts are versioned artifacts; an
  unapproved prompt change is a security event (T11).
- Egress filtering before model calls blocks known-secret shapes (prevents
  training-data contamination via third-party providers) and applies DLP
  classification rules.
