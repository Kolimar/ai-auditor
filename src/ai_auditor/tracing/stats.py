"""Runtime statistics per component, computed from spans.

An *execution* is one trace_id. Rates carry 95% Wilson intervals; a zero count carries the exact one-sided upper
bound (≈ 3/n). Costs are summed only over calls whose cost is known; the number of UNKNOWN-cost calls is reported
next to every total.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ai_auditor.evaluation.stats import wilson, zero_events_upper
from ai_auditor.tracing.schema import Span


@dataclass
class Rate:
    k: int
    n: int

    @property
    def value(self) -> float | None:
        return self.k / self.n if self.n else None

    @property
    def ci(self) -> tuple[float, float]:
        return wilson(self.k, self.n)

    @property
    def upper_if_zero(self) -> float | None:
        return zero_events_upper(self.n) if self.k == 0 and self.n else None

    def __str__(self) -> str:
        if not self.n:
            return "n/a (n=0)"
        if self.k == 0:
            return f"0/{self.n} (95% upper bound {self.upper_if_zero:.3f})"
        lo, hi = self.ci
        return f"{self.k}/{self.n} = {self.value:.3f} [95% CI {lo:.3f}, {hi:.3f}]"


@dataclass
class ComponentStats:
    component: str
    calls: int = 0
    executions: int = 0  # executions in which the component ran at least once
    calls_per_execution: float | None = None  # over executions where it ran
    max_calls_in_execution: int = 0
    tokens: dict[str, int] = field(default_factory=lambda: {"uncached_input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": 0})
    usage_unknown_calls: int = 0
    cost_usd: float = 0.0
    cost_known_calls: int = 0
    cost_unknown_calls: int = 0
    cost_unknown_reasons: list[str] = field(default_factory=list)
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    retries: Rate = field(default_factory=lambda: Rate(0, 0))
    errors: Rate = field(default_factory=lambda: Rate(0, 0))
    validation_failures: Rate = field(default_factory=lambda: Rate(0, 0))
    duplicate_calls: int = 0  # identical request (prompt_hash) repeated within the same execution
    distinct_inputs: int | None = None
    hashed_inputs: int = 0  # calls that carried an input hash (distinct_inputs is over these only)
    distinct_outputs: int | None = None
    self_consistency: Rate | None = None  # input groups with ≥2 calls whose outputs were all identical
    cache_read_share: float | None = None  # cache_read / total input
    median_gap_s: float | None = None  # median time between consecutive calls (for cache TTL reasoning)
    models: dict[str, int] = field(default_factory=dict)
    labels: dict[str, int] = field(default_factory=dict)  # output value distribution (when outputs are short labels)

    @property
    def cost_per_execution(self) -> float | None:
        if not self.cost_known_calls or not self.executions or self.cost_unknown_calls:
            return None
        return self.cost_usd / self.executions


@dataclass
class RuntimeStats:
    n_executions: int
    n_spans: int
    components: dict[str, ComponentStats]
    synthetic: bool
    sources: dict[str, int]
    unattributed_spans: int
    total_cost_usd: float
    cost_unknown_calls: int
    notes: list[str] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list, repr=False)

    def get(self, name: str | None) -> ComponentStats | None:
        if not name:
            return None
        return self.components.get(name) or next((c for k, c in self.components.items() if k.lower() == name.lower()), None)


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    i = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[i]


def compute_stats(spans: list[Span], prices: Any = None) -> RuntimeStats:
    from ai_auditor.cost.calculator import span_cost
    from ai_auditor.cost.pricing import PriceTable

    prices = prices or PriceTable.load()
    llm = [s for s in spans if s.is_llm]
    by_comp: dict[str, list[Span]] = defaultdict(list)
    unattributed = 0
    for s in llm:
        key = s.component or s.agent
        if key:
            by_comp[key].append(s)
        else:
            unattributed += 1
    executions = {s.trace_id for s in spans}
    comps: dict[str, ComponentStats] = {}
    total_cost, unknown_total = 0.0, 0
    for name, group in by_comp.items():
        c = ComponentStats(name, calls=len(group))
        per_exec = Counter(s.trace_id for s in group)
        c.executions = len(per_exec)
        c.calls_per_execution = len(group) / len(per_exec) if per_exec else None
        c.max_calls_in_execution = max(per_exec.values()) if per_exec else 0
        lat = [s.latency_ms for s in group if s.latency_ms is not None]
        c.latency_p50_ms, c.latency_p95_ms = _pct(lat, 0.5), _pct(lat, 0.95)
        c.retries = Rate(sum(1 for s in group if s.retry_count > 0), len(group))
        c.errors = Rate(sum(1 for s in group if s.error), len(group))
        vals = [s.validation_passed for s in group if s.validation_passed is not None]
        c.validation_failures = Rate(sum(1 for v in vals if not v), len(vals))
        c.models = dict(Counter(s.model or "?" for s in group))
        for s in group:
            u = s.usage
            if u.uncached_input is None or u.output is None:
                c.usage_unknown_calls += 1
            else:
                for k in ("uncached_input", "cache_read", "cache_write", "output", "reasoning"):
                    c.tokens[k] += getattr(u, k) or 0
            cr = span_cost(s, prices)
            if cr.usd is None:
                c.cost_unknown_calls += 1
                if cr.reason not in c.cost_unknown_reasons:
                    c.cost_unknown_reasons.append(cr.reason)
            else:
                c.cost_usd += cr.usd
                c.cost_known_calls += 1
        total_in = c.tokens["uncached_input"] + c.tokens["cache_read"] + c.tokens["cache_write"]
        c.cache_read_share = c.tokens["cache_read"] / total_in if total_in else None
        # duplicates within an execution
        seen: Counter = Counter((s.trace_id, s.prompt_hash) for s in group if s.prompt_hash)
        c.duplicate_calls = sum(n - 1 for n in seen.values() if n > 1)
        # input/output diversity and self-consistency
        ins = [s.input_hash for s in group if s.input_hash]
        outs = [s.output_hash for s in group if s.output_hash]
        c.distinct_inputs = len(set(ins)) if ins else None
        c.hashed_inputs = len(ins)
        c.distinct_outputs = len(set(outs)) if outs else None
        groups: dict[str, set] = defaultdict(set)
        sizes: Counter = Counter()
        for s in group:
            if s.input_hash and s.output_hash:
                groups[s.input_hash].add(s.output_hash)
                sizes[s.input_hash] += 1
        multi = [h for h, n in sizes.items() if n >= 2]
        if multi:
            c.self_consistency = Rate(sum(1 for h in multi if len(groups[h]) == 1), len(multi))
        short = [str(s.output_value) for s in group if s.output_value is not None and len(str(s.output_value)) <= 40]
        if short and len(short) == len([s for s in group if s.output_value is not None]):
            c.labels = dict(Counter(short).most_common(25))
        starts = sorted(s.start_ms for s in group if s.start_ms is not None)
        gaps = [(b - a) / 1000 for a, b in zip(starts, starts[1:])]
        c.median_gap_s = statistics.median(gaps) if gaps else None
        comps[name] = c
        total_cost += c.cost_usd
        unknown_total += c.cost_unknown_calls
    synthetic = any(s.synthetic for s in spans)
    notes = []
    if synthetic:
        notes.append("SYNTHETIC traces: numbers illustrate the pipeline and are not observations of a real system")
    if any(s.usage.semantics == "ambiguous" for s in spans):
        notes.append("some spans had ambiguous token semantics (input smaller than cache subtotals)")
    no_cache = sum(1 for s in llm if s.usage.semantics == "no_cache_info")
    if no_cache:
        notes.append(f"{no_cache} spans report no cache fields: their input is priced as uncached (cost is an upper bound)")
    return RuntimeStats(len(executions), len(spans), comps, synthetic, dict(Counter(s.source for s in spans)), unattributed,
                        total_cost, unknown_total, notes, spans)
