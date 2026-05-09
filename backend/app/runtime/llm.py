from __future__ import annotations

from dataclasses import dataclass
import os
from types import MethodType
from typing import Any

from app.schemas.agent import ModelParams


OPENAI_COMPATIBLE_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "moonshot": "https://api.moonshot.ai/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}

OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openrouter",
    "deepseek",
    "qwen",
    "moonshot",
    "zhipu",
    "custom_openai",
}

PROVIDER_ALIASES = {
    "openroute": "openrouter",
    # Compatibilidad con llaves legacy cargadas como "google" para modelos
    # servidos por OpenRouter (ej: google/gemma-...:free).
    "google": "openrouter",
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str | None = None

    @property
    def is_anthropic(self) -> bool:
        return canonical_provider(self.provider) == "anthropic"

    @property
    def is_openai_compatible(self) -> bool:
        return canonical_provider(self.provider) in OPENAI_COMPATIBLE_PROVIDERS


def bind_crewai_call_adapter(llm: Any, provider: str):
    provider = canonical_provider(provider)
    llm._agentica_provider = provider

    def _call(self, messages: list[dict[str, Any]] | str, callbacks: list[Any] | None = None) -> str:
        import litellm

        payload = messages
        if isinstance(messages, str):
            payload = [{"role": "user", "content": messages}]

        params: dict[str, Any] = {
            "model": self.model,
            "messages": payload,
            "timeout": getattr(self, "timeout", 120.0),
            "temperature": getattr(self, "temperature", None),
            "top_p": getattr(self, "top_p", None),
            "n": getattr(self, "n", None),
            "stop": getattr(self, "stop", None),
            "presence_penalty": getattr(self, "presence_penalty", None),
            "frequency_penalty": getattr(self, "frequency_penalty", None),
            "logit_bias": getattr(self, "logit_bias", None),
            "response_format": getattr(self, "response_format", None),
            "seed": getattr(self, "seed", None),
            "logprobs": getattr(self, "logprobs", None),
            "top_logprobs": getattr(self, "top_logprobs", None),
            "api_key": getattr(self, "api_key", None),
            "base_url": getattr(self, "base_url", None),
            "stream": False,
        }

        if uses_max_completion_tokens(self.model, self._agentica_provider):
            params["max_completion_tokens"] = getattr(self, "max_completion_tokens", None) or getattr(self, "max_tokens", None)
        else:
            params["max_tokens"] = getattr(self, "max_tokens", None)

        response = litellm.completion(**{k: v for k, v in params.items() if v is not None})
        return response["choices"][0]["message"]["content"]

    llm.call = MethodType(_call, llm)
    return llm


def infer_provider(params: ModelParams) -> str:
    if params.provider:
        return canonical_provider(params.provider)

    model = params.model.lower()
    if model.startswith("openrouter:") or model.startswith("openrouter/"):
        return "openrouter"
    if model.startswith("deepseek") or model.startswith("deepseek/"):
        return "deepseek"
    if model.startswith("qwen") or model.startswith("qwen/"):
        return "qwen"
    if model.startswith("moonshot") or model.startswith("kimi"):
        return "moonshot"
    if model.startswith("zhipu") or model.startswith("glm-"):
        return "zhipu"
    if "gpt" in model or model.startswith("o1") or model.startswith("o3") or model.startswith("o4"):
        return "openai"
    if "claude" in model:
        return "anthropic"
    # Modelo no reconocido → asumir openrouter como gateway universal
    return "openrouter"


def canonical_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    return PROVIDER_ALIASES.get(normalized, normalized)


def normalize_model_name(model: str, provider: str) -> str:
    provider = canonical_provider(provider)
    if provider == "openrouter" and model.startswith("openrouter:"):
        return model.split(":", 1)[1]
    if provider == "openrouter" and model.startswith("openrouter/"):
        return model.split("/", 1)[1]
    if provider in {"openai", "custom_openai"} and model.startswith("openai/"):
        return model.split("/", 1)[1]
    if provider == "anthropic" and model.startswith("anthropic/"):
        return model.split("/", 1)[1]
    if provider in {"deepseek", "qwen", "moonshot", "zhipu"} and model.startswith(f"{provider}/"):
        return model.split("/", 1)[1]
    return model


def qualify_model_name(model: str, provider: str) -> str:
    provider = canonical_provider(provider)
    if provider == "openrouter":
        if model.startswith("openrouter:"):
            return f"openrouter/{model.split(':', 1)[1]}"
        if model.startswith("openrouter/"):
            return model
        return f"openrouter/{model}"
    return model


def qualify_crewai_model_name(model: str, provider: str) -> str:
    provider = canonical_provider(provider)
    normalized = normalize_model_name(model, provider)

    if provider == "anthropic":
        return f"anthropic/{normalized}"
    if provider == "openrouter":
        return f"openrouter/{normalized}"
    if provider in {"openai", "deepseek", "qwen", "moonshot", "zhipu", "custom_openai"}:
        return f"openai/{normalized}"
    return normalized


def uses_max_completion_tokens(model: str, provider: str) -> bool:
    provider = canonical_provider(provider)
    normalized = normalize_model_name(model, provider).lower()
    if provider not in {"openai", "custom_openai"}:
        return False
    return (
        normalized.startswith("gpt-5")
        or normalized.startswith("o1")
        or normalized.startswith("o3")
        or normalized.startswith("o4")
    )


def resolve_base_url(provider: str, explicit_base_url: str | None = None) -> str | None:
    if explicit_base_url:
        return explicit_base_url
    if provider == "custom_openai":
        return os.getenv("CUSTOM_OPENAI_BASE_URL") or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider)


def create_chat_llm(params: ModelParams, config: LLMConfig):
    provider = canonical_provider(params.provider or config.provider or infer_provider(params))
    model = normalize_model_name(params.model, provider)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            api_key=config.api_key,
        )

    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": model,
            "temperature": params.temperature,
            "api_key": config.api_key,
        }
        if uses_max_completion_tokens(model, provider):
            kwargs["model_kwargs"] = {"max_completion_tokens": params.max_tokens}
        else:
            kwargs["max_tokens"] = params.max_tokens
        base_url = config.base_url or resolve_base_url(provider, params.base_url)
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Proveedor LLM no soportado: {provider}")
