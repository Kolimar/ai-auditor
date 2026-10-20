"""Report renderers: text (terminal), markdown, json, sarif.

All renderers keep the four impact categories separate and print "not available" instead of inventing numbers.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, Any

from ai_auditor.analyzers.finding import EvidenceLevel, Finding, StaticPotential

if TYPE_CHECKING:
    from ai_auditor.audit import AuditResult

NOT_AVAILABLE_RUNTIME = "not available (no runtime traces; run with --traces)"
NOT_AVAILABLE_EXPERIMENT = "not available (no experiment run)"


def _static(sp: StaticPotential | None) -> str:
    if sp is None:
        return "not quantified statically"
    parts = []
    if sp.llm_calls_removed_per_invocation:
        parts.append(f"{sp.llm_calls_removed_per_invocation:g} LLM call(s) removed per invocation")
    elif sp.llm_calls_removed_per_invocation is None:
        parts.append("calls removed: depends on runtime failure rate")
    if sp.context_tokens_removed_per_invocation:
        parts.append(f"~{sp.context_tokens_removed_per_invocation} input tokens per invocation (estimated)")
    parts.append(f"invocations per execution: {sp.invocations_per_execution}")
    if sp.notes:
        parts.append(sp.notes)
    return "; ".join(parts)


def _impact_lines(f: Finding, synthetic: bool = False) -> list[tuple[str, str]]:
    im = f.impact
    tag = "SYNTHETIC traces, illustrative only — " if synthetic else ""
    obs = NOT_AVAILABLE_RUNTIME
    if im.observed:
        o = im.observed
        cost = f"${o.cost_per_execution:.6f}/execution" if o.cost_per_execution is not None else "cost UNKNOWN (no price for model)"
        obs = f"{tag}{o.n_executions} executions; {o.calls_per_execution} calls/execution; {cost}"
    est = "not available (needs observed runtime data)"
    if im.estimated:
        e = im.estimated
        val = f"${e.cost_saving_per_execution:.6f}/execution" if e.cost_saving_per_execution is not None else "UNKNOWN"
        est = f"{tag}{val} ({e.method}; assumptions: {'; '.join(e.assumptions)})"
    val = NOT_AVAILABLE_EXPERIMENT
    if im.validated:
        v = im.validated
        ci = f" CI {v.quality_delta_ci[0]:+.3f}..{v.quality_delta_ci[1]:+.3f}" if v.quality_delta_ci else ""
        dq = f"{v.quality_delta:+.3f}" if v.quality_delta is not None else "n/a"
        dc = f"{v.cost_delta_pct:+.1f}%" if v.cost_delta_pct is not None else "UNKNOWN"
        val = f"{v.decision} (experiment {v.experiment_id}, n={v.n_cases}, Δquality {dq}{ci}, Δcost {dc})"
    return [("Static potential", _static(im.static_potential)), ("Observed runtime", obs), ("Estimated saving", est), ("Validated", val)]


def _loc(f: Finding) -> str:
    return str(f.location) if f.location else "-"


def _summary(res: AuditResult) -> dict[str, Any]:
    steps = res.ir.llm_steps()
    return {
        "root": res.root,
        "files": res.extract_stats.get("files"),
        "llm_steps": len(steps),
        "agents": sum(1 for s in steps if s.step_kind.value == "agent"),
        # Markdown steps are all agent-run; what they are (agent, skill, command, stage) is in cc_type
        "step_kinds": dict(Counter(s.attrs.get("cc_type") or s.step_kind.value for s in steps)),
        "actionable": sum(1 for f in res.actionable if not f.superseded_by),
        "superseded": sum(1 for f in res.actionable if f.superseded_by),
        "by_level": dict(Counter(str(f.level) for f in res.actionable if not f.superseded_by)),
        "discarded_by_review": len(res.discarded),
        "llm_justified": len(res.justified),
        "unassessed_steps": len(res.unassessed_steps()),
        "rules_run": len(res.engine.rules_run),
        "rules_skipped": res.engine.rules_skipped,
        "rule_errors": res.engine.errors,
        "timings_ms": {k: round(v, 1) for k, v in res.timings_ms.items()},
        "cache": {"hits": res.extract_stats.get("cache_hits"), "misses": res.extract_stats.get("cache_misses")},
        **res.meta,
    }


def _kinds(s: dict[str, Any]) -> str:
    plural = {"agent": "agents", "skill": "skills", "command": "commands", "stage": "stages", "call": "calls"}
    return ", ".join(f"{n} {plural.get(k, k) if n != 1 else k}" for k, n in sorted(s["step_kinds"].items())) or "none"


# ---------------------------------------------------------------------------------------------- markdown

def render_markdown(res: AuditResult, findings: list[Finding] | None = None) -> str:
    findings = findings if findings is not None else res.findings
    s = _summary(res)
    act = [f for f in findings if f.actionable and not f.superseded_by]
    sup = [f for f in findings if f.actionable and f.superseded_by]
    rt = s.get("runtime") or {}
    synthetic = bool(rt.get("synthetic"))
    out: list[str] = ["# AI Workflow Optimization Audit", "", f"`{s['root']}`", ""]
    out += [
        "## Summary", "",
        f"- Files analysed: {s['files']} · LLM steps: {s['llm_steps']} ({_kinds(s)})",
        f"- Recommendations: **{len(act)}** ({', '.join(f'{k}: {v}' for k, v in sorted(s['by_level'].items())) or 'none'})"
        + (f", plus {len(sup)} superseded by a stronger one" if sup else ""),
        f"- Discarded by adversarial review: {s['discarded_by_review']} · LLM use justified: {s['llm_justified']}"
        f" · Steps without enough evidence either way: {s['unassessed_steps']}",
        *[f"- **Extractor crash — partial results:** {d.message}" for d in res.ir.diagnostics if d.code == "EXTRACTOR_CRASH"],
        f"- Runtime data: {'yes' if s['runtime_data'] else 'no — observed, estimated and validated savings are not available'}",
        f"- LLM calls made by the auditor: {s['llm_calls_made_by_auditor']} · Token counts: {s['token_estimator']}",
        f"- Pricing data: {s['pricing_origin']}",
        "",
        *_md_runtime(rt, s.get("experiments")),
        "Evidence levels: PROVEN requires an accepted experiment; HIGH_CONFIDENCE = structural evidence; LIKELY = consistent"
        " heuristic evidence; HYPOTHESIS = worth checking; DO_NOT_OPTIMIZE = the LLM is justified. Confidence values are"
        " heuristic until calibrated (see evaluation report).",
        "",
    ]
    if act:
        out += ["## Prioritized recommendations", "", "| # | Level | Sev. | Rule | Component | Location | Change |", "|---|---|---|---|---|---|---|"]
        for i, f in enumerate(act, 1):
            out.append(f"| {i} | {f.level} | {f.severity} | {f.rule_id} {f.title} | `{f.component}` | {_loc(f)} | {f.recommended_change[:110]} |")
        out.append("")
        out += ["## Findings in detail", ""]
        for i, f in enumerate(act, 1):
            out += _md_finding(i, f, synthetic)
    if sup:
        out += ["## Superseded recommendations", "", "Weaker alternatives on components that already have a stronger recommendation.", ""]
        for f in sup:
            out.append(f"- {f.rule_id} {f.title} on `{f.component}` ({f.level}) — superseded by `{f.superseded_by}`")
        out.append("")
    disc = [f for f in findings if f.survived_review is False]
    if disc:
        out += ["## Considered and discarded (adversarial review)", ""]
        for f in disc:
            why = "; ".join(c.detail for c in f.challenges if c.outcome == "failed" and c.blocking)
            out.append(f"- {f.rule_id} {f.title} on `{f.component}` ({_loc(f)}), was {f.demoted_from}: **{why}**")
        out.append("")
    just = [f for f in findings if f.level == EvidenceLevel.DO_NOT_OPTIMIZE and f.survived_review is not False]
    if just:
        out += ["## LLM use justified (DO_NOT_OPTIMIZE)", ""]
        for f in just:
            det = f.determinism or {}
            score = f" · determinism {det.get('score')} ({det.get('band')})" if det.get("score") is not None else ""
            out.append(f"- `{f.component}` ({_loc(f)}){score}: " + "; ".join(e.description for e in f.evidence))
        out.append("")
    un = res.unassessed_steps()
    if un:
        out += ["## Not enough evidence either way", "", "No rule fired and no necessity evidence was found. Runtime traces would help.", ""]
        out += [f"- `{n}`" for n in un] + [""]
    if res.ir.diagnostics:
        out += ["## Analysis diagnostics", ""]
        for code, n in Counter(d.code for d in res.ir.diagnostics).most_common():
            ex = next(d for d in res.ir.diagnostics if d.code == code)
            out.append(f"- {code} × {n} — e.g. {ex.message}" + (f" ({ex.location})" if ex.location else ""))
        out.append("")
    if s["rule_errors"]:
        out += ["## Rule errors", ""] + [f"- {k}: {v}" for k, v in s["rule_errors"].items()] + [""]
    out.append(f"_ai-auditor {s['auditor_version']} · timings (ms): {s['timings_ms']}_")
    return "\n".join(out) + "\n"


def _md_finding(i: int, f: Finding, synthetic: bool = False) -> list[str]:
    o = [f"### {i}. {f.rule_id} {f.title} — `{f.component}`", "",
         f"**Level:** {f.level}" + (f" (demoted from {f.demoted_from})" if f.demoted_from else "")
         + f" · **Confidence:** {f.confidence:.2f} · **Severity:** {f.severity} · **Risk:** {f.risk} · **Location:** {_loc(f)}"
         + f" · **Needs runtime data to confirm:** {'yes' if f.requires_runtime_data else 'no'}", "",
         f"**Current:** {f.current_behavior}", "", f"**Recommended:** {f.recommended_change}", ""]
    if f.alternative:
        o += [f"**Alternative:** {f.alternative}", ""]
    o += [f"**Why:** {f.reasoning}", "", "**Evidence:**", ""]
    for e in f.evidence:
        sign = "for" if e.weight >= 0 else "against"
        o.append(f"- ({sign}, {abs(e.weight):.2f}) {e.description}" + (f" — {e.location}" if e.location else ""))
    o.append("")
    det = f.determinism or {}
    if det.get("score") is not None:
        o.append(f"**Determinism score:** {det['score']}/100 ({det['band']})")
        for c in det.get("contributions", [])[:6]:
            o.append(f"- {c['points']:+g} {c['feature']}: {c['evidence']}")
        o.append("")
    flagged = [c for c in f.challenges if c.outcome != "passed"]
    if flagged:
        o += ["**Adversarial review:**", ""] + [f"- {c.name}: {c.outcome} — {c.detail}" for c in flagged] + [""]
    if f.risks:
        o += ["**Risks:** " + " ".join(f.risks), ""]
    o += [f"**How to validate:** {f.validation}", "", "**Impact (never summed across categories):**", ""]
    o += [f"- {k}: {v}" for k, v in _impact_lines(f, synthetic)] + [""]
    return o


def _md_runtime(rt: dict[str, Any], experiments: dict[str, Any] | None) -> list[str]:
    o: list[str] = []
    if rt:
        o += ["## Runtime data", ""]
        if rt.get("synthetic"):
            o += ["> **SYNTHETIC traces.** Every runtime number below and in the findings is illustrative only: synthetic data"
                  " never changes an evidence level and must not be quoted as a measurement.", ""]
        o += [f"- Executions: {rt['executions']} · spans: {rt['spans']} · sources: {', '.join(rt['sources']) or '-'}"
              f" · spans without a component: {rt['unattributed_spans']}",
              f"- Total observed cost: ${rt['total_cost_usd']:.6f}"
              + (f" + **{rt['cost_unknown_calls']} calls with UNKNOWN cost** (no price or usage)" if rt["cost_unknown_calls"] else ""),
              f"- Steps observed in traces: {len(rt['observed_steps'])} · not observed: {len(rt['unobserved_steps'])}"
              + (f" ({', '.join(rt['unobserved_steps'][:8])})" if rt["unobserved_steps"] else ""),
              ]
        if rt["unmatched_components"]:
            o.append(f"- Trace components that match no step in the code: {', '.join(rt['unmatched_components'][:8])}")
        o += [f"- {n}" for n in rt.get("notes", [])] + [""]
    if experiments:
        o += ["## Experiments", "", f"- Attached: {experiments['attached']} ({experiments['by_decision']})"]
        o += [f"- {n}" for n in experiments.get("notes", [])] + [""]
    return o


# ---------------------------------------------------------------------------------------------- text

def render_text(res: AuditResult, findings: list[Finding] | None = None, max_items: int = 15) -> str:
    findings = findings if findings is not None else res.findings
    s = _summary(res)
    act = [f for f in findings if f.actionable and not f.superseded_by]
    lines = [
        f"ai-auditor {s['auditor_version']}  {s['root']}",
        f"files {s['files']} · LLM steps {s['llm_steps']} ({_kinds(s)}) · {sum(s['timings_ms'].values()):.0f} ms · auditor LLM calls: {s['llm_calls_made_by_auditor']}",
        f"recommendations {len(act)} · discarded by review {s['discarded_by_review']} · justified {s['llm_justified']} · unassessed {s['unassessed_steps']}",
        *[f"!! {d.message}" for d in res.ir.diagnostics if d.code == "EXTRACTOR_CRASH"],
        f"runtime data: {'yes' if s['runtime_data'] else 'no (observed/estimated/validated savings: not available)'}"
        + (" — SYNTHETIC traces: runtime figures are illustrative only" if (s.get("runtime") or {}).get("synthetic") else ""),
        "",
    ]
    for i, f in enumerate(act[:max_items], 1):
        lines.append(f"{i:>2}. [{f.level}] {f.rule_id} {f.title}  ·  {f.component}  ·  {_loc(f)}")
        lines.append(f"    confidence {f.confidence:.2f} · severity {f.severity} · risk {f.risk}" + (f" · demoted from {f.demoted_from}" if f.demoted_from else ""))
        lines.append(f"    → {f.recommended_change}")
        for e in sorted(f.evidence, key=lambda e: -e.weight)[:3]:
            lines.append(f"      {'+' if e.weight >= 0 else '-'} {e.description[:140]}")
        lines.append(f"    static potential: {_static(f.impact.static_potential)}")
        lines.append("")
    if len(act) > max_items:
        lines.append(f"... {len(act) - max_items} more (use --format markdown for the full report)")
    disc = [f for f in findings if f.survived_review is False]
    if disc:
        lines.append("Discarded by adversarial review:")
        for f in disc:
            why = "; ".join(c.detail for c in f.challenges if c.outcome == "failed" and c.blocking)
            lines.append(f"  - {f.rule_id} on {f.component}: {why[:140]}")
        lines.append("")
    just = [f for f in findings if f.level == EvidenceLevel.DO_NOT_OPTIMIZE and f.survived_review is not False]
    if just:
        lines.append("LLM use justified: " + ", ".join(f.component for f in just))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------- json / sarif

def render_json(res: AuditResult, findings: list[Finding] | None = None) -> str:
    findings = findings if findings is not None else res.findings
    return json.dumps({"summary": _summary(res), "findings": [f.to_dict() for f in findings],
                       "unassessed_steps": res.unassessed_steps(),
                       "diagnostics": [d.__dict__ | {"location": str(d.location) if d.location else None} for d in res.ir.diagnostics]},
                      indent=2, default=str, ensure_ascii=False)


SARIF_LEVEL = {EvidenceLevel.PROVEN: "error", EvidenceLevel.HIGH_CONFIDENCE: "warning", EvidenceLevel.LIKELY: "warning",
               EvidenceLevel.HYPOTHESIS: "note", EvidenceLevel.DO_NOT_OPTIMIZE: "none"}


def render_sarif(res: AuditResult, findings: list[Finding] | None = None) -> str:
    from ai_auditor import __version__
    from ai_auditor.analyzers.engine import load_rules

    findings = [f for f in (findings if findings is not None else res.findings) if f.actionable]
    rules = load_rules()
    results = []
    for f in findings:
        r: dict[str, Any] = {
            "ruleId": f.rule_id, "level": SARIF_LEVEL[f.level],
            "message": {"text": f"{f.title}: {f.recommended_change}"},
            "properties": {"evidenceLevel": str(f.level), "confidence": f.confidence, "component": f.component,
                           "supersededBy": f.superseded_by},
            "partialFingerprints": {"aiAuditorId": f.id},
        }
        if f.location and f.location.file:
            region = {"startLine": f.location.line} if f.location.line else {}
            r["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": f.location.file}, **({"region": region} if region else {})}}]
        results.append(r)
    doc = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "ai-auditor", "version": __version__,
                                       "rules": [{"id": rid, "name": cls.title, "shortDescription": {"text": cls.title}}
                                                 for rid, cls in rules.items()]}},
                  "results": results}],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


RENDERERS = {"text": render_text, "markdown": render_markdown, "json": render_json, "sarif": render_sarif}
