"""Finding model.

Two invariants are enforced here rather than left to rule authors:

1. Impact is reported in four separate categories that are never summed:
   static potential, runtime observed, estimated, validated.
2. ``PROVEN`` can only be set by attaching a validated experiment result.
   Static or runtime evidence alone caps at ``HIGH_CONFIDENCE``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any

from ai_auditor.ir.model import SourceLocation, stable_id


class EvidenceLevel(IntEnum):
    # Ordered so that comparisons express strength. DO_NOT_OPTIMIZE is a different
    # axis (a positive conclusion that the LLM is justified) and sorts lowest.
    DO_NOT_OPTIMIZE = 0
    HYPOTHESIS = 1
    LIKELY = 2
    HIGH_CONFIDENCE = 3
    PROVEN = 4

    def __str__(self) -> str:
        return self.name


class Severity(IntEnum):
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def __str__(self) -> str:
        return self.name


class Risk(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def __str__(self) -> str:
        return self.name


UNKNOWN = "UNKNOWN"


@dataclass
class Evidence:
    kind: str  # e.g. prompt_text, output_spec, graph, model_catalog, trace_stat, experiment
    description: str
    location: SourceLocation | None = None
    value: Any = None
    weight: float = 0.0  # contribution to confidence; negative = counter-evidence


@dataclass
class StaticPotential:
    """What could be removed per invocation of the component. Structural, not a measurement."""

    llm_calls_removed_per_invocation: float | None = None
    context_tokens_removed_per_invocation: int | None = None  # estimated tokens (approximate tokenizer)
    invocations_per_execution: str = "1"  # "1", "N (inside loop)", "1..3" ...
    notes: str = ""


@dataclass
class ObservedRuntime:
    n_executions: int
    calls_per_execution: float | None = None
    cost_per_execution: float | None = None  # USD; None when pricing unknown
    cost_unknown_calls: int = 0
    tokens_per_execution: float | None = None
    latency_ms_p50: float | None = None
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class Estimate:
    """Savings estimated from observed data + explicit assumptions. Never from literature numbers."""

    cost_saving_per_execution: float | None
    pct_of_component_cost: float | None
    method: str
    assumptions: list[str] = field(default_factory=list)


@dataclass
class Validated:
    experiment_id: str
    decision: str  # ACCEPT | REJECT | INCONCLUSIVE
    quality_delta: float | None
    quality_delta_ci: tuple[float, float] | None
    cost_delta_pct: float | None
    latency_delta_ms: float | None
    n_cases: int


@dataclass
class Impact:
    static_potential: StaticPotential | None = None
    observed: ObservedRuntime | None = None
    estimated: Estimate | None = None
    validated: Validated | None = None


@dataclass
class Challenge:
    """One adversarial counter-check applied to a finding."""

    name: str
    outcome: str  # passed | failed | unknown
    detail: str
    blocking: bool = False  # a failed blocking challenge demotes the finding to DO_NOT_OPTIMIZE / drops it


@dataclass
class Finding:
    rule_id: str
    title: str
    category: str  # deterministic | model_selection | context | caching | architecture | reliability | latency | necessity
    severity: Severity
    level: EvidenceLevel
    confidence: float  # 0..1 heuristic, see calibration notes in report
    component: str
    component_id: str | None
    location: SourceLocation | None
    evidence: list[Evidence]
    reasoning: str
    current_behavior: str
    recommended_change: str
    alternative: str = ""
    risk: Risk = Risk.MEDIUM
    risks: list[str] = field(default_factory=list)
    validation: str = ""  # how to validate (experiment design)
    requires_runtime_data: bool = True
    impact: Impact = field(default_factory=Impact)
    determinism: dict[str, Any] | None = None  # determinism score breakdown, when relevant
    challenges: list[Challenge] = field(default_factory=list)
    survived_review: bool | None = None  # None = review not run
    demoted_from: str | None = None  # original level if adversarial review demoted it
    related: list[str] = field(default_factory=list)  # ids of findings this one supersedes / overlaps
    superseded_by: str | None = None  # id of a stronger recommendation on the same component
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.rule_id}-{stable_id(self.rule_id, self.component_id or self.component, self.location)}"
        self.confidence = max(0.0, min(1.0, round(self.confidence, 3)))
        if self.level == EvidenceLevel.PROVEN and not (
            self.impact.validated and self.impact.validated.decision == "ACCEPT"
        ):
            # Invariant 2: PROVEN requires an accepted experiment.
            self.level = EvidenceLevel.HIGH_CONFIDENCE

    @property
    def actionable(self) -> bool:
        return self.level >= EvidenceLevel.HYPOTHESIS and self.survived_review is not False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = str(self.severity)
        d["level"] = str(self.level)
        d["risk"] = str(self.risk)
        return d
