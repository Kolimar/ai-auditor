from __future__ import annotations

import json
import random

from ai_auditor.optimization.distill import (distill, examples_from_spans, fit_tree, predict_tree, render, split_examples,
                                             to_python)
from ai_auditor.tracing.schema import Span

COMP = "router"


def _span(i: int, inp, out, *, synthetic: bool = False, ih: str | None = None) -> Span:
    return Span(trace_id=f"t{i}", span_id=f"s{i}", component=COMP, input_value=inp, output_value=out, synthetic=synthetic,
                input_hash=ih)


def _rule_label(f: dict) -> str:
    if f["order"]["total"] > 500:
        return "review"
    return "hold" if f["country"] != "ES" else "auto"


def _rule_spans(n: int = 600, seed: int = 0, synthetic: bool = False) -> list[Span]:
    rng = random.Random(seed)
    spans = []
    for i in range(n):
        f = {"order": {"total": round(rng.uniform(0, 1000), 3)}, "country": rng.choice(["ES", "FR", "DE"]), "noise": rng.random()}
        spans.append(_span(i, f if i % 2 else json.dumps(f), _rule_label(f), synthetic=synthetic))
    return spans


def test_rule_labels_are_distillable():
    r = distill(_rule_spans(), COMP)
    assert r.decision == "distillable" and r.best is not None
    assert r.candidates["tree"].fidelity.ci[0] >= 0.95
    text = " ".join(r.rules)
    assert "order.total" in text and "country" in text
    assert r.python_code and "def predict" in r.python_code
    assert "DISTILLABLE" in render(r)


def test_random_labels_not_distillable():
    rng = random.Random(0)
    spans = [_span(i, {"a": rng.random(), "b": rng.choice("xyz")}, rng.choice(["p", "q", "r"])) for i in range(600)]
    r = distill(spans, COMP)
    assert r.decision == "not_distillable" and r.best is None and r.python_code is None


def test_small_sample_is_insufficient():
    r = distill(_rule_spans(20), COMP)
    assert r.decision == "insufficient_data"


def test_generated_code_matches_tree():
    examples, skipped = examples_from_spans(_rule_spans(), COMP)
    assert skipped == 0
    train, test = split_examples(examples)
    tree = fit_tree(train)
    ns: dict = {}
    exec(to_python(tree), ns)
    assert test
    for e in test + [type(test[0])({"country": None, "order.total": "oops"}, "x", "g")]:
        assert ns["predict"](e.features) == predict_tree(tree, e.features)


def test_no_leakage_between_splits():
    rng = random.Random(0)
    spans = []
    for i in range(300):
        f = {"k": rng.randrange(40)}
        spans.append(_span(i, f, "a"))
    examples, _ = examples_from_spans(spans, COMP)
    train, test = split_examples(examples)
    assert train and test
    assert {e.group for e in train}.isdisjoint({e.group for e in test})
    # identical features with different hashes / serializations are the same input (no leak through the hash)
    hs = [_span(i, {"k": i % 25, "z": 1} if i % 2 else json.dumps({"z": 1, "k": i % 25}), "a", ih=f"h{i}") for i in range(200)]
    tr, te = split_examples(examples_from_spans(hs, COMP)[0])
    assert {e.group for e in tr}.isdisjoint({e.group for e in te})
    assert len({e.group for e in tr} | {e.group for e in te}) == 25


def test_replicated_traffic_does_not_inflate_the_sample():
    # 12 distinct inputs repeated 50 times each: 600 rows but far too few distinct inputs for any verdict
    rng = random.Random(1)
    base = [{"order": {"total": rng.uniform(0, 1000)}, "country": rng.choice(["ES", "FR"])} for _ in range(12)]
    spans = [_span(i, base[i % 12], _rule_label(base[i % 12])) for i in range(600)]
    r = distill(spans, COMP)
    assert r.n_distinct == 12 and r.decision == "insufficient_data"


def test_synthetic_flagged():
    r = distill(_rule_spans(synthetic=True), COMP)
    assert r.synthetic
    assert any("synthetic" in x.lower() for x in r.reasons)


def test_skips_unparseable():
    spans = [_span(0, "not json", "a"), _span(1, None, "a"), _span(2, {"x": 1}, "a")]
    ex, skipped = examples_from_spans(spans, COMP)
    assert len(ex) == 1 and skipped == 2
