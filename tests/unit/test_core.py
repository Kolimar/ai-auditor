"""Profile, determinism score, statistics, findings invariants, pricing, report, CLI."""

from __future__ import annotations

import json
import math
import sys

import pytest

from ai_auditor.analyzers.engine import combine, level_from_confidence
from ai_auditor.analyzers.finding import EvidenceLevel, Finding, Impact, Severity, Validated
from ai_auditor.cost.pricing import PriceTable, normalize_model_id
from ai_auditor.evaluation.stats import bootstrap_ci, brier, ece, holm, mcnemar_exact, wilson, zero_events_upper
from ai_auditor.parser.python.resolve import name_hint


# ------------------------------------------------------------------------------------------ statistics
def test_wilson_known_values():
    lo, hi = wilson(8, 10)
    assert math.isclose(lo, 0.4902, abs_tol=1e-3) and math.isclose(hi, 0.9433, abs_tol=1e-3)
    assert wilson(0, 0) == (0.0, 1.0)


def test_rule_of_three():
    assert math.isclose(zero_events_upper(100), 0.0295, abs_tol=1e-3)  # ≈ 3/n


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert math.isclose(mcnemar_exact(1, 9), 0.0215, abs_tol=1e-3)


def test_bootstrap_and_holm():
    lo, hi = bootstrap_ci([0.0] * 50 + [1.0] * 50, n_boot=2000)
    assert lo < 0.5 < hi
    assert holm({"a": 0.001, "b": 0.04, "c": 0.5}) == {"a": True, "b": False, "c": False}


def test_calibration_metrics():
    pairs = [(0.9, True), (0.8, True), (0.3, False), (0.2, False)]
    assert brier(pairs) < 0.05 and ece(pairs) < 0.25


# ------------------------------------------------------------------------------------------ evidence model
def test_confidence_combination_is_monotone():
    assert combine([0.5]) < combine([0.5, 0.3])
    assert combine([0.5, -0.5]) == pytest.approx(0.25)
    assert level_from_confidence(0.95, EvidenceLevel.LIKELY) == EvidenceLevel.LIKELY
    assert level_from_confidence(0.1, EvidenceLevel.HIGH_CONFIDENCE) is None


def _finding(level, validated=None):
    return Finding(rule_id="LLM-001", title="t", category="c", severity=Severity.LOW, level=level, confidence=0.9,
                   component="x", component_id="x", location=None, evidence=[], reasoning="", current_behavior="",
                   recommended_change="", impact=Impact(validated=validated))


def test_proven_requires_accepted_experiment():
    assert _finding(EvidenceLevel.PROVEN).level == EvidenceLevel.HIGH_CONFIDENCE
    rejected = Validated("e1", "REJECT", -0.1, (-0.2, 0.0), -50.0, None, 200)
    assert _finding(EvidenceLevel.PROVEN, rejected).level == EvidenceLevel.HIGH_CONFIDENCE
    accepted = Validated("e2", "ACCEPT", 0.0, (-0.005, 0.01), -60.0, None, 400)
    assert _finding(EvidenceLevel.PROVEN, accepted).level == EvidenceLevel.PROVEN


# ------------------------------------------------------------------------------------------ names, pricing
@pytest.mark.parametrize("name,expected", [
    ("payload", True), ("raw_csv", True), ("date_text", True), ("order_json", True),
    ("review_text", False), ("email_body", False), ("message", False), ("x", None),
])
def test_name_hint(name, expected):
    assert name_hint(name) is expected


def test_pricing_table_and_normalization():
    table = PriceTable.load()
    assert normalize_model_id("anthropic/claude-sonnet-5-5-20260101") == "claude-sonnet-5-5"
    p = table.get("claude-sonnet-5-5")
    assert p is not None and p.input and p.output and p.retrieved_at
    assert table.get("some-unknown-model") is None


# ------------------------------------------------------------------------------------------ report & CLI
def test_report_keeps_impact_categories_separate(project):
    from ai_auditor.reporting.render import render_json, render_markdown

    res = project({"app.py": '''
        from openai import OpenAI
        client = OpenAI()

        def tips():
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "List five tips for writing clear commit messages."}])
            return r.choices[0].message.content
        '''})
    md = render_markdown(res)
    assert "Observed runtime: not available" in md and "Validated: not available" in md and "Estimated saving: not available" in md
    data = json.loads(render_json(res))
    assert data["summary"]["llm_calls_made_by_auditor"] == 0
    f = next(f for f in data["findings"] if f["rule_id"] == "LLM-020")
    assert f["impact"]["observed"] is None and f["impact"]["estimated"] is None and f["impact"]["validated"] is None


def test_cli_analyze_and_rules(tmp_path, capsys):
    from ai_auditor.cli.main import main

    (tmp_path / "app.py").write_text("x = 1\n")
    assert main(["analyze", str(tmp_path), "--no-cache", "-f", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["llm_steps"] == 0
    assert main(["rules"]) == 0
    assert "LLM-026" in capsys.readouterr().out


def test_cli_refuses_holdout_without_confirmation(capsys):
    from ai_auditor.cli.main import main

    assert main(["benchmark", "--split", "holdout_v3"]) == 1


# ------------------------------------------------------------------------------------------ cost of the auditor itself
def test_auditor_imports_no_llm_sdk(project):
    for mod in ("openai", "anthropic", "litellm"):
        sys.modules.pop(mod, None)
    project({"app.py": "import openai\nclient = openai.OpenAI()\n"})
    assert not {"openai", "anthropic", "litellm"} & set(sys.modules)


def test_cache_is_written_outside_the_audited_project(tmp_path, monkeypatch):
    from ai_auditor.audit import audit

    proj, cache = tmp_path / "proj", tmp_path / "cache"
    proj.mkdir()
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "agents" / "a.md").write_text("---\nname: a\ndescription: d\n---\nSummarize the diff.\n")
    monkeypatch.setenv("AI_AUDITOR_CACHE", str(cache))
    first = audit(proj, use_cache=True)
    second = audit(proj, use_cache=True)
    assert sorted(p.name for p in proj.rglob("*")) == [".claude", "a.md", "agents"]  # nothing written into the project
    assert any(cache.rglob("*.json"))
    assert first.extract_stats["cache_misses"] >= 1 and second.extract_stats["cache_hits"] >= 1


def test_marketplace_catalogs_under_claude_home_are_not_audited(tmp_path):
    from ai_auditor.parser.discovery import discover

    home = tmp_path / ".claude"
    skill = "---\nname: s\ndescription: d\n---\nRun the tests.\n"
    for rel in ("plugins/marketplaces/m/plugins/p/skills/s/SKILL.md", "plugins/cache/m/p/1.0/skills/s/SKILL.md", "skills/own/SKILL.md"):
        (home / rel).parent.mkdir(parents=True)
        (home / rel).write_text(skill)
    assert [f.rel for f in discover(home, [])] == ["plugins/cache/m/p/1.0/skills/s/SKILL.md", "skills/own/SKILL.md"]
    # auditing a marketplace checkout directly still works
    assert len(discover(home / "plugins" / "marketplaces" / "m", [])) == 1
