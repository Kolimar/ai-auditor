"""Shared helpers for rules: evidence accumulation, risk-class caps, static potential."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_auditor.analyzers.engine import AnalysisContext, combine, level_from_confidence
from ai_auditor.analyzers.finding import (
    Evidence,
    EvidenceLevel,
    Finding,
    Impact,
    Risk,
    Severity,
    StaticPotential,
)
from ai_auditor.ir.model import LLMStep, SourceLocation

# Risk classes: the strongest level that static
# evidence may claim depends on whether the change can alter outputs.
CLASS_A = "A"  # semantics-preserving (caching, batch, parallelize, bound loops)
CLASS_B = "B"  # mechanical replacement (parser/formatter/schema check/precompute/fixed tool call)
CLASS_C = "C"  # may affect quality (smaller model, routing, remove agent/validator, cut context)

STATIC_CAP = {CLASS_A: EvidenceLevel.HIGH_CONFIDENCE, CLASS_B: EvidenceLevel.HIGH_CONFIDENCE, CLASS_C: EvidenceLevel.LIKELY}


@dataclass
class Builder:
    """Accumulates weighted evidence for one candidate finding."""

    evidence: list[Evidence] = field(default_factory=list)

    def pro(self, kind: str, desc: str, weight: float, location: SourceLocation | None = None, value: object = None) -> None:
        self.evidence.append(Evidence(kind, desc, location, value, abs(weight)))

    def con(self, kind: str, desc: str, weight: float, location: SourceLocation | None = None, value: object = None) -> None:
        self.evidence.append(Evidence(kind, desc, location, value, -abs(weight)))

    @property
    def confidence(self) -> float:
        return combine(e.weight for e in self.evidence)

    def level(self, cap: EvidenceLevel) -> EvidenceLevel | None:
        return level_from_confidence(self.confidence, cap)


def skip_step(step: LLMStep) -> bool:
    return bool(step.attrs.get("dead_code"))


ACTING_TOOLS = {"bash", "edit", "write", "multiedit", "notebookedit", "webfetch", "websearch", "task", "agent"}


def cc_procedure(step: LLMStep, prof=None) -> bool:
    """A Claude Code agent/skill that runs a multi-step procedure with tools: replacing it "with code" is not a
    mechanical change, whatever fragments of its instructions look like (`compute`, `validate`, ...).

    Acting (or inherited) tools alone do not make a procedure: a short body whose task profile is a mechanical,
    bounded transformation (format, compute, schema check, extraction, without judgment) is still a candidate.
    """
    if step.framework != "claude_code":
        return False
    if int(step.attrs.get("body_tokens") or 0) > 600:
        return True
    tools = {t.lower().split("(")[0] for t in step.tool_names}
    if not (tools & ACTING_TOOLS or step.attrs.get("tools_inherited")):
        return False
    return not (prof is not None and mechanical_profile(prof))


def mechanical_profile(prof) -> bool:
    return (prof.primary in ("format", "compute", "validate_schema", "extract")
            and not prof.tasks.keys() & {"reason", "generate", "code", "summarize", "translate"} and not prof.judgment)


def potential(ctx: AnalysisContext, step: LLMStep, calls: float | None = 1.0, tokens: int | None = None, notes: str = "") -> StaticPotential:
    mult = ctx.graph.multiplicity(step.id)
    per = mult.per_execution
    if step.step_kind.value == "agent":
        per = "1 agent run (multiple model turns)" if per == "1" else per
    return StaticPotential(calls, tokens, per, notes)


def severity_for(ctx: AnalysisContext, step: LLMStep, base: Severity) -> Severity:
    """Raise severity when the step runs many times or uses a top-tier model."""
    sev = int(base)
    mult = ctx.graph.multiplicity(step.id)
    if mult.in_loop or step.attrs.get("entrypoints"):
        sev += 1
    prof = ctx.profile(step)
    if prof.model and prof.model.tier == "frontier":
        sev += 1
    return Severity(min(sev, int(Severity.HIGH)))


def finding(
    rule,
    ctx: AnalysisContext,
    step: LLMStep | None,
    b: Builder,
    risk_class: str,
    *,
    component: str | None = None,
    location: SourceLocation | None = None,
    severity: Severity,
    reasoning: str,
    current: str,
    change: str,
    alternative: str = "",
    risk: Risk = Risk.MEDIUM,
    risks: list[str] | None = None,
    validation: str = "",
    requires_runtime: bool = True,
    impact: Impact | None = None,
    cap: EvidenceLevel | None = None,
    with_determinism: bool = False,
) -> Finding | None:
    effective_cap = min(cap or STATIC_CAP[risk_class], STATIC_CAP[risk_class])
    lvl = b.level(effective_cap)
    if lvl is None:
        return None
    f = Finding(
        rule_id=rule.id, title=rule.title, category=rule.category, severity=severity, level=lvl, confidence=b.confidence,
        component=component or (step.name if step else "*system*"), component_id=step.id if step else None,
        location=location or (step.location if step else None), evidence=b.evidence, reasoning=reasoning,
        current_behavior=current, recommended_change=change, alternative=alternative, risk=risk, risks=risks or [],
        validation=validation, requires_runtime_data=requires_runtime, impact=impact or Impact(),
        determinism=ctx.profile(step).determinism if (with_determinism and step is not None) else None,
    )
    f.__dict__["risk_class"] = risk_class
    return f


def model_alternatives(ctx: AnalysisContext, step: LLMStep) -> str:
    prof = ctx.profile(step)
    info = prof.model
    if info is None:
        return "a smaller model of the same provider"
    alts = ctx.catalog.cheaper_same_provider(info)
    if not alts:
        return "a smaller model (none with known price in the catalog for this provider)"
    out = []
    for a in alts[:3]:
        ratio = ""
        if info.price and a.price and info.price.input and a.price.input:
            ratio = f", input price {info.price.input / a.price.input:.0f}x lower per catalog {a.price.retrieved_at}"
        out.append(f"{a.id} ({a.tier}{ratio})")
    return "; ".join(out)
