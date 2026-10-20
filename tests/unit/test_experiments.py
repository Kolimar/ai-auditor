"""Counterfactual experiments: decision rule, composite fallback semantics, constraints, and attachment to findings."""

from __future__ import annotations

import json
import random
import textwrap
from pathlib import Path

import pytest

from ai_auditor.analyzers.finding import EvidenceLevel
from ai_auditor.config import AuditConfig
from ai_auditor.experiments.attach import attach_experiments
from ai_auditor.experiments.runner import ExperimentSpec, load_results, run_experiment, save
from tests.conftest import fired

CANDIDATE = '''
def lane(order):
    if order["total"] > 500:
        return "EXPRESS"
    if order["country"] != "ES":
        return "HOLD"
    return "STANDARD"

def unsure_on_hold(order):
    out = lane(order)
    return None if out == "HOLD" else out

def crashes(order):
    return order["missing_key"]
'''


def truth(order: dict) -> str:
    if order["total"] > 500:
        return "EXPRESS"
    return "HOLD" if order["country"] != "ES" else "STANDARD"


def make(tmp_path: Path, n: int, *, llm_error_rate: float = 0.0, gold: bool = False, synthetic: bool = False,
         cost: float | None = 0.002, seed: int = 0, **spec_kw) -> ExperimentSpec:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        order = {"total": rng.randint(1, 1000), "country": rng.choice(["ES", "ES", "FR", "PT"])}
        t = truth(order)
        llm = t if rng.random() >= llm_error_rate else rng.choice([x for x in ("EXPRESS", "HOLD", "STANDARD") if x != t])
        row = {"trace_id": f"t{i}", "input": order, "baseline_output": llm, "baseline_latency_ms": 800.0}
        if cost is not None:
            row["baseline_cost_usd"] = cost
        if gold:
            row["expected"] = t
        if synthetic:
            row["synthetic"] = True
        rows.append(row)
    (tmp_path / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "cand.py").write_text(textwrap.dedent(CANDIDATE))
    kw = {"candidate": {"kind": "python", "target": "cand:lane"}, **spec_kw}
    return ExperimentSpec(id="exp1", component="pick_lane", dataset="data.jsonl", root=str(tmp_path), **kw)


def test_fidelity_accept_when_code_reproduces_the_llm(tmp_path):
    r = run_experiment(make(tmp_path, 600, margin=0.02))
    assert r.mode == "fidelity" and r.decision == "ACCEPT"
    assert r.quality_candidate == 1.0 and r.coverage == 1.0
    assert r.cost_delta_pct == pytest.approx(-100.0)


def test_fidelity_reject_when_agreement_is_clearly_below_target(tmp_path):
    # the "LLM" disagrees with the rules 30% of the time: the code cannot be a faithful replacement
    r = run_experiment(make(tmp_path, 600, llm_error_rate=0.3, margin=0.02))
    assert r.decision == "REJECT"


def test_inconclusive_small_sample_reports_required_n(tmp_path):
    r = run_experiment(make(tmp_path, 40, margin=0.02))
    assert r.decision == "INCONCLUSIVE"
    assert any("straddles" in x for x in r.reasons)


def test_correctness_mode_with_gold_noninferiority(tmp_path):
    # baseline LLM is 10% wrong vs gold; code is exact -> the paired CI lies above -delta
    r = run_experiment(make(tmp_path, 400, llm_error_rate=0.1, gold=True, margin=0.02))
    assert r.mode == "correctness" and r.decision == "ACCEPT"
    assert r.quality_delta > 0 and r.mcnemar_p is not None and r.mcnemar_p < 0.001


def test_abstention_falls_back_to_the_llm(tmp_path):
    # the candidate abstains on HOLD: those items keep the baseline output, cost and latency
    spec = make(tmp_path, 400, gold=True, margin=0.01, candidate={"kind": "python", "target": "cand:unsure_on_hold"})
    r = run_experiment(spec)
    assert r.decision == "ACCEPT" and 0.4 < r.coverage < 0.8
    assert r.cost_baseline_per_item * 0.2 < r.cost_candidate_per_item < r.cost_baseline_per_item


def test_correctness_reject_when_candidate_is_worse(tmp_path):
    make(tmp_path, 400, gold=True, margin=0.01)
    rows = [json.loads(x) for x in (tmp_path / "data.jsonl").read_text().splitlines()]
    for row in rows:  # the business rule changed: big orders are now held; the LLM prompt knows, the code does not
        if row["input"]["total"] > 500:
            row["expected"] = row["baseline_output"] = "HOLD"
    (tmp_path / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    spec = ExperimentSpec(id="exp2", component="pick_lane", dataset="data.jsonl", root=str(tmp_path),
                          candidate={"kind": "python", "target": "cand:lane"}, margin=0.01)
    r = run_experiment(spec)
    assert r.mode == "correctness" and r.decision == "REJECT" and r.quality_delta < -0.3


def test_crashes_count_as_reliability_failures(tmp_path):
    r = run_experiment(make(tmp_path, 200, margin=0.02, candidate={"kind": "python", "target": "cand:crashes"}))
    assert r.candidate_errors == 200
    assert r.decision != "ACCEPT"


def test_synthetic_dataset_can_never_validate(tmp_path):
    r = run_experiment(make(tmp_path, 600, synthetic=True, margin=0.02))
    assert r.decision == "INCONCLUSIVE"
    assert any("synthetic" in x for x in r.reasons)


def test_cost_unknown_is_reported_not_invented(tmp_path):
    r = run_experiment(make(tmp_path, 600, cost=None, margin=0.02))
    assert r.cost_delta_pct is None
    assert any("UNKNOWN" in x for x in r.reasons)


def test_latency_target_blocks_accept(tmp_path):
    spec = make(tmp_path, 600, margin=0.02)
    cfg = AuditConfig()
    cfg.latency_target_ms = 0.0000001
    assert run_experiment(spec, cfg).decision == "REJECT"


def test_llm_candidate_requires_explicit_live_mode(tmp_path):
    spec = make(tmp_path, 50, candidate={"kind": "llm", "model": "claude-haiku-5-5", "prompt": "{input}"})
    with pytest.raises(PermissionError):
        run_experiment(spec)


def test_spec_rejects_unknown_keys(tmp_path):
    p = tmp_path / "spec.yaml"
    p.write_text("id: x\ncomponent: c\ndataset: d.jsonl\ncandidate: {kind: python, target: m:f}\ntypo_key: 1\n")
    with pytest.raises(ValueError, match="typo_key"):
        ExperimentSpec.load(p)


def test_save_and_load_roundtrip(tmp_path):
    r = run_experiment(make(tmp_path, 300, margin=0.02))
    save(r, tmp_path / "results")
    (back,) = load_results(tmp_path / "results")
    assert back.decision == r.decision and back.quality_delta_ci == r.quality_delta_ci


def test_live_runner_enforces_budget_before_calling():
    from ai_auditor.experiments.live import BudgetExceeded, LiveRunner

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("the model must not be called when the budget cannot cover the call")

    runner = LiveRunner(budget_usd=1e-9)
    runner._clients["anthropic"] = Boom()
    with pytest.raises(BudgetExceeded):
        runner.run({"model": "claude-haiku-5-5", "prompt": "Classify: {input}", "max_tokens": 50}, "hello")


# ------------------------------------------------------------------------------------------- attachment
LANE_APP = '''
        import json
        import anthropic
        client = anthropic.Anthropic()
        RULES = """Decide the shipping lane for the order. Respond only with EXPRESS, STANDARD or HOLD.
        - If the order total is greater than 500, answer "EXPRESS".
        - If the country is not "ES", answer "HOLD".
        - Otherwise answer "STANDARD"."""

        def pick_lane(order: dict) -> str:
            r = client.messages.create(model="claude-opus-5-5", max_tokens=5, system=RULES,
                                       messages=[{"role": "user", "content": json.dumps(order)}])
            lane = r.content[0].text.strip()
            if lane == "HOLD":
                notify(order)
            return lane
        '''


def test_accept_is_the_only_path_to_proven(project, tmp_path):
    res = project({"app.py": LANE_APP})
    (f,) = fired(res, "LLM-001", "pick_lane")
    assert f.level < EvidenceLevel.PROVEN
    (tmp_path / "exp").mkdir()
    r = run_experiment(make(tmp_path / "exp", 600, margin=0.02))
    r.rule = "LLM-001"
    notes = attach_experiments(res.findings, [r])
    assert notes == [] and f.level == EvidenceLevel.PROVEN and f.impact.validated.decision == "ACCEPT"


def test_reject_discards_the_recommendation(project, tmp_path):
    res = project({"app.py": LANE_APP})
    (f,) = fired(res, "LLM-001", "pick_lane")
    (tmp_path / "exp").mkdir()
    r = run_experiment(make(tmp_path / "exp", 600, llm_error_rate=0.3, margin=0.02))
    r.finding = f.id
    attach_experiments(res.findings, [r])
    assert f.level == EvidenceLevel.DO_NOT_OPTIMIZE and f.survived_review is False and not f.actionable
    assert any(c.name == "experiment" and c.blocking for c in f.challenges)


def test_unmatched_experiment_is_reported(project, tmp_path):
    res = project({"app.py": LANE_APP})
    (tmp_path / "exp").mkdir()
    r = run_experiment(make(tmp_path / "exp", 300, margin=0.02))
    r.rule, r.component = "LLM-001", "does_not_exist"
    notes = attach_experiments(res.findings, [r])
    assert notes and "matched no finding" in notes[0]
    assert all(x.level != EvidenceLevel.PROVEN for x in res.findings)


def test_quality_target_blocks_a_change_that_breaks_it(tmp_path):
    # baseline meets 0.95; the candidate is non-inferior only under a huge margin but drops below the absolute target
    make(tmp_path, 400, gold=True)
    rows = [json.loads(x) for x in (tmp_path / "data.jsonl").read_text().splitlines()]
    for i, row in enumerate(rows):
        if i % 2 == 0 and row["input"]["total"] <= 500 and row["input"]["country"] == "ES":
            row["expected"] = row["baseline_output"] = "HOLD"  # cases the rules in code do not know about
    (tmp_path / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    spec = ExperimentSpec(id="q", component="pick_lane", dataset="data.jsonl", root=str(tmp_path),
                          candidate={"kind": "python", "target": "cand:lane"}, margin=0.2)
    r = run_experiment(spec)
    assert r.quality_baseline == 1.0 and r.quality_candidate < 0.95
    assert r.decision == "REJECT" and any("quality_target" in x for x in r.reasons)


# ------------------------------------------------------------------ regressions from the adversarial code review
def _rows(tmp_path: Path, rows: list[dict], cand: str = CANDIDATE) -> None:
    (tmp_path / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "cand.py").write_text(textwrap.dedent(cand))


def _spec(tmp_path: Path, **kw) -> ExperimentSpec:
    kw.setdefault("candidate", {"kind": "python", "target": "cand:lane"})
    return ExperimentSpec(id="r", component="c", dataset="data.jsonl", root=str(tmp_path), **kw)


def test_tiny_identical_sample_cannot_accept(tmp_path):
    # a percentile bootstrap gives CI (0, 0) here and accepted on 3 items
    rows = [{"input": {"total": 900, "country": "ES"}, "baseline_output": "EXPRESS", "expected": "EXPRESS", "baseline_cost_usd": 0.01}] * 3
    _rows(tmp_path, rows)
    assert run_experiment(_spec(tmp_path, margin=0.01)).decision == "INCONCLUSIVE"


def test_candidate_that_always_abstains_cannot_accept(tmp_path):
    make(tmp_path, 600, margin=0.02)
    (tmp_path / "cand.py").write_text("def lane(order):\n    return None\n")
    r = run_experiment(_spec(tmp_path, margin=0.02))
    assert r.coverage == 0.0 and r.decision != "ACCEPT"


def test_margin_and_alpha_are_validated(tmp_path):
    with pytest.raises(ValueError, match="1% is 0.01"):
        _spec(tmp_path, margin=1)
    with pytest.raises(ValueError):
        _spec(tmp_path, alpha=0)


def test_missing_recorded_column_is_an_error_not_a_wrong_answer(tmp_path):
    _rows(tmp_path, [{"input": {"total": 1, "country": "ES"}, "llm_output": "STANDARD", "expected": "STANDARD"}] * 50)
    with pytest.raises(ValueError, match="baseline_output"):
        run_experiment(_spec(tmp_path, margin=0.02))


def test_null_trace_ids_are_independent_rows_and_few_traces_block_accept(tmp_path):
    spec = make(tmp_path, 600, gold=True, margin=0.02)
    rows = [json.loads(x) for x in (tmp_path / "data.jsonl").read_text().splitlines()]
    for r in rows:
        r["trace_id"] = None
    _rows(tmp_path, rows)
    assert run_experiment(spec).decision == "ACCEPT"  # 600 independent rows
    for i, r in enumerate(rows):
        r["trace_id"] = f"t{i % 10}"  # 10 executions only
    _rows(tmp_path, rows)
    r = run_experiment(spec)
    assert r.decision != "ACCEPT" and any("independent traces" in x for x in r.reasons)


def test_abstention_pays_candidate_and_llm_cost(tmp_path):
    rows = [{"trace_id": f"t{i}", "input": i, "baseline_output": "A", "baseline_cost_usd": 0.010,
             "candidate_output": None if i % 2 else "A", "candidate_cost_usd": 0.008} for i in range(600)]
    _rows(tmp_path, rows)
    r = run_experiment(_spec(tmp_path, candidate={"kind": "recorded"}, margin=0.02))
    assert r.cost_candidate_per_item == pytest.approx((0.008 + 0.018) / 2)
    assert r.decision == "REJECT" and r.cost_delta_pct > 0


def test_alpha_sets_the_exact_quantile(tmp_path):
    rows = [{"trace_id": f"t{i}", "input": i, "baseline_output": "A", "baseline_cost_usd": 0.01,
             "candidate_output": "B" if i < 2 else "A", "candidate_cost_usd": 0.0} for i in range(1000)]
    _rows(tmp_path, rows)
    assert run_experiment(_spec(tmp_path, candidate={"kind": "recorded"}, margin=0.01, alpha=0.05)).decision == "ACCEPT"
    assert run_experiment(_spec(tmp_path, candidate={"kind": "recorded"}, margin=0.01, alpha=0.01)).decision == "INCONCLUSIVE"


def test_zero_crashes_on_a_small_sample_do_not_demonstrate_reliability(tmp_path):
    rows = [{"trace_id": f"t{i}", "input": {"total": 900, "country": "ES"}, "baseline_output": "EXPRESS",
             "baseline_cost_usd": 0.01} for i in range(150)]
    _rows(tmp_path, rows)
    r = run_experiment(_spec(tmp_path, margin=0.05))
    assert r.candidate_errors == 0 and r.decision == "INCONCLUSIVE"
    assert any("reliability not demonstrated" in x for x in r.reasons)


def test_recorded_candidate_with_unknown_cost_cannot_accept(tmp_path):
    rows = [{"trace_id": f"t{i}", "input": i, "baseline_output": "A", "candidate_output": "A"} for i in range(600)]
    _rows(tmp_path, rows)
    r = run_experiment(_spec(tmp_path, candidate={"kind": "recorded"}, margin=0.02))
    assert r.cost_delta_pct is None and r.decision == "INCONCLUSIVE"


def test_empty_dataset_is_an_error(tmp_path):
    _rows(tmp_path, [])
    with pytest.raises(ValueError, match="empty"):
        run_experiment(_spec(tmp_path))


def test_live_budget_uses_the_price_tier_of_the_prompt_size():
    from ai_auditor.experiments.live import BudgetExceeded, LiveRunner

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("must not be called")

    long_input = "word " * 120_000  # > 100k tokens: the over-100k tier is 5x the base input price
    # base tier estimate ≈ 0.016 USD, real tier ≈ 0.078 USD: a 0.05 budget must refuse
    runner = LiveRunner(budget_usd=0.05)
    runner._clients["anthropic"] = Boom()
    with pytest.raises(BudgetExceeded):
        runner.run({"model": "claude-haiku-5-5", "prompt": "{input}", "max_tokens": 10}, long_input)


def test_live_failed_call_is_charged_against_the_budget():
    from ai_auditor.experiments.live import LiveRunner

    class Failing:
        class messages:  # noqa: N801 - mimics the SDK attribute
            @staticmethod
            def create(**kw):
                raise RuntimeError("provider 500")

    runner = LiveRunner(budget_usd=1.0)
    runner._clients["anthropic"] = Failing()
    out, _, cost, err = runner.run({"model": "claude-haiku-5-5", "prompt": "Classify: {input}", "max_tokens": 50}, "hello")
    assert out == "__error__" and err == 1 and runner.spent_usd > 0
