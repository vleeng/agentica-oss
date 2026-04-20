from __future__ import annotations

import os

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.runtime.llm import resolve_base_url

settings = get_settings()


class TextGenerationClient:
    def __init__(self):
        self.provider = settings.builder_provider.lower()
        self.model = settings.builder_model

        if self.provider == "anthropic":
            api_key = settings.builder_api_key or settings.anthropic_api_key
            self._client = AsyncAnthropic(api_key=api_key)
        else:
            env_name = f"{self.provider.upper()}_API_KEY"
            api_key = (
                settings.builder_api_key
                or os.getenv(env_name)
                or settings.openai_api_key
                or ""
            )
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=resolve_base_url(self.provider, settings.builder_base_url),
            )

    async def complete(self, prompt: str, max_tokens: int, temperature: float = 0.2) -> str:
        if self.provider == "anthropic":
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()

        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()
