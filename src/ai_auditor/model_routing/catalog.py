"""Model catalog: resolve a ModelRef to tier, price row and prompt-caching rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml

from ai_auditor.cost.pricing import Price, PriceTable, normalize_model_id
from ai_auditor.ir.model import ModelRef

TIER_ORDER = {"small": 0, "medium": 1, "large": 2, "frontier": 3}


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str | None
    tier: str  # small | medium | large | frontier | unknown
    tier_source: str  # pattern | price | config | unknown
    price: Price | None
    cache_mechanism: str | None  # explicit | automatic | None (unknown)
    cache_min_tokens: int | None
    via_alias: str | None = None


def _provider_of(model_id: str) -> str | None:
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith(("gpt", "o1", "o3", "o4", "text-embedding", "chatgpt")):
        return "openai"
    if model_id.startswith("gemini"):
        return "google"
    if model_id.startswith("deepseek"):
        return "deepseek"
    return None


class ModelCatalog:
    def __init__(self, prices: PriceTable, meta: dict[str, Any], tier_overrides: dict[str, str] | None = None) -> None:
        self.prices = prices
        self.meta = meta
        self.aliases: dict[str, str] = meta.get("aliases", {})
        self.overrides = tier_overrides or {}
        self.retrieved_at = meta.get("retrieved_at")

    @classmethod
    def default(cls, prices: PriceTable | None = None, tier_overrides: dict[str, str] | None = None) -> ModelCatalog:
        text = resources.files("ai_auditor.model_routing").joinpath("data/models.yaml").read_text()
        return cls(prices or PriceTable.load(), yaml.safe_load(text), tier_overrides)

    def resolve(self, ref: ModelRef | str | None) -> ModelInfo | None:
        raw = ref if isinstance(ref, str) else (ref.raw if ref is not None else None)
        if not raw:
            return None
        alias = None
        key = raw.strip().lower()
        if key in self.aliases:
            alias, raw = key, self.aliases[key]
        mid = normalize_model_id(raw)
        provider = (ref.provider if isinstance(ref, ModelRef) and ref.provider else None) or _provider_of(mid)
        price = self.prices.get(mid)
        if price and not provider:
            provider = price.provider
        tier, source = self._tier(mid, provider, price)
        mech, minimum = self._caching(mid, provider)
        return ModelInfo(mid, provider, tier, source, price, mech, minimum, alias)

    def _tier(self, mid: str, provider: str | None, price: Price | None) -> tuple[str, str]:
        for pat, tier in self.overrides.items():
            if re.search(pat, mid):
                return tier, "config"
        for row in self.meta.get("tier_patterns", []):
            if (provider is None or row["provider"] == provider) and re.search(row["pattern"], mid):
                return row["tier"], "pattern"
        if price and price.input is not None:
            th = self.meta.get("price_tiers", {})
            for tier in ("frontier", "large", "medium"):
                if price.input >= th.get(tier, float("inf")):
                    return tier, "price"
            return "small", "price"
        return "unknown", "unknown"

    def _caching(self, mid: str, provider: str | None) -> tuple[str | None, int | None]:
        rules = self.meta.get("caching", {}).get(provider or "", None)
        if not rules:
            return None, None
        for row in rules.get("min_tokens", []):
            if re.search(row["pattern"], mid):
                return rules.get("mechanism"), int(row["min"])
        return rules.get("mechanism"), None

    def cheaper_same_provider(self, info: ModelInfo) -> list[ModelInfo]:
        """Smaller-tier models of the same provider with a known price, cheapest last-resort first."""
        if info.provider is None:
            return []
        out = []
        for p in self.prices.models():
            if p.provider != info.provider or p.input is None or "embedding" in p.model:
                continue
            cand = self.resolve(ModelRef(raw=p.model, provider=p.provider))
            if cand and TIER_ORDER.get(cand.tier, 9) < TIER_ORDER.get(info.tier, -1):
                out.append(cand)
        # prefer the most recent-looking id per tier: keep cheapest per tier
        best: dict[str, ModelInfo] = {}
        for c in sorted(out, key=lambda c: c.price.input if c.price and c.price.input is not None else 1e9):
            best.setdefault(c.tier, c)
        return sorted(best.values(), key=lambda c: TIER_ORDER[c.tier], reverse=True)
