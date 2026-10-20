"""Necessity assessment and prioritization.

``necessity`` emits explicit DO_NOT_OPTIMIZE conclusions ("the LLM is justified here, and why") for steps that no
actionable finding targets and whose profile shows open generation, judgment or language understanding. Steps with
neither optimization evidence nor necessity evidence get no conclusion: the report lists them as "insufficient
evidence" rather than guessing.

``prioritize`` orders findings and marks weaker recommendations that a stronger one on the same component supersedes
(e.g. "use a smaller model" is moot if the step can become code).
"""

from __future__ import annotations

from ai_auditor.analyzers.engine import AnalysisContext, combine
from ai_auditor.analyzers.finding import Evidence, EvidenceLevel, Finding, Risk, Severity
from ai_auditor.ir.model import StepKind
from ai_auditor.optimization.adversarial import CUT_CONTEXT, REMOVE_STEP, REPLACE_WITH_CODE, SMALLER_MODEL

NECESSITY_RULE = "LLM-000"
OPEN_TASKS = {"generate", "reason", "summarize", "translate", "code", "conversation"}


def necessity(ctx: AnalysisContext, findings: list[Finding]) -> list[Finding]:
    targeted = {f.component_id for f in findings if f.actionable and f.component_id}
    targeted |= {r for f in findings if f.actionable for r in f.related}
    out: list[Finding] = []
    for step in ctx.ir.llm_steps():
        if step.id in targeted or step.attrs.get("dead_code") or step.attrs.get("non_production"):
            continue
        p = ctx.profile(step)
        ev: list[Evidence] = []
        if p.output_space == "open" or p.primary in OPEN_TASKS:
            ev.append(Evidence("profile", f"open-ended task '{p.primary}' with {p.output_space} output", step.location, weight=0.6))
        if p.judgment:
            ev.append(Evidence("prompt_text", f"requires judgment: {p.judgment[:3]}", weight=min(0.6, 0.25 * len(p.judgment))))
        if p.input_structured is False and p.primary in ("classify", "extract", "decide", "validate_semantic"):
            ev.append(Evidence("profile", f"interprets free text {p.free_text_inputs[:2]}", weight=0.45))
        if p.has("validate_semantic"):
            ev.append(Evidence("prompt_text", f"semantic check: '{p.tasks['validate_semantic'][0][:60]}'", weight=0.4))
        if step.step_kind == StepKind.AGENT and (step.tool_names or step.attrs.get("tools_count")):
            ev.append(Evidence("ir", "agent decides which tools to call and when", weight=0.35))
        if p.risk_domains:
            ev.append(Evidence("prompt_text", f"high-risk domain {sorted(p.risk_domains)}: changes need measured evidence", weight=0.2))
        det = p.determinism or {}
        if det.get("band") in ("generative", "model_dependent"):
            ev.append(Evidence("determinism", f"determinism score {det.get('score')} ({det.get('band')})", weight=0.2))
        if not ev:
            continue
        conf = combine(e.weight for e in ev)
        if conf < 0.5:
            continue
        f = Finding(
            rule_id=NECESSITY_RULE, title="LLM use justified", category="necessity", severity=Severity.INFO,
            level=EvidenceLevel.DO_NOT_OPTIMIZE, confidence=conf, component=step.name, component_id=step.id,
            location=step.location, evidence=ev,
            reasoning="No optimization rule found removable work here, and the task profile needs language understanding or generation.",
            current_behavior=f"'{p.primary}' task on {p.model.id if p.model else 'an unresolved model'}.",
            recommended_change="Keep the LLM. Revisit only with runtime evidence (e.g. a cheaper model in a measured experiment).",
            risk=Risk.LOW, requires_runtime_data=False, determinism=p.determinism or None,
        )
        f.survived_review = True
        out.append(f)
    return out


STRENGTH = {**{r: 3 for r in REPLACE_WITH_CODE | REMOVE_STEP}, **{r: 2 for r in SMALLER_MODEL}, **{r: 1 for r in CUT_CONTEXT}}


def prioritize(findings: list[Finding]) -> list[Finding]:
    by_comp: dict[str, list[Finding]] = {}
    for f in findings:
        if f.actionable and f.component_id:
            by_comp.setdefault(f.component_id, []).append(f)
    for group in by_comp.values():
        strongest = max(group, key=lambda f: (STRENGTH.get(f.rule_id, 0), int(f.level), f.confidence))
        top = STRENGTH.get(strongest.rule_id, 0)
        for f in group:
            if f is not strongest and 0 < STRENGTH.get(f.rule_id, 0) < top and f.level <= strongest.level:
                f.superseded_by = strongest.id

    def key(f: Finding):
        return (not f.actionable, f.superseded_by is not None, -int(f.level), -int(f.severity), -f.confidence, f.rule_id)

    return sorted(findings, key=key)
