"""Evaluate the auditor against labelled fixtures (docs/GOLDEN_SPEC.md).

Split is pre-registered (tests/golden/SPLIT.md): ``split_of(name)``. Development only looks at ``dev``;
``holdout`` is measured once at the end and reported as is.
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ai_auditor.analyzers.finding import EvidenceLevel, Finding
from ai_auditor.audit import audit
from ai_auditor.evaluation.stats import brier, ece, platt, wilson

FIXTURE_ROOTS = ("tests/golden/systems", "tests/adversarial/cases")
# Later holdouts (tests/holdout_vN/PREREGISTRATION.md): every fixture under them belongs to that split, whatever its name
HELD_OUT = {v: tuple(f"tests/{v}/{fam}" for fam in ("systems", "adversarial", "claude_code")) for v in ("holdout_v2", "holdout_v3")}
SEEN = ("dev", "holdout", "holdout_v2")  # tuning = dev + holdout v1 + holdout v2 (all already inspected)
UNSEEN = ("holdout_v3",)  # measured once, with --confirm-holdout
SPLITS = ("dev", "holdout", "tuning", "holdout_v2", "holdout_v3", "all")


def split_of(name: str) -> str:
    return "holdout" if int(hashlib.sha1(name.encode()).hexdigest(), 16) % 2 == 1 else "dev"


@dataclass
class Expectation:
    id: str
    rules: list[str] | None  # None = ANY
    component: str
    expect: str
    min_level: EvidenceLevel | None
    added_after_review: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Expectation:
        rule = d.get("rule")
        rules = None if rule in (None, "ANY") else ([rule] if isinstance(rule, str) else list(rule))
        ml = d.get("min_level")
        return cls(str(d.get("id")), rules, str(d.get("component")), d.get("expect", "present"),
                   EvidenceLevel[ml] if ml else None, bool(d.get("added_after_review")))


def _norm(c: str) -> str:
    return c.strip().lower()


def component_match(finding_comp: str, expected: str) -> bool:
    a, b = _norm(finding_comp), _norm(expected)
    return a == b or a.endswith("." + b) or b.endswith("." + a) or a.split("/")[-1] == b


def matches(f: Finding, e: Expectation) -> bool:
    if not f.actionable or not component_match(f.component, e.component):
        return False
    return e.rules is None or f.rule_id in e.rules


@dataclass
class FixtureResult:
    name: str
    kind: str
    split: str
    tp: list[str] = field(default_factory=list)
    fn: list[str] = field(default_factory=list)
    fp: list[str] = field(default_factory=list)
    tn: list[str] = field(default_factory=list)
    unlabeled: list[str] = field(default_factory=list)
    below_min_level: list[str] = field(default_factory=list)
    calibration: list[tuple[float, bool, str, str]] = field(default_factory=list)  # (confidence, correct, level, rule)
    per_rule: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    post_hoc: int = 0
    runtime_ms: float = 0.0
    error: str | None = None
    llm_justified: list[str] = field(default_factory=list)


def evaluate_fixture(path: Path, kind: str) -> FixtureResult:
    name = path.name
    r = FixtureResult(name, kind, next((v for v in HELD_OUT if v in path.parts), None) or split_of(name))
    try:
        spec = yaml.safe_load((path / "expected.yaml").read_text()) or {}
    except yaml.YAMLError as exc:
        r.error = f"invalid expected.yaml: {str(exc).splitlines()[0]} (line {getattr(getattr(exc, 'problem_mark', None), 'line', -1) + 1})"
        return r
    exps = [Expectation.from_dict(d) for d in spec.get("expectations", [])]
    t0 = time.perf_counter()
    try:
        res = audit(path, use_cache=False)
    except Exception as exc:  # noqa: BLE001 - reported per fixture
        r.error = f"{type(exc).__name__}: {exc}"
        # a crash produces no report: every expected finding is missed (absent labels are not credited as TN)
        for e in exps:
            if e.expect == "present":
                rule_key = e.rules[0] if e.rules else "ANY"
                r.fn.append(f"{e.id}:{'ANY' if e.rules is None else '/'.join(e.rules)}@{e.component} (crash)")
                r.per_rule[rule_key]["fn"] += 1
        return r
    r.runtime_ms = (time.perf_counter() - t0) * 1000
    crashes = [d.message for d in res.ir.diagnostics if d.code == "EXTRACTOR_CRASH"]
    if crashes:
        r.error = "; ".join(crashes)
    findings = [f for f in res.findings if f.actionable]
    r.llm_justified = [f.component for f in res.justified]
    used: set[str] = set()
    for e in exps:
        r.post_hoc += e.added_after_review
        hits = [f for f in findings if matches(f, e)]
        tag = f"{e.id}:{'ANY' if e.rules is None else '/'.join(e.rules)}@{e.component}"
        for f in hits:
            used.add(f.id)
        if e.expect == "present":
            good = [f for f in hits if e.min_level is None or f.level >= e.min_level]
            rule_key = good[0].rule_id if good else (e.rules[0] if e.rules else "ANY")
            if good:
                r.tp.append(tag)
                r.per_rule[rule_key]["tp"] += 1
                for f in good:
                    r.calibration.append((f.confidence, True, str(f.level), f.rule_id))
            else:
                r.fn.append(tag + (f" (found at {hits[0].level})" if hits else ""))
                if hits:
                    r.below_min_level.append(tag)
                r.per_rule[rule_key]["fn"] += 1
        elif e.expect == "absent":
            if hits:
                r.fp.append(tag + " <- " + ", ".join(f"{f.rule_id}[{f.level}]" for f in hits))
                for f in hits:
                    r.per_rule[f.rule_id]["fp"] += 1
                    r.calibration.append((f.confidence, False, str(f.level), f.rule_id))
            else:
                r.tn.append(tag)
        # optional: neither counted nor reported as unlabeled
    for f in findings:
        if f.id not in used:
            r.unlabeled.append(f"{f.rule_id}[{f.level}]@{f.component}")
            r.per_rule[f.rule_id]["unlabeled"] += 1
    return r


def discover_fixtures(repo: Path, split: str) -> list[tuple[Path, str]]:
    out = []
    roots = [(rel, None) for rel in FIXTURE_ROOTS] + [(rel, v) for v, rels in HELD_OUT.items() for rel in rels]
    for rel, fixed in roots:
        base = repo / rel
        if not base.is_dir():
            continue
        for d in sorted(p for p in base.iterdir() if p.is_dir() and (p / "expected.yaml").exists()):
            sp = fixed or split_of(d.name)
            if split == "all" or sp == split or (split == "tuning" and sp in SEEN):
                out.append((d, rel.split("/")[-1] if fixed else rel.split("/")[1]))
    return out


def aggregate(results: list[FixtureResult]) -> dict[str, Any]:
    tp = sum(len(r.tp) for r in results)
    fn = sum(len(r.fn) for r in results)
    fp = sum(len(r.fp) for r in results)  # violated `absent` labels (label level, like TP)
    fp_findings = sum(c["fp"] for r in results for c in r.per_rule.values())  # findings that violated them
    tn = sum(len(r.tn) for r in results)
    un = sum(len(r.unlabeled) for r in results)
    per_rule: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        for rule, c in r.per_rule.items():
            for k, v in c.items():
                per_rule[rule][k] += v
    cal = [(c, y) for r in results for c, y, _, _ in r.calibration]
    by_level: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for _, y, lvl, _ in r.calibration:
            by_level[lvl].append(y)
    return {
        "fixtures": len(results), "errors": {r.name: r.error for r in results if r.error},
        "tp": tp, "fn": fn, "fp": fp, "fp_findings": fp_findings, "tn": tn, "unlabeled": un,
        "precision_labeled": (tp / (tp + fp)) if tp + fp else None, "precision_labeled_ci": wilson(tp, tp + fp),
        "precision_strict": (tp / (tp + fp + un)) if tp + fp + un else None, "precision_strict_ci": wilson(tp, tp + fp + un),
        "recall": (tp / (tp + fn)) if tp + fn else None, "recall_ci": wilson(tp, tp + fn),
        "absent_respected": (tn / (tn + fp)) if tn + fp else None, "absent_respected_ci": wilson(tn, tn + fp),
        "per_rule": {k: dict(v) for k, v in sorted(per_rule.items())},
        "calibration": {"n": len(cal), "brier": brier(cal), "ece": ece(cal), "platt": platt(cal),
                        "hit_rate_by_level": {k: (sum(v) / len(v), len(v)) for k, v in sorted(by_level.items())}},
        "post_hoc_labels": sum(r.post_hoc for r in results),
        "runtime_ms": {"total": sum(r.runtime_ms for r in results),
                       "max": max((r.runtime_ms for r in results), default=0.0)},
    }


def run_benchmark(repo: Path, split: str) -> tuple[list[FixtureResult], dict[str, Any]]:
    results = [evaluate_fixture(p, kind) for p, kind in discover_fixtures(repo, split)]
    return results, aggregate(results)


def render_benchmark(results: list[FixtureResult], agg: dict[str, Any], split: str, verbose: bool = True) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.2f}"

    def ci(c):
        return f"[{c[0]:.2f}, {c[1]:.2f}]"

    lines = [f"# Benchmark — split: {split}", "",
             f"fixtures {agg['fixtures']} · TP {agg['tp']} · FN {agg['fn']} · FP {agg['fp']} (labels; {agg['fp_findings']} findings) · TN {agg['tn']} · unlabeled {agg['unlabeled']}",
             f"precision (labelled) {pct(agg['precision_labeled'])} {ci(agg['precision_labeled_ci'])} · "
             f"precision (strict) {pct(agg['precision_strict'])} {ci(agg['precision_strict_ci'])}",
             f"recall {pct(agg['recall'])} {ci(agg['recall_ci'])} · absent labels respected {pct(agg['absent_respected'])} {ci(agg['absent_respected_ci'])}",
             f"calibration: n={agg['calibration']['n']} brier={pct(agg['calibration']['brier'])} ece={pct(agg['calibration']['ece'])}"
             f" · hit rate by level {agg['calibration']['hit_rate_by_level']}",
             f"runtime: total {agg['runtime_ms']['total']:.0f} ms, max fixture {agg['runtime_ms']['max']:.0f} ms · post-hoc labels: {agg['post_hoc_labels']}",
             "", "95% Wilson intervals. Small n: per-rule numbers are indicative only.", "", "## Per rule", "",
             "| rule | tp | fn | fp | unlabeled |", "|---|---|---|---|---|"]
    for rule, c in agg["per_rule"].items():
        lines.append(f"| {rule} | {c.get('tp', 0)} | {c.get('fn', 0)} | {c.get('fp', 0)} | {c.get('unlabeled', 0)} |")
    if agg["errors"]:
        lines += ["", "## Errors", ""] + [f"- {k}: {v}" for k, v in agg["errors"].items()]
    if verbose:
        lines += ["", "## Per fixture", ""]
        for r in results:
            lines.append(f"### {r.name} ({r.kind}, {r.split}) — {r.runtime_ms:.0f} ms")
            for lab, items in (("FN", r.fn), ("FP", r.fp), ("unlabeled", r.unlabeled), ("TP", r.tp)):
                for it in items:
                    lines.append(f"- {lab}: {it}")
            lines.append("")
    return "\n".join(lines) + "\n"
