"""Audit pipeline: extract -> IR/graph -> rules -> [runtime] -> adversarial review -> [experiments] -> necessity -> prioritize.

This is the only module that wires the stages together; each stage stays independently testable.
No stage calls an LLM: the optional LLM reviewer must be passed in explicitly.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai_auditor import __version__
from ai_auditor.analyzers.engine import AnalysisContext, EngineResult, run_rules
from ai_auditor.analyzers.finding import EvidenceLevel, Finding
from ai_auditor.config import AuditConfig
from ai_auditor.cost.pricing import PriceTable
from ai_auditor.ir.model import SystemIR
from ai_auditor.model_routing.catalog import ModelCatalog
from ai_auditor.optimization.adversarial import llm_review, review
from ai_auditor.optimization.necessity import necessity, prioritize
from ai_auditor.parser.project import extract_project
from ai_auditor.parser.tokens import METHOD as TOKEN_METHOD
from ai_auditor.tracing.stats import RuntimeStats


@dataclass
class AuditResult:
    root: str
    ir: SystemIR
    ctx: AnalysisContext
    findings: list[Finding]
    engine: EngineResult
    timings_ms: dict[str, float]
    extract_stats: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def actionable(self) -> list[Finding]:
        return [f for f in self.findings if f.actionable]

    @property
    def discarded(self) -> list[Finding]:
        return [f for f in self.findings if f.survived_review is False]

    @property
    def justified(self) -> list[Finding]:
        return [f for f in self.findings if f.level == EvidenceLevel.DO_NOT_OPTIMIZE and f.survived_review is not False]

    def unassessed_steps(self) -> list[str]:
        """LLM steps with no finding and no necessity conclusion: insufficient evidence either way."""
        seen = {f.component_id for f in self.findings} | {r for f in self.findings for r in f.related}
        return [s.name for s in self.ir.llm_steps() if s.id not in seen and not s.attrs.get("dead_code")]


def audit(
    root: Path,
    config: AuditConfig | None = None,
    *,
    use_cache: bool = True,
    runtime: RuntimeStats | None = None,
    only_rules: set[str] | None = None,
    llm_judge: Callable[[Finding], str | None] | None = None,
    experiments: list[Any] | None = None,
) -> AuditResult:
    root = Path(root)
    config = config or AuditConfig.load(root if root.is_dir() else root.parent)
    t: dict[str, float] = {}
    t0 = time.perf_counter()
    ir, stats = extract_project(root, config, use_cache)
    t["extract"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    prices = PriceTable.load(Path(config.pricing_file) if config.pricing_file else None)
    catalog = ModelCatalog.default(prices, config.model_tiers)
    ctx = AnalysisContext(ir, config, catalog, runtime)
    engine = run_rules(ctx, only_rules)
    t["rules"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    if runtime is not None:
        from ai_auditor.tracing.attach import attach_runtime, coverage

        attach_runtime(ctx, engine.findings, runtime)
    findings = review(ctx, engine.findings)
    if llm_judge is not None:
        findings = llm_review(findings, llm_judge)
    exp_notes: list[str] = []
    if experiments:
        from ai_auditor.experiments.attach import attach_experiments

        exp_notes = attach_experiments(findings, experiments)
    findings += necessity(ctx, findings)
    findings = prioritize(findings)
    t["review"] = (time.perf_counter() - t0) * 1000

    meta = {
        "auditor_version": __version__,
        "token_estimator": TOKEN_METHOD,
        "pricing_origin": prices.origin,
        "llm_calls_made_by_auditor": 0 if llm_judge is None else "see reviewer",
        "runtime_data": runtime is not None,
    }
    if runtime is not None:
        meta["runtime"] = {"executions": runtime.n_executions, "spans": runtime.n_spans, "synthetic": runtime.synthetic,
                           "sources": runtime.sources, "unattributed_spans": runtime.unattributed_spans,
                           "total_cost_usd": round(runtime.total_cost_usd, 6), "cost_unknown_calls": runtime.cost_unknown_calls,
                           "notes": runtime.notes, **coverage(ctx, runtime)}
    if experiments:
        meta["experiments"] = {"attached": len(experiments), "notes": exp_notes,
                               "by_decision": dict(Counter(r.decision for r in experiments))}
    return AuditResult(str(root.resolve()), ir, ctx, findings, engine, t, stats, meta)


def min_level_filter(findings: list[Finding], level: str) -> list[Finding]:
    lvl = EvidenceLevel[level]
    return [f for f in findings if f.level >= lvl or f.level == EvidenceLevel.DO_NOT_OPTIMIZE]
