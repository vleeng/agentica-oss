from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.session import PublicSessionFactory
from app.runtime.llm import canonical_provider, infer_provider, normalize_model_name
from app.schemas.agent import ModelParams
from app.schemas.tenant import LLMProviderModel


def normalize_provider_models(raw_models: Any) -> list[LLMProviderModel]:
    normalized: list[LLMProviderModel] = []
    if not isinstance(raw_models, list):
        return normalized

    for raw in raw_models:
        if isinstance(raw, str):
            model_id = raw.strip()
            if model_id:
                normalized.append(LLMProviderModel(id=model_id))
            continue

        if isinstance(raw, LLMProviderModel):
            normalized.append(raw)
            continue

        if isinstance(raw, dict):
            model_id = str(raw.get("id", "")).strip()
            if not model_id:
                continue
            normalized.append(
                LLMProviderModel(
                    id=model_id,
                    input_cost_per_million=float(raw.get("input_cost_per_million", 0.0) or 0.0),
                    output_cost_per_million=float(raw.get("output_cost_per_million", 0.0) or 0.0),
                )
            )

    return normalized


def estimate_text_tokens(text: str) -> int:
    stripped = (text or "").strip()
    if not stripped:
        return 0
    # Heurística simple y estable: ~4 caracteres por token.
    return max(1, round(len(stripped) / 4))


def estimate_usage_tokens(
    user_input: str,
    output: str,
    *,
    reported_tokens_in: int = 0,
    reported_tokens_out: int = 0,
) -> tuple[int, int]:
    tokens_in = reported_tokens_in if reported_tokens_in > 0 else estimate_text_tokens(user_input)
    tokens_out = reported_tokens_out if reported_tokens_out > 0 else estimate_text_tokens(output)
    return tokens_in, tokens_out


def calculate_model_cost(
    tokens_in: int,
    tokens_out: int,
    model: LLMProviderModel | None,
) -> float:
    if not model:
        return 0.0
    return round(
        (tokens_in * model.input_cost_per_million / 1_000_000)
        + (tokens_out * model.output_cost_per_million / 1_000_000),
        6,
    )


async def resolve_model_pricing(tenant_id: str, params: ModelParams) -> LLMProviderModel | None:
    provider = canonical_provider(params.provider or infer_provider(params))

    async with PublicSessionFactory() as db:
        if params.llm_key_id:
            result = await db.execute(
                text(
                    """
                    SELECT models
                    FROM llm_provider_keys
                    WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tid AS uuid)
                    """
                ),
                {"id": params.llm_key_id, "tid": tenant_id},
            )
        else:
            result = await db.execute(
                text(
                    """
                    SELECT models
                    FROM llm_provider_keys
                    WHERE tenant_id = CAST(:tid AS uuid) AND provider = :provider AND is_default = TRUE
                    """
                ),
                {"tid": tenant_id, "provider": provider},
            )

        row = result.fetchone()
        if not row and provider == "openrouter" and not params.llm_key_id:
            result = await db.execute(
                text(
                    """
                    SELECT models
                    FROM llm_provider_keys
                    WHERE tenant_id = CAST(:tid AS uuid) AND provider = 'google' AND is_default = TRUE
                    """
                ),
                {"tid": tenant_id},
            )
            row = result.fetchone()

    if not row:
        return None

    normalized_models = normalize_provider_models(row.models)
    target_model = normalize_model_name(params.model, provider).lower()

    for model in normalized_models:
        candidate = normalize_model_name(model.id, provider).lower()
        if candidate == target_model or model.id.lower() == params.model.lower():
            return model

    return None
