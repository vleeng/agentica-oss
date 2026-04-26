from __future__ import annotations
import os
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.runtime.llm import resolve_base_url

settings = get_settings()


async def _get_builder_config() -> tuple[str, str, str]:
    """Returns (provider, model, api_key) reading from DB first, then env vars."""
    try:
        from app.db.session import PublicSessionFactory
        from sqlalchemy import text
        async with PublicSessionFactory() as db:
            result = await db.execute(
                text("SELECT key, value FROM system_config WHERE key IN ('builder_provider','builder_model','builder_llm_key_id')")
            )
            rows = {r.key: r.value for r in result.fetchall()}

        provider = rows.get("builder_provider") or settings.builder_provider
        model = rows.get("builder_model") or settings.builder_model

        # If a vault key is configured, decrypt and use it
        llm_key_id = rows.get("builder_llm_key_id")
        if llm_key_id:
            from sqlalchemy import text as _text
            async with PublicSessionFactory() as db:
                r = await db.execute(
                    _text("SELECT encrypted_key FROM public.llm_provider_keys WHERE id = CAST(:id AS uuid)"),
                    {"id": llm_key_id}
                )
                row = r.fetchone()
                if row:
                    from app.core.security import decrypt_provider_key
                    return provider, model, decrypt_provider_key(row.encrypted_key)

        # Fall back to env vars
        api_key = (
            settings.builder_api_key
            or os.getenv(f"{provider.upper()}_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or ""
        )
        return provider, model, api_key
    except Exception:
        # Fallback to env only
        provider = settings.builder_provider
        model = settings.builder_model
        api_key = settings.builder_api_key or os.getenv(f"{provider.upper()}_API_KEY") or ""
        return provider, model, api_key


class TextGenerationClient:
    async def complete(self, prompt: str, max_tokens: int, temperature: float = 0.2) -> str:
        provider, model, api_key = await _get_builder_config()

        if provider == "anthropic":
            client = AsyncAnthropic(api_key=api_key or None)
            message = await client.messages.create(
                model=model, max_tokens=max_tokens, temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        else:
            client = AsyncOpenAI(
                api_key=api_key or "no-key",
                base_url=resolve_base_url(provider, None),
            )
            response = await client.chat.completions.create(
                model=model, max_tokens=max_tokens, temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return (response.choices[0].message.content or "").strip()
