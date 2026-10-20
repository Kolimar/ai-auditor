"""Adversarial review: every finding must survive deterministic challenges before it is reported.

Each challenge asks "why could this recommendation be wrong?" using facts the analysis already has
(task profile, graph, IR). Outcomes:

* failed + blocking   -> the finding becomes DO_NOT_OPTIMIZE (survived_review=False, kept for the report
                         as "considered and discarded", with the reason);
* failed, non-blocking -> the level drops one step (demoted_from records the original);
* passed / unknown     -> recorded, no change.

The optional LLM reviewer (off by default) may only demote, never promote: see ``llm_review``.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from ai_auditor.analyzers.engine import AnalysisContext
from ai_auditor.analyzers.finding import Challenge, EvidenceLevel, Finding
from ai_auditor.ir.model import LLMStep, VarSource

# Recommendation families (what the finding asks to do with the LLM step).
REPLACE_WITH_CODE = {"LLM-001", "LLM-009", "LLM-010", "LLM-011", "LLM-020", "LLM-026"}
REMOVE_STEP = {"LLM-002", "LLM-006", "LLM-012"}
SMALLER_MODEL = {"LLM-003", "LLM-018", "LLM-013", "LLM-019"}
CUT_CONTEXT = {"LLM-004", "LLM-016", "LLM-023", "LLM-007"}
# Semantics-preserving recommendations (risk class A) are not challenged on task semantics.
PRESERVING = {"LLM-005", "LLM-014", "LLM-015", "LLM-021", "LLM-024", "LLM-025", "LLM-008", "LLM-022", "LLM-017"}

GUARDRAIL = re.compile(r"(?i)\b(moderat|guardrail|jailbreak|prompt injection|unsafe|toxic|self-harm|policy violation|"
                       r"moderaci[oó]n|contenido da[ñn]ino)")
USER_FACING = re.compile(r"(?i)\b(customer|user|client|cliente|usuario)s?\b.{0,40}\b(reply|email|message|response|respuesta|correo|mensaje)")

ChallengeFn = Callable[[AnalysisContext, Finding, LLMStep | None], Challenge | None]


def _step(ctx: AnalysisContext, f: Finding) -> LLMStep | None:
    node = ctx.ir.nodes.get(f.component_id or "")
    return node if isinstance(node, LLMStep) else None


def c_dead_code(ctx, f, step):
    if step is None:
        return None
    if step.attrs.get("non_production"):
        why = step.attrs.get("non_production_reason") or "examples/tests"
        return Challenge("non_production_code", "failed", f"step lives in non-production code ({step.location.file if step.location else '?'}: {why})", blocking=True)
    return Challenge("non_production_code", "passed", "step is in production code")


def c_judgment(ctx, f, step):
    if step is None or f.rule_id in PRESERVING:
        return None
    j = ctx.profile(step).judgment
    if not j:
        return Challenge("judgment_required", "passed", "no judgment cues in the instructions")
    blocking = f.rule_id in REPLACE_WITH_CODE and len(j) >= 2
    return Challenge("judgment_required", "failed", f"instructions ask for judgment: {j[:3]}", blocking=blocking)


def c_free_text_input(ctx, f, step):
    if step is None or f.rule_id not in REPLACE_WITH_CODE - {"LLM-020", "LLM-010"}:
        return None
    p = ctx.profile(step)
    if p.input_structured is False:
        return Challenge("free_text_input", "failed", f"code would have to interpret free text: {p.free_text_inputs[:3]}", blocking=True)
    if p.input_structured is None:
        return Challenge("free_text_input", "unknown", "input structure could not be established statically")
    return Challenge("free_text_input", "passed", f"structured input: {p.input_evidence[:2]}")


def c_risk_domain(ctx, f, step):
    if step is None or f.rule_id in PRESERVING:
        return None
    dom = ctx.profile(step).risk_domains
    if not dom:
        return Challenge("high_risk_domain", "passed", "no high-risk domain cues")
    if f.rule_id in REPLACE_WITH_CODE:
        # deterministic code is auditable; the risk is in misreading the task, already covered by other challenges
        return Challenge("high_risk_domain", "unknown", f"risk domain {sorted(dom)}: the replacement must be reviewed by a domain owner")
    return Challenge("high_risk_domain", "failed", f"risk domain {sorted(dom)}: quality regressions are costly", blocking=False)


def c_guardrail(ctx, f, step):
    if step is None or f.rule_id in PRESERVING:
        return None
    text = step.static_text()
    if not GUARDRAIL.search(text):
        return None
    blocking = f.rule_id in REMOVE_STEP | SMALLER_MODEL | REPLACE_WITH_CODE
    return Challenge("safety_guardrail", "failed", "the step acts as a safety/moderation guardrail", blocking=blocking)


def c_semantic_validator(ctx, f, step):
    if step is None or f.rule_id not in {"LLM-002", "LLM-011"}:
        return None
    p = ctx.profile(step)
    if p.has("validate_semantic"):
        return Challenge("semantic_validation", "failed", f"validator checks meaning, not structure: '{p.tasks['validate_semantic'][0][:80]}'", blocking=True)
    return Challenge("semantic_validation", "passed", "only structural checks found")


def c_history(ctx, f, step):
    if step is None or f.rule_id not in REPLACE_WITH_CODE:
        return None
    hist = [v.name for v in step.variables() if v.source == VarSource.HISTORY]
    if step.attrs.get("history_accumulates"):
        hist.append("accumulated messages")
    if not hist:
        return Challenge("implicit_context", "passed", "no conversation history in the prompt")
    return Challenge("implicit_context", "failed", f"output depends on conversation history {hist[:2]}", blocking=f.rule_id == "LLM-020")


def c_unresolved_prompt(ctx, f, step):
    if step is None or f.rule_id in PRESERVING:
        return None
    p = ctx.profile(step)
    if p.prompt_resolved:
        return Challenge("prompt_resolved", "passed", "prompt text resolved statically")
    return Challenge("prompt_resolved", "failed", "part of the prompt is built dynamically and was not seen", blocking=False)


def c_user_facing(ctx, f, step):
    if step is None or f.rule_id not in {"LLM-010", "LLM-003", "LLM-018"}:
        return None
    p = ctx.profile(step)
    if p.output_space == "open" and USER_FACING.search(step.static_text()):
        return Challenge("user_facing_output", "failed", "free-form output addressed to an end user", blocking=f.rule_id == "LLM-010")
    return None


def c_exclusive_context(ctx, f, step):
    """Context-cutting advice when the large input *is* what the task works on."""
    if step is None or f.rule_id not in {"LLM-004"}:
        return None
    if all(e.kind == "context_source" for e in f.evidence if e.weight > 0):
        return None  # always-loaded routing text (a description), not the input the task works on
    p = ctx.profile(step)
    if p.primary in ("summarize", "reason", "translate", "code") or p.output_space == "open":
        return Challenge("context_is_subject", "failed", f"the context is the object of a '{p.primary}' task", blocking=True)
    return None


def c_runtime(ctx, f, step):
    trace = [e for e in f.evidence if e.kind == "trace_stat"]
    if not trace:
        return None
    contra = [e for e in trace if e.weight <= -0.6]
    if contra:
        return Challenge("runtime_contradicts", "failed", contra[0].description, blocking=True)
    unused = [e for e in trace if e.weight == 0.0]
    if unused:
        return Challenge("runtime_sample", "unknown", unused[0].description)
    return Challenge("runtime_sample", "passed", "runtime sample large enough and not synthetic")


CHALLENGES: list[ChallengeFn] = [
    c_dead_code, c_judgment, c_free_text_input, c_risk_domain, c_guardrail, c_semantic_validator,
    c_history, c_unresolved_prompt, c_user_facing, c_exclusive_context, c_runtime,
]


def review(ctx: AnalysisContext, findings: Iterable[Finding]) -> list[Finding]:
    out = []
    for f in findings:
        step = _step(ctx, f)
        for ch in CHALLENGES:
            res = ch(ctx, f, step)
            if res is not None:
                f.challenges.append(res)
        failed = [c for c in f.challenges if c.outcome == "failed"]
        if any(c.blocking for c in failed):
            f.demoted_from = str(f.level)
            f.level = EvidenceLevel.DO_NOT_OPTIMIZE
            f.survived_review = False
        else:
            f.survived_review = True
            if failed and f.level > EvidenceLevel.HYPOTHESIS:
                f.demoted_from = str(f.level)
                f.level = EvidenceLevel(f.level - 1)
        out.append(f)
    return out


def llm_review(findings: list[Finding], judge: Callable[[Finding], str | None]) -> list[Finding]:
    """Optional second opinion. ``judge`` returns a reason to demote, or None. It can never promote."""
    for f in findings:
        if not f.actionable:
            continue
        reason = judge(f)
        if reason:
            f.challenges.append(Challenge("llm_reviewer", "failed", reason, blocking=False))
            if f.level > EvidenceLevel.HYPOTHESIS:
                f.demoted_from = f.demoted_from or str(f.level)
                f.level = EvidenceLevel(f.level - 1)
    return findings

