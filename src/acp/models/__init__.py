"""Model provider adapters: interface + MockModelProvider (deterministic, for
tests/demo). OpenAI/Anthropic adapters are thin STUBS behind the interface —
clearly marked, no fake 'real' behavior."""

from __future__ import annotations

from typing import Any


class ModelProvider:
    name: str = "base"

    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError

    def cost_per_1k_tokens(self) -> float:
        raise NotImplementedError

    def latency_ms_p50(self) -> float:
        return 800.0

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError


class MockModelProvider(ModelProvider):
    """Deterministic mock model for tests and demos. NOT a real model."""

    name = "mock"

    def __init__(self, model: str = "mock-llm-1"):
        self.model = model

    def capabilities(self) -> dict[str, Any]:
        return {"provider": "mock", "model": self.model, "tools": True, "streaming": False, "deterministic": True}

    def cost_per_1k_tokens(self) -> float:
        return 0.001

    def latency_ms_p50(self) -> float:
        return 5.0

    def generate(self, prompt: str, **kwargs: Any) -> str:
        import hashlib

        digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
        return f"[mock:{self.model}] deterministic response {digest} for prompt of {len(prompt)} chars"


class OpenAIProvider(ModelProvider):
    """STUB — real OpenAI integration is V1. Raises until wired."""

    name = "openai"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        raise NotImplementedError("OpenAIProvider is a documented stub for V1 (no fake real behavior).")


class AnthropicProvider(ModelProvider):
    """STUB — real Anthropic integration is V1. Raises until wired."""

    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str = "claude-haiku-4-5"):
        raise NotImplementedError("AnthropicProvider is a documented stub for V1 (no fake real behavior).")


def build_provider(provider: str, model: str) -> ModelProvider:
    if provider == "mock":
        return MockModelProvider(model)
    if provider == "openai":
        return OpenAIProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"unknown model provider: {provider!r}")
