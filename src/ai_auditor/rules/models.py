"""Model-selection rules: oversized models, small-model candidates, missing routing, redundant reasoning. Risk class C."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import Finding, Risk, Severity
from ai_auditor.ir.model import LLMStep, StepKind
from ai_auditor.model_routing.catalog import TIER_ORDER
from ai_auditor.rules._common import CLASS_C, Builder, cc_procedure, finding, mechanical_profile, model_alternatives, potential, severity_for, skip_step

SIMPLE_TASKS = {"classify", "extract", "format", "validate_schema", "compute", "decide"}
OPEN_TASKS = {"generate", "reason", "summarize", "translate", "code", "conversation"}
CASCADE_VALIDATION = (
    "Offline replay on a labelled sample (≥ a few hundred items, stratified by label incl. rare classes): run the candidate "
    "model and the current one, compare per-class accuracy with a paired test (McNemar) and a pre-registered "
    "non-inferiority margin. Deploy as a cascade (small model first, escalate on low confidence or failed validation) in "
    "shadow mode before switching."
)


def _long_input(step: LLMStep, prof) -> str | None:
    big = [v for v in step.variables() if (v.est_tokens or 0) > 4000]
    if big:
        return f"large input variable {big[0].name} (~{big[0].est_tokens} tokens)"
    doc = [v.name for v in step.variables() if any(k in v.name.lower() for k in ("contract", "document", "filing", "report",
                                                                                   "transcript", "contrato", "documento", "informe"))]
    if doc:
        return f"document-like input {doc[0]}"
    return None


def _simple_profile(prof) -> bool:
    return prof.primary in SIMPLE_TASKS and prof.output_space in ("closed", "structured") and not (prof.tasks.keys() & {"reason", "generate", "code"} and prof.primary in OPEN_TASKS)


@register
class LargeModelSimpleTask(Rule):
    id = "LLM-003"
    title = "Large Model for Simple Task"
    category = "model_selection"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            info = p.model
            if info is None or info.tier not in ("frontier", "large"):
                continue
            cc_commands = step.framework == "claude_code" and len(step.attrs.get("fixed_commands") or []) >= 2 and not p.tasks.keys() & OPEN_TASKS
            if cc_procedure(step, ctx.profile(step)) and not cc_commands:
                continue  # task profile of a long tool-using procedure is not reliable enough to call it "simple"
            cc_mechanical = step.framework == "claude_code" and mechanical_profile(p)  # edits files: no output contract
            if not _simple_profile(p) and not cc_commands and not cc_mechanical:
                continue
            mechanical = p.primary in ("format", "validate_schema", "compute") or (p.primary == "extract" and p.input_structured)
            if info.tier == "large" and not mechanical and p.input_structured is False:
                continue  # semantic narrow task on a large (not frontier) model -> LLM-018 territory
            b = Builder()
            b.pro("model_catalog", f"model {info.id} is tier '{info.tier}' ({info.tier_source})", 0.45 if info.tier == "frontier" else 0.3, step.location)
            b.pro("profile", f"primary task '{p.primary}' with {p.output_space} output", 0.25)
            if p.short_output:
                b.pro("profile", "short output requested", 0.1)
            if mechanical:
                b.pro("profile", "mechanical task", 0.15)
            if p.judgment:
                b.con("prompt_text", f"judgment cues {p.judgment[:3]}", min(0.7, 0.25 * len(p.judgment)))
            if p.risk_domains:
                b.con("prompt_text", f"risk domain(s) {sorted(p.risk_domains)}", 0.3)
            if p.has("reason"):
                b.con("prompt_text", f"also asks to reason: '{p.tasks['reason'][0][:60]}'", 0.35)
            li = _long_input(step, p)
            if li:
                b.con("input", li, 0.4)
            if p.reasoning_requested and p.reasoning_consumed is not False:
                b.con("prompt_text", "explicit reasoning requested and possibly consumed", 0.2)
            if step.step_kind == StepKind.AGENT and len(step.tool_names) > 3:
                b.con("ir", f"agentic step with {len(step.tool_names)} tools", 0.3)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("The task profile is narrow (closed or structured output, no multi-step reasoning cues), while the "
                           f"model is in the '{info.tier}' tier. Smaller models of the same family are typically adequate for such "
                           "tasks, but this is a hypothesis about *this* task until measured."),
                current=f"{info.id} ({info.tier}) runs a '{p.primary}' task.",
                change=f"Evaluate a smaller model: {model_alternatives(ctx, step)}. Route by step, with fallback to the current model.",
                alternative="If the step is also a deterministic candidate (see related findings), prefer code over a smaller model.",
                risk=Risk.MEDIUM, risks=["Accuracy on rare/edge classes can drop even if average accuracy holds.",
                                         "Different tokenizers change token counts; compare real cost, not price ratios."],
                validation=CASCADE_VALIDATION, requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, None, "same number of calls; cheaper per-token price")
                yield f


@register
class SmallModelCandidate(Rule):
    id = "LLM-018"
    title = "Candidate for Small Model"
    category = "model_selection"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            info = p.model
            if info is None or TIER_ORDER.get(info.tier, -1) < TIER_ORDER["medium"] or info.tier == "frontier":
                continue
            if p.primary not in ("classify", "extract") or p.output_space not in ("closed", "structured"):
                continue
            if p.input_structured is not False:
                continue  # structured inputs are deterministic candidates (LLM-001/009), not small-model ones
            b = Builder()
            b.pro("profile", f"narrow semantic task '{p.primary}' over free text with {p.output_space} output", 0.35, step.location)
            b.pro("model_catalog", f"model {info.id} is tier '{info.tier}'", 0.2)
            if p.output_space == "closed" and len(p.labels) <= 10:
                b.pro("profile", f"few labels ({len(p.labels)})", 0.1)
            mult = ctx.graph.multiplicity(step.id)
            if mult.in_loop:
                b.pro("graph", "high-volume step (inside a loop)", 0.1)
            if p.judgment:
                b.con("prompt_text", f"judgment cues {p.judgment[:3]}", min(0.6, 0.2 * len(p.judgment)))
            if p.risk_domains:
                b.con("prompt_text", f"risk domain(s) {sorted(p.risk_domains)}", 0.35)
            li = _long_input(step, p)
            if li:
                b.con("input", li, 0.3)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("Classification/extraction over free text needs language understanding, so code is not a safe "
                           "replacement, but narrow tasks are where small models most often match larger ones."),
                current=f"{info.id} ({info.tier}) performs '{p.primary}'.",
                change=f"Run a cascade experiment with {model_alternatives(ctx, step)}; escalate to the current model on low confidence.",
                alternative="With enough labelled traces, a fine-tuned small classifier (distillation).",
                risk=Risk.MEDIUM, risks=["Small models degrade more on out-of-distribution inputs and rare classes."],
                validation=CASCADE_VALIDATION, requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, None, "same calls; cheaper per-token price")
                yield f


@register
class MissingModelRouting(Rule):
    id = "LLM-013"
    title = "Missing Model Routing"
    category = "model_selection"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        by_model: dict[str, list[LLMStep]] = defaultdict(list)
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.framework == "claude_code":
                continue
            info = ctx.profile(step).model
            if info is not None:
                by_model[info.id].append(step)
        known = sum(len(v) for v in by_model.values())
        if known < 3:
            return
        for model_id, steps in by_model.items():
            info = ctx.profile(steps[0]).model
            if info is None or info.tier not in ("frontier", "large") or len(steps) < 3 or len(steps) / known < 0.75:
                continue
            simple = [s for s in steps if _simple_profile(ctx.profile(s))]
            complex_ = [s for s in steps if ctx.profile(s).primary in OPEN_TASKS]
            if not simple or not complex_:
                continue
            b = Builder()
            b.pro("ir", f"{len(steps)}/{known} LLM steps use {model_id} ({info.tier})", 0.3)
            b.pro("profile", f"{len(simple)} narrow steps ({[s.name for s in simple[:4]]}) next to {len(complex_)} open-ended ones", 0.35)
            f = finding(
                self, ctx, None, b, CLASS_C, component="*system*", location=steps[0].location,
                severity=Severity.MEDIUM,
                reasoning="Steps with very different difficulty share one top-tier model; per-step routing is decided statically, at no runtime cost.",
                current=f"Single model {model_id} for heterogeneous steps.",
                change=f"Assign models per step: keep {model_id} for {[s.name for s in complex_[:3]]}; evaluate cheaper tiers for {[s.name for s in simple[:4]]}.",
                risk=Risk.MEDIUM, validation=CASCADE_VALIDATION, requires_runtime=True,
            )
            if f:
                f.related = [s.id for s in simple]
                yield f


@register
class RedundantReasoning(Rule):
    id = "LLM-007"
    title = "Redundant Reasoning"
    category = "model_selection"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            textual = [r for r in p.reasoning_requested if not r.startswith("thinking/effort configured")]
            if not textual or p.primary not in SIMPLE_TASKS or cc_procedure(step, ctx.profile(step)) or p.output_space not in ("closed", "structured"):
                continue
            b = Builder()
            b.pro("prompt_text", f"reasoning requested: {textual[:2]}", 0.35, step.location)
            if step.thinking:
                b.pro("params", f"thinking/reasoning configured: {step.thinking}", 0.2)
            if p.output_space == "closed":
                b.pro("profile", f"final answer is a label among {p.labels[:5]}", 0.2)
            if p.reasoning_consumed is False or (p.controls_branch and not p.consumers):
                b.pro("graph", "only the label is consumed downstream (code branch); the reasoning text is discarded", 0.25)
            if p.judgment:
                b.con("prompt_text", f"judgment cues {p.judgment[:3]}", 0.3)
            if p.risk_domains:
                b.con("prompt_text", f"risk domain(s) {sorted(p.risk_domains)}: reasoning may be kept for auditability", 0.3)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning="Reasoning tokens are billed as output and add latency; for narrow tasks whose rationale is thrown away the benefit is unproven.",
                current="The step asks for explicit reasoning before a short answer that is the only thing used.",
                change="Remove the chain-of-thought instruction / lower the thinking budget or effort, and request the label only.",
                alternative="Keep reasoning only on low-confidence cases (two-pass) or log it for sampled audits.",
                risk=Risk.MEDIUM, risks=["Some tasks do gain accuracy from reasoning; measure before removing."],
                validation="A/B on a labelled sample: accuracy and output tokens with vs without reasoning, k≥3 runs per item.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, None, "fewer output (reasoning) tokens per call")
                yield f
