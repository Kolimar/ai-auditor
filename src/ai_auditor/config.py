"""Audit configuration (``.ai-auditor.yaml`` at the project root, or ``--config``)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


class UsageError(ValueError):
    """Invalid user input (configuration, experiment spec, dataset): reported as a usage error, not as a crash."""


@dataclass
class AuditConfig:
    # Quality constraint: minimize cost subject to these (used by experiments).
    quality_target: float = 0.95
    reliability_target: float = 0.99
    latency_target_ms: float | None = None
    non_inferiority_margin: float = 0.01  # max acceptable quality drop (absolute), decided BEFORE the experiment

    # Static analysis thresholds (starting points; tune per project).
    repeated_context_min_tokens: int = 500
    excessive_context_tokens: int = 4000
    always_loaded_description_tokens: int = 150
    rag_top_k_warn: int = 10
    rag_top_k_high: int = 20
    tool_count_warn: int = 10
    tool_tokens_warn: int = 10_000

    min_level: str = "HYPOTHESIS"  # lowest evidence level shown in the report
    disabled_rules: list[str] = field(default_factory=list)
    exclude: list[str] = field(
        default_factory=lambda: [".git", ".venv", "venv", "node_modules", "__pycache__", ".ai-auditor-cache", "dist", "build", ".tox", ".nox",
                                 ".mypy_cache", ".pytest_cache", ".ruff_cache", ".ipynb_checkpoints", "site-packages"]
    )
    model_tiers: dict[str, str] = field(default_factory=dict)  # pattern -> tier overrides
    pricing_file: str | None = None
    # Jupyter notebooks: "exploratory" (extracted, findings discarded as non-production), "production" or "skip"
    notebooks: str = "exploratory"

    @classmethod
    def load(cls, root: Path, explicit: Path | None = None) -> AuditConfig:
        path = explicit or (root / ".ai-auditor.yaml")
        if not path.exists():
            return cls()
        data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise UsageError(f"unknown config keys in {path}: {sorted(unknown)}")
        cfg = cls(**data)
        if cfg.notebooks not in ("exploratory", "production", "skip"):
            raise UsageError(f"notebooks must be exploratory, production or skip (got {cfg.notebooks!r})")
        return cfg
