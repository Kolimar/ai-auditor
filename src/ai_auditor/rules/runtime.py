"""Rules that need runtime traces (skipped without them)."""

from __future__ import annotations

from typing import ClassVar, Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import Estimate, Finding, ObservedRuntime, Risk, Severity
from ai_auditor.rules._common import CLASS_A, Builder, finding, skip_step
from ai_auditor.tracing.attach import MIN_CALLS_FOR_EVIDENCE, component_stats


@register
class DuplicateCalls(Rule):
    id = "LLM-027"
    title = "Duplicate LLM Calls"
    category = "caching"
    needs: ClassVar[frozenset[str]] = frozenset({"runtime"})

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        rt = ctx.runtime
        n = max(rt.n_executions, 1)
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            cs = component_stats(rt, step)
            if cs is None or not cs.duplicate_calls:
                continue
            b = Builder()
            share = cs.duplicate_calls / cs.calls
            if rt.synthetic or cs.calls < MIN_CALLS_FOR_EVIDENCE:
                b.pro("trace_stat", f"{cs.duplicate_calls}/{cs.calls} calls repeat an identical request within the same execution (small or synthetic sample)", 0.3)
            else:
                b.pro("trace_stat", f"{cs.duplicate_calls}/{cs.calls} calls ({share:.1%}) repeat an identical request within the same execution", 0.75)
            f = finding(
                self, ctx, step, b, CLASS_A, severity=Severity.MEDIUM if share >= 0.1 else Severity.LOW,
                reasoning="An identical request in the same execution returns an equivalent answer; recomputing it pays twice.",
                current=f"'{step.name}' is called again with the same prompt during one execution.",
                change="Memoize the result per execution (keyed by the request hash) or restructure so it is computed once.",
                risk=Risk.LOW, risks=["If sampling diversity is intended (temperature > 0, self-consistency voting), keep the repeats."],
                validation="Assert identical downstream results with memoization on recorded executions.",
                requires_runtime=True,
            )
            if f:
                cost = None if cs.cost_unknown_calls else cs.cost_usd / n
                f.impact.observed = ObservedRuntime(rt.n_executions, round(cs.calls / n, 3), cost, cs.cost_unknown_calls,
                                                    stats={"duplicate_calls": cs.duplicate_calls, "synthetic": rt.synthetic})
                if cost is not None:
                    f.impact.estimated = Estimate(cost * share, share, "share of duplicate calls × component cost",
                                                  ["duplicates have the same token cost as the first call"])
                yield f
