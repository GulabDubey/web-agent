"""
Chat models for any configured provider.

Django (Admin → LLM providers) decides which provider/model each website
uses; app/services/llm_config_service.py fetches that and calls
`get_chat_model`. Two client families cover every provider:
  - "anthropic": Claude via langchain-anthropic
  - "openai":    OpenAI and any OpenAI-compatible API (Gemini, Groq,
                 OpenRouter, DeepSeek, Mistral, Ollama, …) via base_url
"""

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, field

from app.config.settings import settings

MAX_TOKENS = 2048
_CACHE_SIZE = 32


@dataclass(frozen=True)
class LLMConfig:
    api_type: str  # "anthropic" | "openai"
    model: str
    api_key: str = field(repr=False)
    base_url: str = ""
    provider: str = ""
    source: str = "env"  # "website" | "default" (from Django) | "env" (local fallback)

    @property
    def cache_key(self):
        digest = hashlib.sha256(self.api_key.encode()).hexdigest()
        return (self.api_type, self.base_url, self.model, digest)


class UnsupportedProvider(Exception):
    pass


def env_llm_config():
    """This service's own .env Anthropic settings: used until Django has a provider."""
    return LLMConfig(
        api_type="anthropic",
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        provider="Anthropic (.env)",
        source="env",
    )


def _build(config: LLMConfig):
    if config.api_type == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = {}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return ChatAnthropic(
            model=config.model,
            anthropic_api_key=config.api_key,
            # Current models think before answering and that thinking counts
            # toward max_tokens, so leave headroom or replies get cut off.
            max_tokens=MAX_TOKENS,
            # Short support answers don't need deep reasoning; low effort keeps
            # thinking (and latency/cost) minimal on every current model.
            output_config={"effort": "low"},
            **kwargs,
        )

    if config.api_type == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url or None,
            max_tokens=MAX_TOKENS,
            # Usage numbers feed the per-site daily token budget.
            stream_usage=True,
        )

    raise UnsupportedProvider(f"Unsupported LLM API type: {config.api_type!r}")


_models: "OrderedDict[tuple, object]" = OrderedDict()
_lock = threading.Lock()


def get_chat_model(config: LLMConfig):
    """A (cached) chat model for this provider/model/key combination."""
    key = config.cache_key
    with _lock:
        if key in _models:
            _models.move_to_end(key)
            return _models[key]

    model = _build(config)

    with _lock:
        _models[key] = model
        _models.move_to_end(key)
        while len(_models) > _CACHE_SIZE:
            _models.popitem(last=False)
    return model
