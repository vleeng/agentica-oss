from __future__ import annotations

from dataclasses import dataclass
import os

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
    if provider == "openrouter" and model.startswith("openrouter:"):
        return model.split(":", 1)[1]
    if provider == "openrouter" and model.startswith("openrouter/"):
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


def resolve_base_url(provider: str, explicit_base_url: str | None = None) -> str | None:
    if explicit_base_url:
        return explicit_base_url
    if provider == "custom_openai":
        return os.getenv("CUSTOM_OPENAI_BASE_URL") or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    return OPENAI_COMPATIBLE_BASE_URLS.get(provider)


def create_chat_llm(params: ModelParams, config: LLMConfig):
    provider = canonical_provider(config.provider)
    model = normalize_model_name(params.model, provider)
    if config.is_anthropic:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            api_key=config.api_key,
        )

    if config.is_openai_compatible:
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": model,
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "api_key": config.api_key,
        }
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Proveedor LLM no soportado: {provider}")
