"""Versioned price table. Missing price -> None (reported as UNKNOWN), never imputed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Price:
    model: str
    provider: str
    input: float | None
    output: float | None
    cache_read: float | None
    cache_write: float | None
    batch_input: float | None
    batch_output: float | None
    source_url: str | None
    retrieved_at: str
    condition: str | None = None


def normalize_model_id(raw: str) -> str:
    s = raw.strip().lower()
    for prefix in ("anthropic/", "openai/", "google/", "gemini/", "models/", "bedrock/", "vertex_ai/", "azure/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    if ":" in s and not s.startswith("ft:"):
        s = s.split(":", 1)[1] if s.split(":", 1)[0] in ("openai", "anthropic", "google-gla", "google", "groq") else s
    s = re.sub(r"-(20\d{6}|\d{4}-\d{2}-\d{2})$", "", s)
    s = re.sub(r"-latest$", "", s)
    s = s.replace(".", "-") if s.startswith("claude") else s
    return s


class PriceTable:
    def __init__(self, data: dict[str, Any], origin: str) -> None:
        self.origin = origin
        self.retrieved_at = str(data.get("retrieved_at", "unknown"))
        self.verification = data.get("verification", "")
        self._by_id: dict[str, list[Price]] = {}
        for m in data.get("models", []):
            p = Price(
                model=str(m["id"]), provider=str(m.get("provider", "")), input=m.get("input"), output=m.get("output"),
                cache_read=m.get("cache_read"), cache_write=m.get("cache_write"), batch_input=m.get("batch_input"),
                batch_output=m.get("batch_output"), source_url=m.get("source_url"), retrieved_at=self.retrieved_at,
                condition=m.get("condition"),
            )
            self._by_id.setdefault(normalize_model_id(p.model), []).append(p)

    @classmethod
    def load(cls, path: Path | None = None) -> PriceTable:
        if path is not None:
            return cls(yaml.safe_load(path.read_text()) or {}, str(path))
        text = resources.files("ai_auditor.cost").joinpath("data/pricing.yaml").read_text()
        return cls(yaml.safe_load(text) or {}, "builtin:cost/data/pricing.yaml")

    def get(self, model: str | None, prompt_tokens: int | None = None) -> Price | None:
        if not model:
            return None
        rows = self._by_id.get(normalize_model_id(model))
        if not rows:
            return None
        if len(rows) == 1 or prompt_tokens is None:
            return rows[0]
        for r in rows:  # e.g. "prompt_tokens > 100000"
            m = re.match(r"prompt_tokens\s*(<=|>)\s*(\d+)", r.condition or "")
            if m and ((m.group(1) == "<=" and prompt_tokens <= int(m.group(2))) or (m.group(1) == ">" and prompt_tokens > int(m.group(2)))):
                return r
        return rows[0]

    def models(self) -> list[Price]:
        return [rows[0] for rows in self._by_id.values()]
