"""End-to-end through the CLI: static audit -> synthetic traces -> experiment -> PROVEN, and distillation to code."""

from __future__ import annotations

import json
import random
import textwrap
from pathlib import Path

from ai_auditor.cli.main import main

APP = '''
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

CANDIDATE = '''
def lane(order):
    if order["total"] > 500:
        return "EXPRESS"
    return "HOLD" if order["country"] != "ES" else "STANDARD"
'''


def truth(o: dict) -> str:
    return "EXPRESS" if o["total"] > 500 else ("HOLD" if o["country"] != "ES" else "STANDARD")


def orders(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{"total": rng.randint(1, 1000), "country": rng.choice(["ES", "ES", "FR", "PT"])} for _ in range(n)]


def _findings(path: Path) -> list[dict]:
    return json.loads(path.read_text())["findings"]


def test_static_then_synthetic_then_experiment(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text(APP)

    static = tmp_path / "static.json"
    assert main(["analyze", str(proj), "--no-cache", "-f", "json", "-o", str(static)]) == 0
    before = {f["id"]: f["level"] for f in _findings(static)}
    lane_ids = [i for i, f in ((f["id"], f) for f in _findings(static)) if f["rule_id"] == "LLM-001" and f["component"] == "pick_lane"]
    assert lane_ids and before[lane_ids[0]] in ("HIGH_CONFIDENCE", "LIKELY")

    # synthetic traces: labelled everywhere, never change a level
    traces = tmp_path / "synthetic.jsonl"
    assert main(["trace", "synth", str(proj), "-o", str(traces), "--executions", "40"]) == 0
    assert all(json.loads(x)["synthetic"] for x in traces.read_text().splitlines())
    md = tmp_path / "with_traces.md"
    assert main(["analyze", str(proj), "--no-cache", "--traces", str(traces), "-f", "markdown", "-o", str(md)]) == 0
    text = md.read_text()
    assert "## Runtime data" in text and "SYNTHETIC traces" in text
    js = tmp_path / "with_traces.json"
    main(["analyze", str(proj), "--no-cache", "--traces", str(traces), "-f", "json", "-o", str(js)])
    assert {f["id"]: f["level"] for f in _findings(js)} == before

    # offline experiment on recorded LLM outputs -> ACCEPT -> PROVEN
    exp = tmp_path / "exp"
    exp.mkdir()
    (exp / "cand.py").write_text(textwrap.dedent(CANDIDATE))
    rows = [{"trace_id": f"t{i}", "input": o, "baseline_output": truth(o), "baseline_cost_usd": 0.004, "baseline_latency_ms": 900}
            for i, o in enumerate(orders(600))]
    (exp / "data.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (exp / "spec.yaml").write_text(
        f"id: lane-as-code\ncomponent: pick_lane\nfinding: {lane_ids[0]}\ndataset: data.jsonl\n"
        "candidate: {kind: python, target: 'cand:lane'}\nmargin: 0.02\n")
    results = tmp_path / "results"
    out = tmp_path / "exp.txt"
    assert main(["experiment", "run", str(exp / "spec.yaml"), "--save", str(results), "-o", str(out)]) == 0
    assert "DECISION: ACCEPT" in out.read_text()

    final = tmp_path / "final.json"
    assert main(["analyze", str(proj), "--no-cache", "--experiments", str(results), "-f", "json", "-o", str(final)]) == 0
    after = {f["id"]: f for f in _findings(final)}
    f = after[lane_ids[0]]
    assert f["level"] == "PROVEN" and f["impact"]["validated"]["decision"] == "ACCEPT"
    assert sum(1 for x in after.values() if x["level"] == "PROVEN") == 1


def test_live_experiment_refused_without_flag(tmp_path, capsys):
    (tmp_path / "data.jsonl").write_text(json.dumps({"input": "x", "baseline_output": "y"}) + "\n")
    (tmp_path / "spec.yaml").write_text("id: e\ncomponent: c\ndataset: data.jsonl\n"
                                        "candidate: {kind: llm, model: claude-haiku-5-5, prompt: '{input}'}\n")
    assert main(["experiment", "run", str(tmp_path / "spec.yaml")]) == 1
    assert "--allow-live" in capsys.readouterr().err
    assert main(["experiment", "run", str(tmp_path / "spec.yaml"), "--allow-live"]) == 1  # no budget


def test_distill_emits_code_equivalent_on_logged_decisions(tmp_path):
    rows = [{"trace_id": f"t{i}", "component": "pick_lane", "model": "claude-opus-5-5",
             "usage": {"input_tokens": 120, "output_tokens": 2}, "input_value": json.dumps(o), "output_value": truth(o)}
            for i, o in enumerate(orders(800, seed=7))]
    traces = tmp_path / "real.jsonl"
    traces.write_text("".join(json.dumps(r) + "\n" for r in rows))
    code = tmp_path / "lane_rules.py"
    report = tmp_path / "distill.txt"
    assert main(["distill", str(traces), "--component", "pick_lane", "--emit-python", str(code), "-o", str(report)]) == 0
    assert "DISTILLABLE" in report.read_text()
    ns: dict = {}
    exec(code.read_text(), ns)  # noqa: S102 - generated by the test itself
    fresh = orders(300, seed=99)
    answered = [(o, ns["predict"](json.dumps(o))) for o in fresh]
    covered = [(o, p) for o, p in answered if p is not None]
    assert len(covered) >= 0.5 * len(fresh)
    assert sum(p == truth(o) for o, p in covered) / len(covered) >= 0.95


def test_distill_refuses_to_emit_code_for_noise(tmp_path):
    rng = random.Random(3)
    rows = [{"trace_id": f"t{i}", "component": "pick_lane", "input_value": json.dumps(o),
             "output_value": rng.choice(["EXPRESS", "HOLD", "STANDARD"])} for i, o in enumerate(orders(600, seed=5))]
    traces = tmp_path / "noise.jsonl"
    traces.write_text("".join(json.dumps(r) + "\n" for r in rows))
    code = tmp_path / "noise.py"
    assert main(["distill", str(traces), "--component", "pick_lane", "--emit-python", str(code), "-o", str(tmp_path / "r.txt")]) == 1
    assert not code.exists()


def test_real_traces_with_values_add_distillation_evidence(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text(APP)
    rows = [{"trace_id": f"t{i}", "component": "pick_lane", "model": "claude-opus-5-5",
             "usage": {"input_tokens": 150, "output_tokens": 2}, "input_value": json.dumps(o), "output_value": truth(o)}
            for i, o in enumerate(orders(500, seed=11))]
    traces = tmp_path / "real.jsonl"
    traces.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = tmp_path / "a.json"
    assert main(["analyze", str(proj), "--no-cache", "--traces", str(traces), "-f", "json", "-o", str(out)]) == 0
    (f,) = [f for f in _findings(out) if f["rule_id"] == "LLM-001" and f["component"] == "pick_lane"]
    assert any(e["kind"] == "distillation" and e["weight"] > 0 for e in f["evidence"])
    assert f["impact"]["estimated"]["method"].startswith("component cost × share of inputs")
    assert f["level"] == "HIGH_CONFIDENCE"  # real evidence lifts the cap, but PROVEN still needs an experiment


def test_cli_usage_errors_exit_2(tmp_path, capsys):
    from ai_auditor.cli.main import main

    assert main(["analyze", str(tmp_path / "missing")]) == 2
    (tmp_path / ".ai-auditor.yaml").write_text("notebooks: maybe\n")
    assert main(["analyze", str(tmp_path), "--no-cache"]) == 2
    assert "notebooks must be" in capsys.readouterr().err
