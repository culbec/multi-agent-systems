from __future__ import annotations

import os

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Centralised configuration for Ollama-backed LLM usage.

    Override values via environment variables (prefixed with ``OLLAMA_``) or
    by mutating the singleton before passing it to ``EditorAgent``.
    """

    summarization_model: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_SUMMARIZATION_MODEL", "mistral"),
        description="Ollama model tag used by the Editor for article summarisation.",
    )
    base_url: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        description="Ollama OpenAI-compatible API endpoint.",
    )
    temperature: float = Field(
        default_factory=lambda: float(os.environ.get("OLLAMA_TEMPERATURE", "0.3")),
        description="Sampling temperature for deterministic summaries.",
    )
    max_tokens: int = Field(
        default_factory=lambda: int(os.environ.get("OLLAMA_MAX_TOKENS", "512")),
        description="Maximum tokens per summary generation call.",
    )
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "30")),
        description="HTTP timeout for a single LLM call.",
    )
    fallback_to_extract: bool = Field(
        default_factory=lambda: os.environ.get("OLLAMA_FALLBACK_TO_EXTRACT", "true").lower() == "true",
        description="When *True* and the LLM is unreachable, the Editor uses the ``article.summary`` field instead.",
    )

    def provider_kwargs(self) -> dict[str, object]:
        """Return keyword arguments compatible with ``spade_llm.LLMProvider``.

        :return dict[str, object]: Mapping consumed by the provider constructor.
        """
        return {
            "model": f"ollama/{self.summarization_model}",
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_seconds,
        }
