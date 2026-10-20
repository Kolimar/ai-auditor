"""Rule engine: registry, analysis context and execution.

Adding a rule never requires touching this module:

* built-in rules live in ``ai_auditor.rules`` and register via ``@register``;
* external packs expose a module under the ``ai_auditor.rules`` entry-point
  group; importing it runs their ``@register`` decorators.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from functools import cached_property
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any, ClassVar, Iterable

from ai_auditor.analyzers.finding import EvidenceLevel, Finding
from ai_auditor.graph.workflow_graph import WorkflowGraph
from ai_auditor.ir.model import LLMStep, SystemIR

if TYPE_CHECKING:
    from ai_auditor.config import AuditConfig
    from ai_auditor.model_routing.catalog import ModelCatalog
    from ai_auditor.optimization.profile import TaskProfile
    from ai_auditor.tracing.stats import RuntimeStats


class Rule:
    """Base class. Subclasses set the class attributes and implement ``check``."""

    id: ClassVar[str]
    title: ClassVar[str]
    category: ClassVar[str]
    # "static" rules run on IR only; "runtime" rules need traces and are skipped without them.
    needs: ClassVar[frozenset[str]] = frozenset({"static"})

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:  # pragma: no cover - interface
        raise NotImplementedError


_REGISTRY: dict[str, type[Rule]] = {}


def register(cls: type[Rule]) -> type[Rule]:
    if cls.id in _REGISTRY and _REGISTRY[cls.id] is not cls:
        raise ValueError(f"rule id collision: {cls.id}")
    _REGISTRY[cls.id] = cls
    return cls


def load_rules() -> dict[str, type[Rule]]:
    import ai_auditor.rules as builtin

    for mod in pkgutil.iter_modules(builtin.__path__):
        importlib.import_module(f"{builtin.__name__}.{mod.name}")
    for ep in entry_points(group="ai_auditor.rules"):
        ep.load()
    return dict(sorted(_REGISTRY.items()))


@dataclass
class AnalysisContext:
    ir: SystemIR
    config: AuditConfig
    catalog: ModelCatalog
    runtime: RuntimeStats | None = None
    _profiles: dict[str, TaskProfile] = field(default_factory=dict)

    @cached_property
    def graph(self) -> WorkflowGraph:
        return WorkflowGraph(self.ir)

    def profile(self, step: LLMStep) -> TaskProfile:
        """Task profile is computed once per step and shared by all rules (no repeated analysis)."""
        from ai_auditor.optimization.profile import build_profile

        if step.id not in self._profiles:
            self._profiles[step.id] = build_profile(step, self.graph, self.catalog)
        return self._profiles[step.id]

    @property
    def has_runtime(self) -> bool:
        return self.runtime is not None and self.runtime.n_executions > 0


@dataclass
class EngineResult:
    findings: list[Finding]
    rules_run: list[str]
    rules_skipped: dict[str, str]
    errors: dict[str, str]
    stats: dict[str, Any] = field(default_factory=dict)


def run_rules(ctx: AnalysisContext, only: set[str] | None = None) -> EngineResult:
    rules = load_rules()
    findings: list[Finding] = []
    ran: list[str] = []
    skipped: dict[str, str] = {}
    errors: dict[str, str] = {}
    disabled = set(ctx.config.disabled_rules)
    for rule_id, cls in rules.items():
        if only and rule_id not in only:
            continue
        if rule_id in disabled:
            skipped[rule_id] = "disabled by config"
            continue
        if "runtime" in cls.needs and not ctx.has_runtime:
            skipped[rule_id] = "needs runtime traces"
            continue
        try:
            produced = list(cls().check(ctx))
        except Exception as exc:  # a broken rule must not take down the audit
            errors[rule_id] = f"{type(exc).__name__}: {exc}"
            continue
        ran.append(rule_id)
        findings.extend(produced)
    return EngineResult(findings, ran, skipped, errors)


def level_from_confidence(conf: float, cap: EvidenceLevel) -> EvidenceLevel | None:
    """Map a heuristic confidence to an evidence level, never above ``cap``.

    ``cap`` encodes the strongest claim the *kind* of evidence allows: text
    heuristics alone cap at LIKELY, corroborated structure at HIGH_CONFIDENCE.
    """
    if conf >= 0.85:
        lvl = EvidenceLevel.HIGH_CONFIDENCE
    elif conf >= 0.6:
        lvl = EvidenceLevel.LIKELY
    elif conf >= 0.3:
        lvl = EvidenceLevel.HYPOTHESIS
    else:
        return None
    return min(lvl, cap)


def combine(weights: Iterable[float]) -> float:
    """Noisy-OR for supporting evidence, multiplicative discount for counter-evidence.

    Each positive weight w is read as "this signal alone gives w probability that the
    smell is real"; independent signals combine as 1 - prod(1 - w). Each negative
    weight -v removes a fraction v of the remaining confidence. Explainable and
    monotone; calibrated afterwards against the golden set (see evaluation/).
    """
    pos = 1.0
    discount = 1.0
    for w in weights:
        if w > 0:
            pos *= 1.0 - min(w, 0.99)
        elif w < 0:
            discount *= 1.0 - min(-w, 0.99)
    return (1.0 - pos) * discount
