"""Join runtime statistics to static findings.

For each finding whose component was observed in traces:

* ``impact.observed``  — what the component cost and did (never mixed with static numbers);
* ``impact.estimated`` — observed × an explicit, rule-specific saving model, with every assumption written out;
* runtime evidence     — added to the finding's evidence list; with real (non-synthetic) traces and a large enough
  sample it lifts the static cap (class C: LIKELY -> HIGH_CONFIDENCE). Synthetic traces never change levels.

When real traces carry input/output values (``Tracer(store_values=True)``), code-replacement findings are also
checked by distillation (optimization/distill.py): if a small tree reproduces the logged LLM decisions on held-out
inputs, that is evidence for the finding and bounds the estimated saving by the share of inputs it answers.

PROVEN is not reachable here: it needs an accepted experiment (experiments/).
"""

from __future__ import annotations

from ai_auditor.analyzers.engine import AnalysisContext, combine, level_from_confidence
from ai_auditor.analyzers.finding import Estimate, Evidence, EvidenceLevel, Finding, ObservedRuntime
from ai_auditor.cost.calculator import tokens_cost
from ai_auditor.ir.model import LLMStep
from ai_auditor.tracing.stats import ComponentStats, RuntimeStats

MIN_CALLS_FOR_EVIDENCE = 30
CODE_REPLACEMENT = {"LLM-001", "LLM-009", "LLM-010", "LLM-011", "LLM-026", "LLM-002", "LLM-006", "LLM-012"}
SMALLER_MODEL = {"LLM-003", "LLM-018"}
DISTILL_RULES = {"LLM-001", "LLM-009", "LLM-011", "LLM-026", "LLM-019"}
CACHE_TTL_S = 300  # Anthropic default ephemeral TTL (5 min); OpenAI automatic caching is best-effort


def component_stats(runtime: RuntimeStats, step: LLMStep) -> ComponentStats | None:
    return runtime.get(step.name) or runtime.get(step.attrs.get("qualname"))


NOT_COMPUTABLE = {
    "LLM-004": "the saving depends on which fields are removed; trace the prompt tokens before and after the change",
    "LLM-016": "the saving depends on the new top_k; tokens per retrieved chunk are not in the traces",
    "LLM-023": "tool-schema tokens are not separated from the prompt in the traces",
    "LLM-021": "the bounded loop length is a design choice; compare calls per execution after the change",
    "LLM-025": "parallelisation reduces latency, not cost",
    "LLM-015": "the saving equals the retrieval calls removed; retrieval spans are not priced",
    "LLM-017": "the saving depends on how many tool round-trips the script replaces",
}


def coverage(ctx: AnalysisContext, runtime: RuntimeStats) -> dict[str, list[str]]:
    names = {s.name.lower() for s in ctx.ir.llm_steps()}
    return {
        "observed_steps": sorted(s.name for s in ctx.ir.llm_steps() if component_stats(runtime, s)),
        "unobserved_steps": sorted(s.name for s in ctx.ir.llm_steps() if not component_stats(runtime, s)),
        "unmatched_components": sorted(c for c in runtime.components if c.lower() not in names),
    }


def _distillation(runtime: RuntimeStats, cs: ComponentStats, f: Finding, cache: dict):
    if runtime.synthetic or f.rule_id not in DISTILL_RULES:
        return None
    if cs.component not in cache:
        from ai_auditor.optimization.distill import distill  # noqa: PLC0415

        r = distill(runtime.spans, cs.component)
        cache[cs.component] = r if r.decision != "insufficient_data" else None
    return cache[cs.component]


def attach_runtime(ctx: AnalysisContext, findings: list[Finding], runtime: RuntimeStats) -> None:
    n = max(runtime.n_executions, 1)
    distilled: dict = {}
    for f in findings:
        step = ctx.ir.nodes.get(f.component_id or "")
        if not isinstance(step, LLMStep):
            continue
        cs = component_stats(runtime, step)
        if cs is None:
            continue
        cost_exec = None if cs.cost_unknown_calls else cs.cost_usd / n
        tok_exec = (sum(cs.tokens[k] for k in ("uncached_input", "cache_read", "cache_write", "output")) / n) if not cs.usage_unknown_calls else None
        f.impact.observed = ObservedRuntime(
            n_executions=runtime.n_executions, calls_per_execution=round(cs.calls / n, 3), cost_per_execution=cost_exec,
            cost_unknown_calls=cs.cost_unknown_calls, tokens_per_execution=tok_exec,
            stats={"calls": cs.calls, "executions_with_component": cs.executions, "retries": str(cs.retries),
                   "errors": str(cs.errors), "validation_failures": str(cs.validation_failures),
                   "cache_read_share": cs.cache_read_share, "latency_p50_ms": cs.latency_p50_ms,
                   "latency_p95_ms": cs.latency_p95_ms, "duplicate_calls": cs.duplicate_calls,
                   "max_calls_in_execution": cs.max_calls_in_execution, "models": cs.models,
                   "synthetic": runtime.synthetic, "cost_unknown_reasons": cs.cost_unknown_reasons},
        )
        d = _distillation(runtime, cs, f, distilled)
        if f.impact.estimated is None:  # runtime-only rules (LLM-027) compute their own saving model
            f.impact.estimated = _estimate(ctx, f, step, cs, n, d)
        _runtime_evidence(f, cs, runtime, d)


def runtime_spans(ctx: AnalysisContext, cs: ComponentStats) -> list:
    return [sp for sp in ctx.runtime.spans if sp.is_llm and (sp.component or sp.agent) == cs.component]


def _reprice(spans: list, prices, model: str | None, batch: bool = False) -> float | None:
    """Total cost of the observed calls repriced one by one (price tiers depend on each call's prompt size);
    ``model=None`` keeps each call's own model. None if any call cannot be priced."""
    total = 0.0
    for sp in spans:
        u = sp.usage
        if u.uncached_input is None or u.output is None:
            return None
        c = tokens_cost(prices, model or sp.model, u.uncached_input, u.output, u.cache_read, u.cache_write, batch=batch)
        if c is None:
            return None
        total += c
    return total


def _estimate(ctx: AnalysisContext, f: Finding, step: LLMStep, cs: ComponentStats, n: int, distilled=None) -> Estimate | None:
    if cs.cost_unknown_calls:
        return Estimate(None, None, "not computable", [f"{cs.cost_unknown_calls} calls with UNKNOWN cost: {cs.cost_unknown_reasons[:2]}"])
    comp_cost = cs.cost_usd / n
    prices = ctx.catalog.prices
    model = next(iter(cs.models), None)
    t = cs.tokens
    if distilled is not None and distilled.decision == "distillable" and f.rule_id in CODE_REPLACEMENT:
        cov = distilled.candidates[distilled.best].coverage
        return Estimate(comp_cost * cov.value, cov.value, "component cost × share of inputs the distilled rules answer",
                        [f"distilled {distilled.best} answers {cov} of held-out logged inputs; the LLM stays as fallback for the rest",
                         f"fidelity to the LLM on answered inputs: {distilled.candidates[distilled.best].fidelity}",
                         "assumes the production input mix matches the traces"])
    if f.rule_id in CODE_REPLACEMENT or f.rule_id == "LLM-020" and step.variables() == []:
        return Estimate(comp_cost, 1.0, "observed component cost per execution (all of it)",
                        ["replacement (code/lookup) cost ≈ 0", "upper bound: with an LLM fallback firing at rate r the saving is ×(1−r)",
                         "quality impact not measured (see validation plan)"])
    if f.rule_id == "LLM-020" and cs.distinct_inputs:
        if cs.hashed_inputs < cs.calls:
            return Estimate(None, None, "not computable from traces",
                            [f"only {cs.hashed_inputs}/{cs.calls} calls carry an input hash; repeats cannot be counted"])
        frac = max(0.0, 1 - cs.distinct_inputs / cs.hashed_inputs)
        return Estimate(comp_cost * frac, frac, "calls for already-seen inputs",
                        [f"{cs.distinct_inputs} distinct inputs over {cs.calls} calls", "one call kept per distinct value"])
    if cs.usage_unknown_calls and f.rule_id in SMALLER_MODEL | {"LLM-013", "LLM-024", "LLM-014", "LLM-005", "LLM-007"}:
        return Estimate(None, None, "not computable from traces",
                        [f"{cs.usage_unknown_calls}/{cs.calls} calls have no token usage (cost reported directly): repricing needs tokens"])
    if f.rule_id in SMALLER_MODEL | {"LLM-013"}:
        info = ctx.profile(step).model
        alts = ctx.catalog.cheaper_same_provider(info) if info else []
        if not alts:
            return Estimate(None, None, "not computable", ["no cheaper model with a known price in the catalog"])
        target = alts[0]
        new = _reprice(runtime_spans(ctx, cs), prices, target.id)
        if new is None:
            return Estimate(None, None, "not computable", [f"price unknown for {target.id}"])
        saving = comp_cost - new / n
        return Estimate(saving, saving / comp_cost if comp_cost else None, f"same observed tokens repriced at {target.id}",
                        ["same token counts (tokenizers differ between models)", "no escalations to the current model (a cascade adds them back)",
                         "quality not measured: run the experiment before acting"])
    if f.rule_id == "LLM-024":
        new = _reprice(runtime_spans(ctx, cs), prices, None, batch=True)
        if new is None:
            return Estimate(None, None, "not computable", ["batch price unknown"])
        saving = comp_cost - new / n
        return Estimate(saving, saving / comp_cost if comp_cost else None, "observed tokens repriced at batch rates",
                        ["all calls of this component go through the batch API", "results within the provider's batch window are acceptable"])
    if f.rule_id in ("LLM-014", "LLM-005"):
        sp = f.impact.static_potential
        prefix = (sp.context_tokens_removed_per_invocation if sp else None) or 0
        price = prices.get(model)
        if not prefix or price is None or price.cache_read is None or price.input is None:
            return Estimate(None, None, "not computable", ["prefix size or cache prices unknown"])
        if (cs.cache_read_share or 0) >= 0.3:
            return Estimate(0.0, 0.0, "prefix already served from cache", [f"cache_read share {cs.cache_read_share:.2f}"])
        hit = 0.0
        if cs.median_gap_s is not None:
            hit = 1.0 if cs.median_gap_s < CACHE_TTL_S else 0.0
        writes_extra = (price.cache_write - price.input) if price.cache_write is not None else 0.0
        per_call = prefix * (hit * (price.input - price.cache_read) - (1 - hit) * writes_extra) / 1e6
        saving = per_call * cs.calls / n
        return Estimate(saving, saving / comp_cost if comp_cost else None, "static prefix × calls × (input − cache-read price)",
                        [f"cache hit rate assumed {hit:.0%} from median gap between calls ({cs.median_gap_s}s vs TTL {CACHE_TTL_S}s)",
                         "prefix tokens estimated statically (±25%)"])
    if f.rule_id == "LLM-007" and t["reasoning"]:
        price = prices.get(model)
        if price and price.output:
            saving = t["reasoning"] * price.output / 1e6 / n
            return Estimate(saving, saving / comp_cost if comp_cost else None, "observed reasoning tokens × output price",
                            ["all reasoning removed (upper bound)", "accuracy impact not measured"])
    if f.rule_id in ("LLM-008", "LLM-022"):
        if not cs.retries.k:
            return Estimate(0.0, 0.0, "no retried calls observed",
                            [f"retried calls: {cs.retries}",
                             "the change is a robustness improvement here, not a cost saving"])
        frac = cs.retries.k / cs.calls
        return Estimate(comp_cost * frac, frac, "cost of retried calls", ["structured outputs remove format-triggered retries"])
    if f.rule_id == "LLM-007":
        return Estimate(0.0, 0.0, "no reasoning tokens observed", ["reasoning tokens were 0 or not reported by the provider"])
    return Estimate(None, None, "not computable from traces", [NOT_COMPUTABLE.get(f.rule_id, "measure the change in an experiment")])


def _runtime_evidence(f: Finding, cs: ComponentStats, runtime: RuntimeStats, distilled=None) -> None:
    if runtime.synthetic:
        f.evidence.append(Evidence("trace_stat", "runtime data is synthetic: not used as evidence", weight=0.0))
        return
    added: list[Evidence] = []
    if cs.calls < MIN_CALLS_FOR_EVIDENCE:
        f.evidence.append(Evidence("trace_stat", f"only {cs.calls} observed calls (< {MIN_CALLS_FOR_EVIDENCE}): not used as evidence", weight=0.0))
        return
    r = f.rule_id
    if r == "LLM-002" and cs.validation_failures.n:
        if cs.validation_failures.k == 0:
            added.append(Evidence("trace_stat", f"validator never rejected: {cs.validation_failures}", weight=0.4))
        else:
            added.append(Evidence("trace_stat", f"validator rejected outputs: {cs.validation_failures}", weight=-0.7))
    if r in ("LLM-008", "LLM-022"):
        if cs.retries.k:
            added.append(Evidence("trace_stat", f"retries observed: {cs.retries}", weight=0.3))
        else:
            added.append(Evidence("trace_stat", f"no retries observed: {cs.retries}", weight=-0.3))
    if r == "LLM-014":
        if (cs.cache_read_share or 0) >= 0.3:
            added.append(Evidence("trace_stat", f"prefix already read from cache (share {cs.cache_read_share:.2f})", weight=-0.85))
        elif cs.median_gap_s is not None and cs.median_gap_s < CACHE_TTL_S:
            added.append(Evidence("trace_stat", f"no cache reads although calls are {cs.median_gap_s:.0f}s apart (TTL {CACHE_TTL_S}s)", weight=0.35))
    if r in ("LLM-001", "LLM-009", "LLM-010", "LLM-011", "LLM-026", "LLM-019") and cs.self_consistency and cs.self_consistency.n >= 10:
        sc = cs.self_consistency
        if sc.value >= 0.95:
            added.append(Evidence("trace_stat", f"model output is stable on repeated inputs: {sc}", weight=0.2))
        elif sc.value < 0.8:
            added.append(Evidence("trace_stat", f"model output varies on repeated inputs: {sc}", weight=-0.3))
    if r == "LLM-020" and cs.distinct_inputs is not None and cs.hashed_inputs == cs.calls and cs.distinct_inputs <= max(20, cs.calls // 10):
        added.append(Evidence("trace_stat", f"{cs.distinct_inputs} distinct inputs over {cs.calls} calls", weight=0.35))
    if distilled is not None:
        if distilled.decision == "distillable":
            c = distilled.candidates[distilled.best]
            added.append(Evidence("distillation", f"logged LLM decisions are reproduced by a distilled {distilled.best} on held-out "
                                  f"inputs: fidelity {c.fidelity}, coverage {c.coverage}", weight=0.45))
        else:
            c = distilled.candidates["tree"]
            added.append(Evidence("distillation", f"no small decision tree over the logged input fields reproduces the LLM "
                                  f"(fidelity {c.fidelity}, coverage {c.coverage}); the decision may depend on information "
                                  "outside the structured fields", weight=-0.25))
    if r == "LLM-021" and cs.max_calls_in_execution >= 20:
        added.append(Evidence("trace_stat", f"up to {cs.max_calls_in_execution} iterations in one execution", weight=0.2))
    if not added:
        return
    f.evidence += added
    f.confidence = round(combine(e.weight for e in f.evidence), 3)
    supported = any(e.weight > 0 for e in added)
    cap = EvidenceLevel.HIGH_CONFIDENCE if supported else EvidenceLevel(min(int(f.level), int(EvidenceLevel.HIGH_CONFIDENCE)))
    lvl = level_from_confidence(f.confidence, cap)
    f.level = lvl if lvl is not None else EvidenceLevel.HYPOTHESIS
