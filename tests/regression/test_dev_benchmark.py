"""Regression gate on the dev split only (the holdout is measured once, outside the test suite)."""

from __future__ import annotations

from pathlib import Path

from ai_auditor.evaluation.golden import run_benchmark, split_of

REPO = Path(__file__).resolve().parents[2]


def test_split_is_the_preregistered_one():
    assert split_of("invoice_processing") == "dev" and split_of("support_triage") == "holdout"


def test_dev_split_no_labelled_false_positives_and_recall_floor():
    results, agg = run_benchmark(REPO, "dev")
    assert not agg["errors"], agg["errors"]
    assert agg["fp"] == 0, [r.fp for r in results if r.fp]
    assert agg["recall"] >= 0.9, [r.fn for r in results if r.fn]
    assert all(r.split == "dev" for r in results)
