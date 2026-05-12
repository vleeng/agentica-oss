from __future__ import annotations

from dataclasses import dataclass
import os
from types import MethodType
from typing import Any
import json

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
        if supports_stop_parameter(self.model, self._agentica_provider):
            params["stop"] = getattr(self, "stop", None)

        if uses_max_completion_tokens(self.model, self._agentica_provider):
            params["max_completion_tokens"] = getattr(self, "max_completion_tokens", None) or getattr(self, "max_tokens", None)
        else:
            params["max_tokens"] = getattr(self, "max_tokens", None)

        response = litellm.completion(**{k: v for k, v in params.items() if v is not None})
        return _coerce_crewai_response_text(response)

    llm.call = MethodType(_call, llm)
    return llm


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stringify_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            item_type = _get_field(item, "type")
            if item_type in {"text", "output_text"}:
                text_value = _get_field(item, "text") or _get_field(item, "content")
                if text_value:
                    parts.append(str(text_value))
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def _format_tool_call_for_crewai(tool_call: Any) -> str:
    function_block = _get_field(tool_call, "function", tool_call)
    tool_name = _get_field(function_block, "name") or _get_field(tool_call, "name") or "tool"
    raw_arguments = _get_field(function_block, "arguments") or _get_field(tool_call, "arguments") or "{}"
    if isinstance(raw_arguments, str):
        action_input = raw_arguments.strip() or "{}"
    else:
        try:
            action_input = json.dumps(raw_arguments, ensure_ascii=False)
        except Exception:
            action_input = "{}"
    return (
        "Thought: I should use a tool to continue.\n"
        f"Action: {tool_name}\n"
        f"Action Input: {action_input}"
    )


def _coerce_crewai_response_text(response: Any) -> str:
    choices = _get_field(response, "choices", []) or []
    first_choice = choices[0] if choices else None
    message = _get_field(first_choice, "message", {})
    content = _stringify_content(_get_field(message, "content"))
    if content.strip():
        return content

    tool_calls = _get_field(message, "tool_calls", []) or []
    if tool_calls:
        return _format_tool_call_for_crewai(tool_calls[0])

    finish_reason = _get_field(first_choice, "finish_reason")
    if finish_reason == "tool_calls":
        return (
            "Thought: I now can give a great answer\n"
            "Final Answer: No pude convertir la respuesta del modelo a un formato util para CrewAI."
        )

    return "Thought: I now can give a great answer\nFinal Answer: No pude generar una respuesta util."


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


def supports_stop_parameter(model: str, provider: str) -> bool:
    return not uses_max_completion_tokens(model, provider)


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
