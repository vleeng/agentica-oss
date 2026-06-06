from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal

from app.core.config import get_settings

ProductProfile = Literal["saas", "platform", "oss"]


@dataclass(frozen=True)
class ProductFeatureFlags:
    billing: bool
    plans: bool
    usage_limits: bool
    signup: bool
    enterprise_auth: bool
    white_label: bool
    community_theme: bool

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ProductProfileState:
    profile: ProductProfile
    display_name: str
    features: ProductFeatureFlags

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "display_name": self.display_name,
            "features": self.features.to_dict(),
        }


def normalize_product_profile(value: str | None) -> ProductProfile:
    raw = (value or "").strip().lower()
    if raw in {"saas", "platform", "oss"}:
        return raw  # type: ignore[return-value]
    if raw in {"opensource", "open-source", "community"}:
        return "oss"
    if raw in {"cloud", "hosted"}:
        return "saas"
    return "saas"


def build_product_profile_state(profile: ProductProfile) -> ProductProfileState:
    if profile == "platform":
        return ProductProfileState(
            profile="platform",
            display_name="Agentica Platform",
            features=ProductFeatureFlags(
                billing=False,
                plans=False,
                usage_limits=False,
                signup=False,
                enterprise_auth=False,
                white_label=False,
                community_theme=False,
            ),
        )

    if profile == "oss":
        return ProductProfileState(
            profile="oss",
            display_name="Agentica OSS",
            features=ProductFeatureFlags(
                billing=False,
                plans=False,
                usage_limits=False,
                signup=False,
                enterprise_auth=False,
                white_label=False,
                community_theme=True,
            ),
        )

    return ProductProfileState(
        profile="saas",
        display_name="Agentica",
        features=ProductFeatureFlags(
            billing=True,
            plans=True,
            usage_limits=True,
            signup=True,
            enterprise_auth=False,
            white_label=False,
            community_theme=False,
        ),
    )


@lru_cache
def get_product_profile_state() -> ProductProfileState:
    settings = get_settings()
    return build_product_profile_state(normalize_product_profile(settings.product_profile))
