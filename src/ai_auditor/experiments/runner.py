"""Counterfactual experiments: does the proposed change keep quality while lowering cost?

Objective (docs/ARCHITECTURE.md §Evaluación): minimize cost subject to quality ≥ target, reliability ≥ target,
latency ≤ target. The decision rule is fixed *before* looking at results (margin δ comes from the spec or config):

* fidelity mode  (reference = baseline LLM output, no gold):  agreement rate of the composite system with the LLM.
      ACCEPT  if Wilson lower bound ≥ 1 − δ;  REJECT if Wilson upper bound < 1 − δ;  else INCONCLUSIVE.
* correctness mode (reference = gold labels): paired difference in accuracy (candidate − baseline), Newcombe's paired
  score interval (and, when several rows share a trace, also a trace-cluster bootstrap; the wider bound wins).
      ACCEPT  if the lower bound > −δ (non-inferiority);  REJECT if the upper bound < −δ;  else INCONCLUSIVE.
      McNemar's exact test is reported alongside; a change may not break a quality_target the baseline meets.
  In both modes ACCEPT also requires: the candidate answers ≥ min_coverage of the items itself, its crash rate upper
  bound ≤ 1 − reliability_target (zero crashes on a small sample does not demonstrate reliability), a cost not higher
  than baseline (unknown cost blocks ACCEPT except for code candidates), and latency within latency_target_ms.
  δ ∈ (0, 0.2] and alpha ∈ (0, 0.5) are validated: "margin: 1" meaning 1% would otherwise accept anything.

"Composite system" = fast path + fallback: when the candidate abstains (returns None) the baseline output is used and
both the candidate's and the LLM's cost and latency are paid for that item, as the deployed cascade would.
Recorded columns that are absent raise an error (an absent key is neither an abstention nor a wrong answer).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from ai_auditor.config import AuditConfig
from ai_auditor.config import UsageError
from ai_auditor.evaluation.stats import bootstrap_ci, mcnemar_exact, newcombe_paired, wilson, z_for, zero_events_upper

Z_POWER80 = 0.8416212335729143


@dataclass
class ExperimentSpec:
    id: str
    component: str
    dataset: str
    candidate: dict[str, Any]
    baseline: dict[str, Any] = field(default_factory=lambda: {"kind": "recorded"})
    metric: str = "exact_match"
    reference: str = "auto"  # expected | baseline | auto (expected when the dataset has it)
    margin: float | None = None
    alpha: float = 0.05
    finding: str | None = None
    rule: str | None = None
    hypothesis: str = ""
    min_coverage: float = 0.5  # share of items the candidate must answer itself for an ACCEPT
    root: str = "."

    def __post_init__(self) -> None:
        if self.margin is not None and not 0 < self.margin <= 0.2:
            raise UsageError(f"margin δ must be an absolute share in (0, 0.2], got {self.margin} (1% is 0.01)")
        if not 0 < self.alpha < 0.5:
            raise UsageError(f"alpha must be in (0, 0.5), got {self.alpha}")
        if not 0 <= self.min_coverage <= 1:
            raise UsageError(f"min_coverage must be in [0, 1], got {self.min_coverage}")

    @classmethod
    def load(cls, path: Path) -> ExperimentSpec:
        data = yaml.safe_load(path.read_text()) or {}
        known = set(cls.__dataclass_fields__)
        unknown = set(data) - known
        if unknown:
            raise UsageError(f"unknown experiment keys: {sorted(unknown)}")
        data.setdefault("root", str(path.parent))
        return cls(**data)


@dataclass
class ExperimentResult:
    id: str
    component: str
    finding: str | None
    rule: str | None
    mode: str
    n: int
    decision: str
    reasons: list[str]
    quality_baseline: float | None
    quality_candidate: float | None
    quality_delta: float | None
    quality_delta_ci: tuple[float, float] | None
    margin: float
    mcnemar_p: float | None
    coverage: float  # share of items the candidate answered (did not abstain)
    candidate_errors: int
    cost_baseline_per_item: float | None
    cost_candidate_per_item: float | None
    cost_delta_pct: float | None
    latency_baseline_ms: float | None
    latency_candidate_ms: float | None
    latency_delta_ms: float | None
    required_n: int | None
    live_calls: int = 0
    live_cost_usd: float = 0.0

    def to_validated(self):
        from ai_auditor.analyzers.finding import Validated

        return Validated(self.id, self.decision, self.quality_delta, self.quality_delta_ci, self.cost_delta_pct,
                         self.latency_delta_ms, self.n)


# ----------------------------------------------------------------------------------------------- metrics

def _norm(x: Any) -> str:
    return " ".join(str(x).strip().lower().split()) if x is not None else ""


def _json_equal(a: Any, b: Any) -> bool:
    def load(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v
    return load(a) == load(b)


METRICS: dict[str, Callable[[Any, Any], bool]] = {
    "exact_match": lambda a, b: a == b or (str(a).strip() == str(b).strip() if a is not None and b is not None else False),
    "normalized_match": lambda a, b: _norm(a) == _norm(b),
    "json_equal": _json_equal,
}


def _metric(name: str, root: Path) -> Callable[[Any, Any], bool]:
    if name in METRICS:
        return METRICS[name]
    if name.startswith("numeric_close"):
        tol = float(name.split(":", 1)[1]) if ":" in name else 1e-6
        return lambda a, b: a is not None and b is not None and abs(float(a) - float(b)) <= tol
    if name.startswith("python:"):
        return _load_callable(name.split(":", 1)[1], root)
    raise UsageError(f"unknown metric {name}")


def _load_callable(target: str, root: Path) -> Callable:
    """`module:function`. A module file next to the spec is loaded from that path (never a stale cached module of the
    same name from another experiment); otherwise it is imported normally."""
    mod_name, _, fn = target.partition(":")
    path = root / (mod_name.replace(".", "/") + ".py")
    if path.is_file():
        unique = f"_ai_auditor_exp_{abs(hash(str(path.resolve())))}"
        spec = importlib.util.spec_from_file_location(unique, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique] = module
        spec.loader.exec_module(module)
        return getattr(module, fn)
    return getattr(importlib.import_module(mod_name), fn)


# ----------------------------------------------------------------------------------------------- run

def _outputs(side: dict[str, Any], rows: list[dict], key: str, root: Path, live: Any) -> tuple[list[Any], list[float | None], list[float | None], int]:
    """Returns outputs, latency_ms, cost_usd per row, and number of crashes. None output = abstain."""
    kind = side.get("kind", "recorded")
    outs, lats, costs, errors = [], [], [], 0
    if kind == "recorded":
        col = side.get("column", f"{key}_output")
        missing = sum(1 for r in rows if col not in r)
        if missing:  # an absent key is not an abstention (explicit null) nor a wrong answer: refuse to guess
            raise UsageError(f"{missing}/{len(rows)} rows lack the recorded column '{col}' for the {key}")
        for r in rows:
            outs.append(r[col])
            lats.append(r.get(f"{key}_latency_ms"))
            costs.append(r.get(f"{key}_cost_usd"))
        return outs, lats, costs, 0
    if kind == "python":
        fn = _load_callable(side["target"], root)
        for r in rows:
            t0 = time.perf_counter()
            try:
                out = fn(r["input"])
            except Exception:  # noqa: BLE001 - a crash is a reliability failure, counted
                out, errors = "__error__", errors + 1
            lats.append((time.perf_counter() - t0) * 1000)
            outs.append(out)
            costs.append(0.0)
        return outs, lats, costs, errors
    if kind == "llm":
        if live is None:
            raise PermissionError("candidate/baseline kind 'llm' calls a model: run with --allow-live and a --budget-usd")
        for r in rows:
            out, lat, cost, err = live.run(side, r["input"])
            outs.append(out)
            lats.append(lat)
            costs.append(cost)
            errors += err
        return outs, lats, costs, errors
    raise UsageError(f"unknown kind {kind}")


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals and len(vals) == len(xs) else None


def run_experiment(spec: ExperimentSpec, config: AuditConfig | None = None, live: Any = None) -> ExperimentResult:
    config = config or AuditConfig()
    root = Path(spec.root)
    path = (root / spec.dataset) if not Path(spec.dataset).is_absolute() else Path(spec.dataset)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise UsageError(f"empty dataset: {path}")
    margin = spec.margin if spec.margin is not None else config.non_inferiority_margin
    if not 0 < margin <= 0.2:
        raise UsageError(f"non_inferiority_margin must be in (0, 0.2], got {margin}")
    metric = _metric(spec.metric, root)

    b_out, b_lat, b_cost, _ = _outputs(spec.baseline, rows, "baseline", root, live)
    c_raw, c_lat, c_cost, c_err = _outputs(spec.candidate, rows, "candidate", root, live)
    # composite: abstention falls back to the baseline (output, latency and cost of the LLM call)
    comp_out, comp_lat, comp_cost, answered = [], [], [], 0
    for i, c in enumerate(c_raw):
        if c is None:  # the candidate ran, abstained, and the LLM was called: both costs and latencies are paid
            comp_out.append(b_out[i])
            comp_lat.append(None if b_lat[i] is None or c_lat[i] is None else b_lat[i] + c_lat[i])
            comp_cost.append(None if b_cost[i] is None or c_cost[i] is None else b_cost[i] + c_cost[i])
        else:
            answered += 1
            comp_out.append(None if c == "__error__" else c)
            comp_lat.append(c_lat[i])
            comp_cost.append(c_cost[i])
    n = len(rows)
    has_gold = all("expected" in r for r in rows)
    mode = "correctness" if (spec.reference == "expected" or (spec.reference == "auto" and has_gold)) else "fidelity"
    reasons: list[str] = []
    q_b = q_c = delta = None
    ci = None
    p_mc = None
    required = None
    alpha = spec.alpha
    z = z_for(alpha)
    # independence unit: the trace (rows of one execution are correlated); rows without trace_id are their own unit
    unit = [str(r["trace_id"]) if r.get("trace_id") is not None else f"row-{i}" for i, r in enumerate(rows)]
    n_units = len(set(unit))
    clustered = n_units < n
    if clustered:
        reasons.append(f"{n} items from {n_units} traces: intervals use the number of traces as the effective sample size")

    if mode == "fidelity":
        agree = [bool(metric(comp_out[i], b_out[i])) for i in range(n)]
        k = sum(agree)
        # clustered: worst case of full intra-trace correlation (effective n = traces), conservative
        k_eff, n_eff = (round(k / n * n_units), n_units) if clustered else (k, n)
        lo, hi = wilson(k_eff, n_eff, z)
        q_b, q_c = 1.0, k / n if n else None
        delta = (q_c - 1.0) if q_c is not None else None
        ci = (lo - 1.0, hi - 1.0)
        threshold = 1 - margin
        reasons.append(f"quality_target {config.quality_target} not checkable without gold labels: fidelity to the LLM is the criterion")
        if lo >= threshold:
            decision = "ACCEPT"
            reasons.append(f"agreement with the LLM {k}/{n}, Wilson lower bound {lo:.4f} ≥ {threshold:.4f} (1 − δ)")
        elif hi < threshold:
            decision = "REJECT"
            reasons.append(f"agreement {k}/{n}, Wilson upper bound {hi:.4f} < {threshold:.4f}")
        else:
            decision = "INCONCLUSIVE"
            p = k / n if n else 0
            if p > threshold:
                required = math.ceil(z * z * p * (1 - p) / (p - threshold) ** 2) if p < 1 else math.ceil(math.log(0.05) / math.log(threshold))
            reasons.append(f"agreement {k}/{n}: interval [{lo:.4f}, {hi:.4f}] straddles {threshold:.4f}"
                           + (f"; ≈{required} items needed if the rate holds" if required else ""))
    else:
        gold = [r["expected"] for r in rows]
        b_ok = [bool(metric(b_out[i], gold[i])) for i in range(n)]
        c_ok = [bool(metric(comp_out[i], gold[i])) for i in range(n)]
        q_b, q_c = sum(b_ok) / n, sum(c_ok) / n
        delta = q_c - q_b
        both = sum(1 for b, c in zip(b_ok, c_ok) if b and c)
        bdisc = sum(1 for b, c in zip(b_ok, c_ok) if b and not c)
        cdisc = sum(1 for b, c in zip(b_ok, c_ok) if c and not b)
        neither = n - both - bdisc - cdisc
        # Newcombe paired score interval: valid at small n and with zero discordant pairs (a percentile bootstrap
        # collapses to width 0 there and would ACCEPT on 3 items)
        ci = newcombe_paired(both, cdisc, bdisc, neither, z)
        if clustered:
            if n_units < 30:
                reasons.append(f"only {n_units} independent traces (< 30): no ACCEPT possible")
            clusters: dict[str, list[float]] = {}
            for u, b, c in zip(unit, b_ok, c_ok):
                clusters.setdefault(u, []).append(float(c) - float(b))
            boot = bootstrap_ci(list(clusters.values()), alpha=alpha)
            ci = (min(ci[0], boot[0]), max(ci[1], boot[1]))  # the more conservative of both
        p_mc = mcnemar_exact(bdisc, cdisc)
        if ci[0] > -margin and not (clustered and n_units < 30):
            decision = "ACCEPT"
            reasons.append(f"accuracy {q_c:.4f} vs {q_b:.4f}; paired CI of the difference [{ci[0]:+.4f}, {ci[1]:+.4f}] lies above −δ = {-margin:+.4f}")
        elif ci[1] < -margin:
            decision = "REJECT"
            reasons.append(f"accuracy drops: CI [{ci[0]:+.4f}, {ci[1]:+.4f}] entirely below −δ = {-margin:+.4f}")
        else:
            decision = "INCONCLUSIVE"
            p_disc = (bdisc + cdisc) / n if n else 0
            eff = margin + min(delta, 0) if delta is not None else margin
            if p_disc and eff > 0:
                required = math.ceil((z + Z_POWER80) ** 2 * p_disc / eff ** 2)
            reasons.append(f"CI [{ci[0]:+.4f}, {ci[1]:+.4f}] includes −δ = {-margin:+.4f}" + (f"; ≈{required} items for 80% power" if required else ""))
        reasons.append(f"McNemar exact p = {p_mc:.4g} (discordant: baseline-only {bdisc}, candidate-only {cdisc})")
        # absolute constraint: the change must not break a quality_target the current system meets
        c_lo, c_hi = wilson(sum(c_ok), n, z)
        target = config.quality_target
        if q_b >= target and c_hi < target:
            if decision == "ACCEPT":
                decision = "REJECT"
            reasons.append(f"candidate accuracy {q_c:.4f} (CI upper {c_hi:.4f}) falls below quality_target {target} that the baseline meets")
        else:
            met = "met" if c_lo >= target else ("not met by the baseline either" if q_b < target else "not demonstrated (CI includes it)")
            reasons.append(f"quality_target {target}: {met} (candidate accuracy CI [{c_lo:.4f}, {c_hi:.4f}])")

    # coverage, reliability, cost, latency constraints (only ever block an ACCEPT)
    coverage = answered / n
    if decision == "ACCEPT" and coverage < spec.min_coverage:
        decision = "INCONCLUSIVE"
        reasons.append(f"the candidate answered only {answered}/{n} items ({coverage:.1%} < min_coverage {spec.min_coverage:.0%}):"
                       " the LLM would still do most of the work, so this does not show the step can drop the LLM")
    err_upper = zero_events_upper(n, alpha) if c_err == 0 else wilson(c_err, n, z)[1]
    if c_err:
        reasons.append(f"candidate crashed on {c_err}/{n} items")
    if decision == "ACCEPT" and err_upper > 1 - config.reliability_target:
        decision = "INCONCLUSIVE"
        reasons.append(f"crash-rate upper bound {err_upper:.4f} ({c_err}/{n}) exceeds 1 − reliability_target "
                       f"({1 - config.reliability_target:.4f}): reliability not demonstrated")
    cb, cc = _mean(b_cost), _mean(comp_cost)
    cost_delta = ((cc - cb) / cb * 100) if cb not in (None, 0) and cc is not None else None
    if decision == "ACCEPT" and cost_delta is not None and cost_delta > 0:
        decision = "REJECT"
        reasons.append(f"composite cost is higher than baseline ({cost_delta:+.1f}%)")
    if cost_delta is None:
        reasons.append("cost delta UNKNOWN (cost per item not recorded for every row)")
        if decision == "ACCEPT" and spec.candidate.get("kind", "recorded") != "python":
            decision = "INCONCLUSIVE"
            reasons.append("a recorded/LLM candidate with unknown cost cannot be shown to be cheaper")
    lb, lc = _mean(b_lat), _mean(comp_lat)
    lat_delta = (lc - lb) if lb is not None and lc is not None else None
    if decision == "ACCEPT" and config.latency_target_ms is not None and lc is not None and lc > config.latency_target_ms:
        decision = "REJECT"
        reasons.append(f"mean latency {lc:.0f} ms exceeds target {config.latency_target_ms:.0f} ms")
    if any(r.get("synthetic") for r in rows):
        decision = "INCONCLUSIVE"
        reasons.append("dataset is synthetic: an experiment on synthetic data cannot validate a change")
    return ExperimentResult(
        spec.id, spec.component, spec.finding, spec.rule, mode, n, decision, reasons, q_b, q_c, delta, ci, margin, p_mc,
        coverage, c_err, cb, cc, cost_delta, lb, lc, lat_delta, required,
        live_calls=getattr(live, "calls", 0), live_cost_usd=getattr(live, "spent_usd", 0.0),
    )


def save(result: ExperimentResult, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result.id}.json"
    path.write_text(json.dumps(asdict(result), indent=2, default=str))
    return path


def load_results(directory: Path) -> list[ExperimentResult]:
    out = []
    for p in sorted(directory.glob("*.json")):
        d = json.loads(p.read_text())
        if d.get("quality_delta_ci") is not None:
            d["quality_delta_ci"] = tuple(d["quality_delta_ci"])
        out.append(ExperimentResult(**d))
    return out


def render(r: ExperimentResult) -> str:
    def f(x, fmt="{:.4f}"):
        return "n/a" if x is None else fmt.format(x)

    lines = [f"experiment {r.id} — component {r.component} ({r.mode} mode, n={r.n}, δ={r.margin})",
             f"DECISION: {r.decision}",
             f"quality: baseline {f(r.quality_baseline)} · candidate {f(r.quality_candidate)} · Δ {f(r.quality_delta, '{:+.4f}')}"
             + (f" CI [{r.quality_delta_ci[0]:+.4f}, {r.quality_delta_ci[1]:+.4f}]" if r.quality_delta_ci else ""),
             f"coverage (candidate answered) {r.coverage:.1%} · crashes {r.candidate_errors}",
             f"cost/item: baseline {f(r.cost_baseline_per_item, '${:.6f}')} · composite {f(r.cost_candidate_per_item, '${:.6f}')} · Δ {f(r.cost_delta_pct, '{:+.1f}%')}",
             f"latency/item: baseline {f(r.latency_baseline_ms, '{:.1f} ms')} · composite {f(r.latency_candidate_ms, '{:.1f} ms')}"]
    if r.live_calls:
        lines.append(f"live model calls {r.live_calls}, spent ${r.live_cost_usd:.4f}")
    lines += [f"- {x}" for x in r.reasons]
    return "\n".join(lines) + "\n"
