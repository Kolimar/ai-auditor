"""Runtime tracing: usage normalization, ingestion, cost, stats, and the static+runtime pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_auditor.cost.calculator import span_cost, tokens_cost
from ai_auditor.cost.pricing import PriceTable
from ai_auditor.reporting.render import render_markdown
from ai_auditor.tracing.ingest import read_spans, usage_from_native, usage_from_otel
from ai_auditor.tracing.schema import Span, Usage
from ai_auditor.tracing.stats import compute_stats
from tests.conftest import fired

# indented like the snippets below so that textwrap.dedent strips one common margin
ANTHROPIC = "        import anthropic\n        client = anthropic.Anthropic()\n"
OPENAI = "        import json\n        from openai import OpenAI\n        client = OpenAI()\n"

MODEL = "claude-sonnet-5-5"


def _llm014_files() -> dict[str, str]:
    guide = " ".join(f"Rule {i}: when the ticket mentions product line {i}, route it using the standard matrix and cite the clause." for i in range(220))
    return {"app.py": ANTHROPIC + f'''
        GUIDE = """{guide}"""

        def handle(ticket: str) -> str:
            r = client.messages.create(model="claude-sonnet-5-5", max_tokens=200, system=GUIDE,
                                       messages=[{{"role": "user", "content": ticket}}])
            return r.content[0].text

        def main(tickets):
            for t in tickets:
                handle(t)
        '''}


LLM008_FILES = {"app.py": OPENAI + '''
        def tags(text: str) -> list:
            for attempt in range(4):
                r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Return a JSON list of tags for: " + text}])
                try:
                    return json.loads(r.choices[0].message.content)
                except json.JSONDecodeError:
                    continue
            return []
        '''}


def mk(component="handle", trace="t1", sid="s", model=MODEL, usage=None, **kw) -> Span:
    return Span(trace_id=trace, span_id=sid, component=component, model=model,
                usage=usage or Usage(uncached_input=1000, cache_read=0, cache_write=0, output=100, semantics="disjoint"), **kw)


def traces(component, n, usage, synthetic=False, per_exec=2, gap_ms=1000.0, **kw) -> list[Span]:
    return [mk(component, trace=f"t{i // per_exec}", sid=f"s{i}", usage=usage, synthetic=synthetic,
               start_ms=i * gap_ms, latency_ms=100.0, **kw) for i in range(n)]


CACHED = Usage(uncached_input=100, cache_read=900, cache_write=0, output=10, semantics="disjoint")
UNCACHED = Usage(uncached_input=1000, cache_read=0, cache_write=0, output=10, semantics="disjoint")


# --------------------------------------------------------------------------- 1. usage_from_otel
def test_otel_input_is_total_including_cache():
    u = usage_from_otel({"gen_ai.usage.input_tokens": 1000, "gen_ai.usage.cache_read.input_tokens": 600,
                         "gen_ai.usage.cache_creation_input_tokens": 100, "gen_ai.usage.output_tokens": 50})
    assert (u.uncached_input, u.cache_read, u.cache_write, u.output) == (300, 600, 100, 50)
    assert u.semantics == "otel_total"
    assert u.total_input == 1000


def test_otel_declared_excluding_cache():
    u = usage_from_otel({"gen_ai.usage.input_tokens": 1000, "gen_ai.usage.cache_read.input_tokens": 600,
                         "gen_ai.usage.cache_creation_input_tokens": 100, "auditor.usage.input_excludes_cache": True})
    assert u.uncached_input == 1000
    assert u.semantics == "anthropic_native"
    assert u.total_input == 1700


def test_otel_ambiguous_when_input_smaller_than_cache():
    u = usage_from_otel({"gen_ai.usage.input_tokens": 100, "gen_ai.usage.cache_read.input_tokens": 500})
    assert u.uncached_input == 100
    assert u.semantics == "ambiguous"
    assert u.notes


def test_otel_missing_input_is_never_inferred():
    u = usage_from_otel({"gen_ai.usage.cache_read.input_tokens": 500, "gen_ai.usage.output_tokens": 5})
    assert u.uncached_input is None
    assert u.total_input is None


# --------------------------------------------------------------------------- 2. usage_from_native
def test_native_anthropic_is_disjoint():
    u = usage_from_native("anthropic", {"input_tokens": 300, "cache_read_input_tokens": 600,
                                        "cache_creation_input_tokens": 100, "output_tokens": 50})
    assert (u.uncached_input, u.cache_read, u.cache_write, u.output) == (300, 600, 100, 50)
    assert u.semantics == "anthropic_native"
    assert u.total_input == 1000


def test_native_openai_chat_subtracts_cached():
    u = usage_from_native("openai", {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 600},
                                     "completion_tokens": 50, "completion_tokens_details": {"reasoning_tokens": 20}})
    assert (u.uncached_input, u.cache_read, u.cache_write, u.output, u.reasoning) == (400, 600, 0, 50, 20)
    assert u.semantics == "openai_native"
    assert u.total_input == 1000


def test_native_openai_responses_without_provider_hint():
    u = usage_from_native(None, {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 600},
                                 "output_tokens": 50, "output_tokens_details": {"reasoning_tokens": 20}})
    assert (u.uncached_input, u.cache_read, u.output, u.reasoning) == (400, 600, 50, 20)
    assert u.semantics == "openai_native"


def test_native_gemini_output_includes_thoughts():
    u = usage_from_native("google", {"promptTokenCount": 1000, "cachedContentTokenCount": 600,
                                     "candidatesTokenCount": 50, "thoughtsTokenCount": 20})
    assert (u.uncached_input, u.cache_read, u.output, u.reasoning) == (400, 600, 70, 20)
    assert u.semantics == "google_native"
    assert u.total_input == 1000


# --------------------------------------------------------------------------- 3. read_spans
def test_read_spans_jsonl(tmp_path: Path):
    rec = {"trace_id": "t1", "span_id": "a", "component": "classify", "model": MODEL, "latency_ms": 120.5,
           "usage": {"uncached_input": 10, "cache_read": 5, "cache_write": 2, "output": 7}}
    f = tmp_path / "spans.jsonl"
    f.write_text(json.dumps(rec) + "\n\n")
    [s] = read_spans(f)
    assert (s.trace_id, s.span_id, s.component, s.model, s.latency_ms, s.source) == ("t1", "a", "classify", MODEL, 120.5, "jsonl")
    assert (s.usage.uncached_input, s.usage.cache_read, s.usage.cache_write, s.usage.output) == (10, 5, 2, 7)
    assert s.usage.semantics == "disjoint"


def test_read_spans_otlp_json(tmp_path: Path):
    def attr(k, **v):
        return {"key": k, "value": v}

    doc = {"resourceSpans": [{"scopeSpans": [{"spans": [{
        "traceId": "tr1", "spanId": "sp1", "startTimeUnixNano": "1000000000", "endTimeUnixNano": "1250000000",
        "attributes": [attr("auditor.component", stringValue="summarize"), attr("gen_ai.request.model", stringValue=MODEL),
                       attr("gen_ai.usage.input_tokens", intValue="1000"),
                       attr("gen_ai.usage.cache_read.input_tokens", intValue="600"),
                       attr("gen_ai.usage.output_tokens", intValue="50")]}]}]}]}
    f = tmp_path / "trace.json"
    f.write_text(json.dumps(doc))
    [s] = read_spans(f)
    assert (s.trace_id, s.span_id, s.component, s.model, s.source) == ("tr1", "sp1", "summarize", MODEL, "otlp_json")
    assert s.latency_ms == 250.0
    assert s.start_ms == 1000.0
    assert (s.usage.uncached_input, s.usage.cache_read, s.usage.output, s.usage.semantics) == (400, 600, 50, "otel_total")


# --------------------------------------------------------------------------- 4. cost
@pytest.fixture(scope="module")
def prices() -> PriceTable:
    return PriceTable.load()


def test_span_cost_from_price_table(prices):
    p = prices.get(MODEL)
    s = mk(usage=Usage(uncached_input=1000, cache_read=2000, cache_write=500, output=300, semantics="disjoint"))
    r = span_cost(s, prices)
    assert r.status == "computed"
    assert r.usd == pytest.approx((1000 * p.input + 2000 * p.cache_read + 500 * p.cache_write + 300 * p.output) / 1e6)
    assert r.usd == pytest.approx(0.00645)


def test_tokens_cost_matches_span_cost(prices):
    p = prices.get(MODEL)
    assert tokens_cost(prices, MODEL, 1000, 300, 2000, 500) == pytest.approx(
        (1000 * p.input + 2000 * p.cache_read + 500 * p.cache_write + 300 * p.output) / 1e6)
    assert tokens_cost(prices, "no-such-model", 1, 1) is None


def test_span_cost_unknown_model(prices):
    r = span_cost(mk(model="acme-9000"), prices)
    assert r.usd is None and r.status == "unknown"


def test_span_cost_unknown_when_usage_missing(prices):
    r = span_cost(mk(usage=Usage(uncached_input=None, output=5)), prices)
    assert r.usd is None and r.status == "unknown"
    r = span_cost(mk(usage=Usage(uncached_input=5, output=None)), prices)
    assert r.usd is None and r.status == "unknown"


def test_span_cost_provided_wins(prices):
    r = span_cost(mk(model="acme-9000", cost_usd=0.5), prices)
    assert (r.usd, r.status) == (0.5, "provided")


def test_span_cost_batch_uses_batch_prices(prices):
    p = prices.get(MODEL)
    assert p.batch_input is not None and p.batch_output is not None
    u = Usage(uncached_input=1000, output=300, semantics="disjoint")
    r = span_cost(mk(usage=u, batch=True), prices)
    assert r.usd == pytest.approx((1000 * p.batch_input + 300 * p.batch_output) / 1e6)
    assert r.usd < span_cost(mk(usage=u), prices).usd
    assert tokens_cost(prices, MODEL, 1000, 300, batch=True) == pytest.approx(r.usd)


# --------------------------------------------------------------------------- 5. compute_stats
def test_compute_stats_duplicates_retries_unknown_cost(prices):
    u = Usage(uncached_input=1000, output=100, semantics="disjoint")
    spans = [
        mk("a", "e1", "1", usage=u, prompt_hash="h1"),
        mk("a", "e1", "2", usage=u, prompt_hash="h1"),
        mk("a", "e1", "3", usage=u, prompt_hash="h2", retry_count=1),
        mk("a", "e2", "4", usage=u, prompt_hash="h1"),  # same hash in another execution: not a duplicate
        mk("a", "e2", "5", usage=u, model="acme-9000", prompt_hash="h3"),
    ]
    rt = compute_stats(spans, prices)
    a = rt.components["a"]
    p = prices.get(MODEL)
    one = (1000 * p.input + 100 * p.output) / 1e6
    assert (rt.n_executions, rt.n_spans) == (2, 5)
    assert (a.calls, a.executions, a.max_calls_in_execution) == (5, 2, 3)
    assert a.duplicate_calls == 1
    assert (a.retries.k, a.retries.n) == (1, 5)
    assert a.cost_unknown_calls == 1 and a.cost_known_calls == 4
    assert a.cost_usd == pytest.approx(4 * one)
    assert rt.cost_unknown_calls == 1
    assert rt.total_cost_usd == pytest.approx(4 * one)
    assert a.cost_per_execution is None
    assert rt.synthetic is False


def test_compute_stats_cost_per_execution_when_all_known(prices):
    u = Usage(uncached_input=1000, output=100, semantics="disjoint")
    rt = compute_stats([mk("a", "e1", "1", usage=u), mk("a", "e2", "2", usage=u)], prices)
    p = prices.get(MODEL)
    assert rt.components["a"].cost_per_execution == pytest.approx((1000 * p.input + 100 * p.output) / 1e6)


def test_compute_stats_synthetic_flag(prices):
    rt = compute_stats([mk("a", synthetic=True), mk("a", sid="2")], prices)
    assert rt.synthetic is True
    assert any("SYNTHETIC" in n for n in rt.notes)


# --------------------------------------------------------------------------- 6. pipeline
def _levels(res):
    return sorted((f.rule_id, f.component, int(f.level), f.confidence) for f in res.findings)


def test_synthetic_traces_never_change_levels(project, prices):
    base = project(_llm014_files())
    rt = compute_stats(traces("handle", 40, UNCACHED, synthetic=True), prices)
    res = project(_llm014_files(), runtime=rt)
    assert _levels(res) == _levels(base)
    assert "SYNTHETIC" in render_markdown(res)


def test_real_traces_with_cache_contradict_llm014(project, prices):
    assert fired(project(_llm014_files()), "LLM-014", "handle")
    rt = compute_stats(traces("handle", 40, CACHED), prices)
    assert rt.components["handle"].cache_read_share == pytest.approx(0.9)
    res = project(_llm014_files(), runtime=rt)
    assert fired(res, "LLM-014", "handle") == []
    assert any(f.rule_id == "LLM-014" and f.component == "handle" for f in res.discarded)


def test_small_real_sample_does_not_change_llm014(project, prices):
    base = project(_llm014_files())
    rt = compute_stats(traces("handle", 29, CACHED), prices)
    res = project(_llm014_files(), runtime=rt)
    lvl = lambda r: [int(f.level) for f in r.findings if f.rule_id == "LLM-014" and f.component == "handle"]  # noqa: E731
    assert lvl(res) == lvl(base) and lvl(base)
    assert fired(res, "LLM-014", "handle")


# --------------------------------------------------------------------------- 7. LLM-027
def test_027_fires_on_duplicate_prompts(project, prices):
    spans = [mk("handle", trace=f"t{i // 2}", sid=f"s{i}", usage=UNCACHED, prompt_hash="same", start_ms=i * 1000.0) for i in range(40)]
    res = project(_llm014_files(), runtime=compute_stats(spans, prices))
    [f] = fired(res, "LLM-027", "handle")
    assert f.impact.observed.stats["duplicate_calls"] == 20
    assert f.impact.estimated is not None


def test_027_estimate_is_share_of_component_cost(project, prices):
    spans = [mk("handle", trace=f"t{i // 2}", sid=f"s{i}", usage=UNCACHED, prompt_hash="same", start_ms=i * 1000.0) for i in range(40)]
    res = project(_llm014_files(), runtime=compute_stats(spans, prices))
    [f] = fired(res, "LLM-027", "handle")
    assert f.impact.estimated.cost_saving_per_execution == pytest.approx(0.5 * f.impact.observed.cost_per_execution)


def test_027_silent_without_duplicates(project, prices):
    spans = [mk("handle", trace=f"t{i // 2}", sid=f"s{i}", usage=UNCACHED, prompt_hash=f"h{i}") for i in range(40)]
    res = project(_llm014_files(), runtime=compute_stats(spans, prices))
    assert not fired(res, "LLM-027")


def test_027_skipped_without_runtime(project):
    assert not fired(project(_llm014_files()), "LLM-027")


# --------------------------------------------------------------------------- 8. estimates
def test_008_estimate_zero_when_no_retries_observed(project, prices):
    u = Usage(uncached_input=100, output=20, semantics="disjoint")
    spans = [mk("tags", trace=f"t{i}", sid=f"s{i}", model="gpt-5.5", usage=u) for i in range(30)]
    res = project(LLM008_FILES, runtime=compute_stats(spans, prices))
    [f] = [f for f in res.findings if f.rule_id == "LLM-008" and f.component == "tags"]
    assert f.impact.estimated.method == "no retried calls observed"
    assert f.impact.estimated.cost_saving_per_execution == 0.0


# --------------------------------------------------------------------------- regressions from the adversarial code review
BATCH_JOB = {"job.py": OPENAI + '''
        import csv

        def summarize_review(text: str) -> str:
            r = client.chat.completions.create(model="gpt-5.5", messages=[{"role": "user", "content": "Summarize this review in one sentence: " + text}])
            return r.choices[0].message.content

        def main(path):
            with open(path) as f:
                for row in csv.DictReader(f):
                    print(summarize_review(row["text"]))

        if __name__ == "__main__":
            main("reviews.csv")
        '''}


def test_own_disjoint_usage_wins_over_provider_hint():
    u = usage_from_native("anthropic", {"uncached_input": 100, "cache_read": 20, "cache_write": 0, "output": 5})
    assert (u.uncached_input, u.cache_read, u.output, u.semantics) == (100, 20, 5, "disjoint")


def test_repricing_is_per_call_not_on_summed_tokens(prices):
    from ai_auditor.tracing.attach import _reprice

    calls = [mk(model="claude-haiku-5-5", sid=f"s{i}", usage=Usage(uncached_input=500, cache_read=0, cache_write=0, output=20,
                                                                    semantics="disjoint")) for i in range(1000)]
    per_call = tokens_cost(prices, "claude-haiku-5-5", 500, 20, batch=True)
    assert _reprice(calls, prices, None, batch=True) == pytest.approx(1000 * per_call)
    # pricing the 500k summed tokens as ONE call would hit the >100k tier: the old, wrong behaviour
    assert tokens_cost(prices, "claude-haiku-5-5", 500_000, 20_000, batch=True) > 1000 * per_call * 2


def test_no_repricing_saving_without_token_usage(project, prices):
    spans = [mk("summarize_review", trace=f"t{i}", sid=f"s{i}", model="gpt-5.5", cost_usd=0.01,
                usage=Usage(semantics="unknown")) for i in range(40)]
    res = project(BATCH_JOB, runtime=compute_stats(spans, prices))
    (f,) = fired(res, "LLM-024", "summarize_review")
    assert f.impact.estimated.cost_saving_per_execution is None
    assert "no token usage" in " ".join(f.impact.estimated.assumptions)


def test_llm020_saving_needs_input_hashes_on_every_call(prices):
    from ai_auditor.tracing.stats import compute_stats as cs

    spans = [mk(sid=f"s{i}", trace=f"t{i}", input_hash=f"h{i}" if i < 100 else None) for i in range(1000)]
    stats = cs(spans, prices).get("handle")
    assert stats.hashed_inputs == 100 and stats.distinct_inputs == 100 and stats.calls == 1000
