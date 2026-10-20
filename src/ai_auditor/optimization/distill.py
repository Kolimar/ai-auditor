"""Distillation of an LLM step into deterministic rules, with abstention and honest fidelity measurement.

Method: the logged (input features -> LLM output label) pairs of one component are grouped by their canonical
features (identical inputs = one group, whatever their hash or serialization) and split into train/test by group, so
no input is on both sides. A small CART decision tree (Gini) is fitted on train with one example per distinct input
(majority label), so heavily repeated inputs cannot fake support. It is scored on the held-out DISTINCT inputs:

    coverage = answered / distinct test inputs     fidelity = agrees with the LLM's majority label / answered
    (both with 95% Wilson CIs; traffic-weighted fidelity is reported for information only)

Exact repeats of seen inputs (memoization) are not a distillation question: LLM-020/LLM-027 measure them from traces.

Abstention exists because a replacement does not have to answer everything: a leaf that is not pure enough (or has too
little support) returns None and the original LLM stays as fallback for that input. This keeps fidelity high on the
covered part and makes the coverage trade-off explicit instead of hiding errors. Verdicts use the Wilson LOWER bound of
fidelity, and small samples yield "insufficient_data" rather than an optimistic claim.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ai_auditor.tracing.schema import Span
from ai_auditor.tracing.stats import Rate

MIN_EVAL = 30  # minimum test examples AND covered examples for any verdict other than insufficient_data
MAX_THRESHOLDS = 64
TEST_FRACTION = 0.3


# ---------------------------------------------------------------- examples
@dataclass
class Example:
    features: dict[str, Any]
    label: str
    group: str  # leakage-guard key: identical inputs share it


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif obj is None:
        pass  # missing
    elif isinstance(obj, (bool, int, float, str)):
        out[prefix] = obj
    else:  # lists and other structures become an opaque categorical value
        out[prefix] = json.dumps(obj, sort_keys=True, default=str)
    return out


def _canon(features: dict[str, Any]) -> str:
    return json.dumps(features, sort_keys=True, default=str)


def examples_from_spans(spans: list[Span], component: str) -> tuple[list[Example], int]:
    """Return (examples, n_skipped). Spans of the component lacking input/output, or with unparseable input, are skipped."""
    examples: list[Example] = []
    skipped = 0
    for s in spans:
        if s.component != component:
            continue
        if s.input_value is None or s.output_value is None:
            skipped += 1
            continue
        raw = s.input_value
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                skipped += 1
                continue
        if not isinstance(raw, dict):
            skipped += 1
            continue
        feats = _flatten(raw)
        examples.append(Example(feats, str(s.output_value).strip(), _canon(feats)))
    return examples, skipped


def split_examples(examples: list[Example], test_fraction: float = TEST_FRACTION) -> tuple[list[Example], list[Example]]:
    """Deterministic group-wise split: sha1(group) decides the side, so identical inputs never straddle it."""
    train, test = [], []
    for e in examples:
        bucket = int(hashlib.sha1(e.group.encode()).hexdigest()[:8], 16) % 10_000
        (test if bucket < test_fraction * 10_000 else train).append(e)
    return train, test


# ---------------------------------------------------------------- tree
@dataclass
class Leaf:
    label: str | None  # None = abstain
    support: int
    purity: float
    majority: str | None = None


@dataclass
class Split:
    feature: str
    kind: str  # "num" (x <= value) | "eq" (x == value)
    value: Any
    yes: Node
    no: Node


Node = Leaf | Split


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def goes_yes(node: Split, feats: dict[str, Any]) -> bool:
    v = feats.get(node.feature)
    if node.kind == "num":
        return _is_num(v) and v <= node.value
    return v is not None and v == node.value


def predict_tree(node: Node, feats: dict[str, Any]) -> str | None:
    while isinstance(node, Split):
        node = node.yes if goes_yes(node, feats) else node.no
    return node.label


def _gini(counts: Counter, n: int) -> float:
    return 1.0 - sum((c / n) ** 2 for c in counts.values()) if n else 0.0


def _make_leaf(rows: list[Example], min_samples_leaf: int, min_purity: float) -> Leaf:
    counts = Counter(e.label for e in rows)
    if not counts:
        return Leaf(None, 0, 0.0)
    label, top = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    purity = top / len(rows)
    ok = purity >= min_purity and len(rows) >= min_samples_leaf
    return Leaf(label if ok else None, len(rows), purity, label)


def _thresholds(values: list[float]) -> list[float]:
    distinct = sorted(set(values))
    mids = [(a + b) / 2 for a, b in zip(distinct, distinct[1:])]
    if len(mids) > MAX_THRESHOLDS:
        step = (len(mids) - 1) / (MAX_THRESHOLDS - 1)
        mids = sorted({mids[round(i * step)] for i in range(MAX_THRESHOLDS)})
    return mids


def _best_split(rows: list[Example], numeric: set[str], features: list[str], min_leaf: int) -> tuple[str, str, Any] | None:
    n = len(rows)
    total = Counter(e.label for e in rows)
    parent = _gini(total, n)
    best_gain, best = 1e-12, None
    for f in features:
        if f in numeric:
            pairs = sorted(((e.features[f], e.label) for e in rows if _is_num(e.features.get(f))), key=lambda p: p[0])
            if len(pairs) < 2:
                continue
            yes: Counter = Counter()
            i = 0
            for t in _thresholds([p[0] for p in pairs]):
                while i < len(pairs) and pairs[i][0] <= t:
                    yes[pairs[i][1]] += 1
                    i += 1
                ny = i
                if ny < min_leaf or n - ny < min_leaf:
                    continue
                no = total - yes
                gain = parent - (ny * _gini(yes, ny) + (n - ny) * _gini(no, n - ny)) / n
                if gain > best_gain:
                    best_gain, best = gain, (f, "num", t)
        else:
            by_val: dict[Any, Counter] = {}
            for e in rows:
                v = e.features.get(f)
                if v is not None:
                    by_val.setdefault(v, Counter())[e.label] += 1
            for v in sorted(by_val, key=lambda x: (type(x).__name__, str(x))):
                yes = by_val[v]
                ny = sum(yes.values())
                if ny < min_leaf or n - ny < min_leaf:
                    continue
                no = total - yes
                gain = parent - (ny * _gini(yes, ny) + (n - ny) * _gini(no, n - ny)) / n
                if gain > best_gain:
                    best_gain, best = gain, (f, "eq", v)
    return best


def fit_tree(train: list[Example], *, max_depth: int = 4, min_samples_leaf: int = 5, min_purity: float = 0.95) -> Node:
    numeric: set[str] = set()
    names = sorted({k for e in train for k in e.features})
    for f in names:
        vals = [e.features[f] for e in train if f in e.features]
        if vals and all(_is_num(v) for v in vals):
            numeric.add(f)

    def build(rows: list[Example], depth: int) -> Node:
        leaf = _make_leaf(rows, min_samples_leaf, min_purity)
        if depth >= max_depth or len({e.label for e in rows}) < 2 or len(rows) < 2 * min_samples_leaf:
            return leaf
        sp = _best_split(rows, numeric, names, min_samples_leaf)
        if sp is None:
            return leaf
        f, kind, value = sp
        probe = Split(f, kind, value, leaf, leaf)
        yes = [e for e in rows if goes_yes(probe, e.features)]
        no = [e for e in rows if not goes_yes(probe, e.features)]
        return Split(f, kind, value, build(yes, depth + 1), build(no, depth + 1))

    return build(train, 0)


# ---------------------------------------------------------------- code generation and rules
def to_python(tree: Node, func_name: str = "predict") -> str:
    """Standalone `def <func_name>(x)` returning the label or None (abstain); same semantics as predict_tree.

    The function accepts the raw input (nested dict or JSON string) and flattens it like the training data did.
    """
    lines = ["import json", "", "",
             "def _flatten(obj, prefix=''):",
             "    out = {}",
             "    if isinstance(obj, dict):",
             "        for k, v in obj.items():",
             "            out.update(_flatten(v, f'{prefix}.{k}' if prefix else str(k)))",
             "    elif obj is None:",
             "        pass",
             "    elif isinstance(obj, (bool, int, float, str)):",
             "        out[prefix] = obj",
             "    else:",
             "        out[prefix] = json.dumps(obj, sort_keys=True, default=str)",
             "    return out",
             "", "",
             f"def {func_name}(x):",
             "    if isinstance(x, str):",
             "        x = json.loads(x)",
             "    x = _flatten(x)"]

    def emit(node: Node, ind: int) -> None:
        pad = "    " * ind
        if isinstance(node, Leaf):
            lines.append(f"{pad}return {node.label!r}")
            return
        key = repr(node.feature)
        if node.kind == "num":
            cond = f"isinstance(x.get({key}), (int, float)) and not isinstance(x.get({key}), bool) and x.get({key}) <= {node.value!r}"
        else:
            cond = f"x.get({key}) is not None and x.get({key}) == {node.value!r}"
        lines.append(f"{pad}if {cond}:")
        emit(node.yes, ind + 1)
        lines.append(f"{pad}else:")
        emit(node.no, ind + 1)

    emit(tree, 1)
    return "\n".join(lines) + "\n"


def rules_from_tree(tree: Node) -> list[str]:
    rules: list[str] = []

    def walk(node: Node, conds: list[str]) -> None:
        if isinstance(node, Leaf):
            if node.label is not None:
                when = " AND ".join(conds) if conds else "ALWAYS"
                rules.append(f"IF {when} THEN {node.label!r}  (support {node.support}, purity {node.purity:.2f})")
            return
        if node.kind == "num":
            yes_c, no_c = f"{node.feature} <= {node.value!r}", f"{node.feature} > {node.value!r}"
        else:
            yes_c, no_c = f"{node.feature} == {node.value!r}", f"{node.feature} != {node.value!r}"
        walk(node.yes, conds + [yes_c])
        walk(node.no, conds + [no_c])

    walk(tree, [])
    return rules


# ---------------------------------------------------------------- evaluation
@dataclass
class CandidateResult:
    coverage: Rate
    fidelity: Rate
    decision: str
    reasons: list[str] = field(default_factory=list)


def _majority(rows: list[Example]) -> str:
    return min(Counter(e.label for e in rows).items(), key=lambda kv: (-kv[1], kv[0]))[0]


def _by_group(examples: list[Example]) -> dict[str, list[Example]]:
    out: dict[str, list[Example]] = {}
    for e in examples:
        out.setdefault(e.group, []).append(e)
    return out


def _evaluate(name: str, predict, test: list[Example], target: float, min_coverage: float) -> CandidateResult:
    """Scored on distinct inputs: replicated traffic must not inflate n or the confidence interval."""
    groups = _by_group(test)
    covered = agree = rows_cov = rows_agree = 0
    for rows in groups.values():
        p = predict(rows[0].features)  # identical features within a group
        if p is None:
            continue
        covered += 1
        agree += p == _majority(rows)
        rows_cov += len(rows)
        rows_agree += sum(e.label == p for e in rows)
    n = len(groups)
    cov, fid = Rate(covered, n), Rate(agree, covered)
    reasons: list[str] = []
    if rows_cov:
        reasons.append(f"{name}: traffic-weighted agreement on answered rows {rows_agree}/{rows_cov} (information only)")
    low_cov = cov.value is not None and cov.value < min_coverage
    if n < MIN_EVAL or (covered < MIN_EVAL and not low_cov):
        decision = "insufficient_data"
        reasons.append(f"{name}: need >= {MIN_EVAL} distinct test inputs and >= {MIN_EVAL} answered; have {n} distinct, {covered} answered")
    else:
        lo = fid.ci[0]
        bad = []
        if covered < MIN_EVAL:  # abstains so much that coverage fails regardless of fidelity
            bad.append(f"only {covered} answered distinct test inputs (< {MIN_EVAL}); fidelity not assessable")
        elif lo < target:
            bad.append(f"fidelity lower bound {lo:.3f} < target {target:.2f} (fidelity {fid})")
        if low_cov:
            bad.append(f"coverage {cov.value:.3f} < min {min_coverage:.2f} ({cov})")
        if bad:
            decision = "not_distillable"
            reasons.extend(f"{name}: {b}" for b in bad)
        else:
            decision = "distillable"
            reasons.append(f"{name}: fidelity lower bound {lo:.3f} >= {target:.2f} and coverage {cov.value:.3f} >= {min_coverage:.2f}")
    return CandidateResult(cov, fid, decision, reasons)


@dataclass
class DistillResult:
    component: str
    n_examples: int
    n_skipped: int
    n_train: int
    n_test: int
    labels: dict[str, int]
    candidates: dict[str, CandidateResult]
    best: str | None
    decision: str
    reasons: list[str]
    rules: list[str]
    python_code: str | None
    synthetic: bool
    tree: Node | None = field(default=None, repr=False)
    n_distinct: int = 0


def distill(spans: list[Span], component: str, *, target_fidelity: float = 0.95, min_coverage: float = 0.5,
            max_depth: int = 4, min_samples_leaf: int = 5, min_purity: float = 0.95) -> DistillResult:
    examples, skipped = examples_from_spans(spans, component)
    synthetic = any(s.synthetic for s in spans if s.component == component)
    train, test = split_examples(examples)
    # one training example per distinct input (majority label): repeated inputs do not count as extra support
    train_distinct = [Example(rows[0].features, _majority(rows), g) for g, rows in _by_group(train).items()]
    tree = fit_tree(train_distinct, max_depth=max_depth, min_samples_leaf=min_samples_leaf, min_purity=min_purity) if train_distinct else None
    cands: dict[str, CandidateResult] = {}
    if tree is not None:
        cands["tree"] = _evaluate("tree", lambda f: predict_tree(tree, f), test, target_fidelity, min_coverage)
    else:
        cands["tree"] = CandidateResult(Rate(0, 0), Rate(0, 0), "insufficient_data", ["tree: no training examples"])
    decision = cands["tree"].decision
    best = "tree" if decision == "distillable" else None
    reasons = list(cands["tree"].reasons)
    if synthetic:
        reasons.append("traces are synthetic: this result is illustrative only, not evidence about the real system")
    rules: list[str] = []
    code = None
    if best:
        rules, code = rules_from_tree(tree), to_python(tree)
    n_distinct = len(_by_group(examples))
    return DistillResult(component, len(examples), skipped, len(train), len(test), dict(Counter(e.label for e in examples)),
                         cands, best, decision, reasons, rules, code, synthetic, tree, n_distinct)


def render(r: DistillResult) -> str:
    out = [f"Distillation of '{r.component}': {r.decision.upper()}" + (f" (best: {r.best})" if r.best else ""),
           f"  examples {r.n_examples} ({r.n_distinct} distinct inputs, skipped {r.n_skipped}); train {r.n_train} / test {r.n_test} rows;"
           f" labels {r.labels}"]
    for name, c in r.candidates.items():
        out.append(f"  [{name}] {c.decision}: coverage {c.coverage}; fidelity {c.fidelity}")
    out.append("Reasons:")
    out.extend(f"  - {x}" for x in r.reasons)
    if r.rules:
        out.append("Rules (tree):")
        out.extend(f"  {x}" for x in r.rules)
    return "\n".join(out)
