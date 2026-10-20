"""Rules where (part of) an LLM step can become deterministic code. Risk class B."""

from __future__ import annotations

import re
from typing import Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import EvidenceLevel, Finding, Risk, Severity
from ai_auditor.ir.model import StepKind, VarSource
from ai_auditor.rules._common import CLASS_B, Builder, cc_procedure, finding, potential, severity_for, skip_step

FIDELITY_VALIDATION = (
    "Replay recorded inputs (or a labelled sample) through the deterministic replacement and the current LLM step; "
    "report fidelity (agreement with the LLM) and correctness (agreement with gold labels) with Wilson 95% intervals, "
    "per label. Ship as a fast path with LLM fallback for inputs the code cannot handle, then compare in shadow mode."
)
SCANNED = re.compile(r"(?i)\b(scanned|ocr|handwrit|pdf|image|photo|escanead|manuscrit|fotograf)")


def _common_counter(b: Builder, prof) -> None:
    if prof.judgment:
        b.con("prompt_text", f"judgment cues in instructions: {prof.judgment[:3]}", min(0.85, 0.3 * len(prof.judgment)))
    if prof.has("validate_semantic"):
        b.con("prompt_text", f"semantic verification requested: '{prof.tasks['validate_semantic'][0][:70]}'", 0.6)
    open_primary = prof.primary in ("generate", "reason", "summarize", "translate", "code", "conversation")
    if open_primary:
        b.con("prompt_text", f"primary task is {prof.primary}", 0.7)
    if not prof.prompt_resolved:
        b.con("ir", "prompt instructions not resolvable statically", 0.5)


def _structured_input_evidence(b: Builder, prof, w_struct: float, w_free: float) -> None:
    if prof.input_structured is True:
        b.pro("input", "; ".join(prof.input_evidence[:2]) or "structured input", w_struct)
    elif prof.input_structured is False:
        b.con("input", "; ".join(prof.input_evidence[:2]) or "free-text input", w_free)
    else:
        if prof.input_evidence:
            b.con("input", "input structure is mixed or unknown: " + "; ".join(prof.input_evidence[:2]), 0.15)


@register
class DeterministicDecision(Rule):
    id = "LLM-001"
    title = "Deterministic Decision Delegated to LLM"
    category = "deterministic"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or cc_procedure(step, ctx.profile(step)) or step.step_kind == StepKind.AGENT and len(step.tool_names) > 0:
                continue
            p = ctx.profile(step)
            if p.output_space != "closed" or not p.explicit_rules or len(p.labels) < 2:
                continue
            if not (p.primary in ("decide", "classify") or p.controls_branch or p.has("decide")):
                continue
            b = Builder()
            n = len(p.explicit_rules)
            b.pro("prompt_text", f"{n} explicit rule statement(s) in the prompt, e.g. \"{p.explicit_rules[0][:100]}\"", 0.55 if n >= 2 else 0.3,
                  step.location)
            b.pro("output", f"closed output: {p.labels[:8]} (sources: {p.label_sources})", 0.15)
            if p.controls_branch:
                b.pro("graph", "the output only selects a code branch", 0.15)
            mentioned = [l for l in p.labels if any(l.lower() in r.lower() for r in p.explicit_rules)]
            if mentioned:
                b.pro("prompt_text", f"rules map conditions directly to labels {mentioned[:5]}", 0.15)
            _structured_input_evidence(b, p, 0.3, 0.6)
            _common_counter(b, p)
            if re.search(r"(?i)\b(otherwise|else|in other cases|de lo contrario|en otro caso)\b[^.\n]{0,60}\b(judg|decide|use your|criterio)", step.static_text()):
                b.con("prompt_text", "fallback branch delegates to model judgment", 0.35)
            strong = p.input_structured is True and n >= 2 and not p.judgment
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.HIGH_CONFIDENCE if strong else EvidenceLevel.LIKELY,
                severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("The decision criteria are written out as explicit conditions over the input, and the output is one of a "
                           "closed set of labels. A function or decision table can evaluate those conditions exactly, without "
                           "sampling variance or per-call cost."),
                current=f"An LLM call ({step.model.raw or 'model unresolved'}) evaluates {n} written rule(s) to pick one of {p.labels[:6]}.",
                change=("Implement the rules as code (if/elif or a decision table) over the input fields. Keep the LLM only as a "
                        "fallback for inputs no rule covers, and log how often the fallback fires."),
                alternative="If some conditions need language understanding, split them: code for the explicit thresholds, a small model for the rest.",
                risk=Risk.LOW if strong else Risk.MEDIUM,
                risks=["Rules written in prose may be incomplete or ambiguous; the LLM may be silently handling unstated cases.",
                       "Label normalization (case/whitespace) must match downstream comparisons."],
                validation=FIDELITY_VALIDATION, requires_runtime=not strong, with_determinism=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, ctx.profile(step).static_tokens)
                yield f


@register
class LLMAsParser(Rule):
    id = "LLM-009"
    title = "LLM Used as Parser"
    category = "deterministic"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or cc_procedure(step, ctx.profile(step)):
                continue
            p = ctx.profile(step)
            if not p.has("extract") or p.input_structured is False:
                continue
            if p.primary not in ("extract", "format", "validate_schema", "classify", "unknown") and p.primary in (
                    "generate", "reason", "summarize", "translate", "code", "conversation"):
                continue
            b = Builder()
            b.pro("prompt_text", f"extraction requested: '{p.tasks['extract'][0][:90]}'", 0.35 if p.primary == "extract" else 0.2)
            struct_vars = [v for v in step.variables() if v.structured is True]
            if struct_vars:
                b.pro("input", f"structured inputs: {[v.name for v in struct_vars[:3]]}", 0.35)
            if any("prompt describes structured input" in e for e in p.input_evidence):
                b.pro("prompt_text", next(e for e in p.input_evidence if "prompt describes structured" in e), 0.3)
            if p.input_structured is None:
                b.con("input", "input structure not established (" + ("; ".join(p.input_evidence[:2]) or "no evidence") + ")", 0.4)
            if p.output_space in ("structured", "closed"):
                b.pro("output", f"output is {p.output_space}", 0.1)
            text = step.static_text()
            if SCANNED.search(text):
                b.con("prompt_text", f"input appears to be scanned/OCR/document text: '{SCANNED.search(text).group(0)}'", 0.7)
            _common_counter(b, p)
            strong = bool(struct_vars) and p.input_structured is True and not p.judgment
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.HIGH_CONFIDENCE if strong else EvidenceLevel.LIKELY,
                severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("The fields being extracted already exist in machine-readable input (JSON/CSV/HTML/log with a fixed "
                           "shape). A parser reads them exactly; an LLM can mis-copy numbers, drop fields or hallucinate values."),
                current="An LLM call reads structured input and returns selected fields.",
                change=("Parse the input with code (json/csv/html parser, regex for fixed-format lines) and map fields directly. "
                        "Add a schema check on the parsed result."),
                alternative="If a few fields are free text inside the structure, parse the rest and send only those fields to a small model.",
                risk=Risk.LOW if strong else Risk.MEDIUM,
                risks=["Input format may vary across sources (versions, optional fields)—the parser needs tests on real samples.",
                       "Fields that are actually free text (descriptions, notes) still need language understanding."],
                validation=FIDELITY_VALIDATION, requires_runtime=not strong, with_determinism=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens)
                yield f


@register
class LLMAsFormatter(Rule):
    id = "LLM-010"
    title = "LLM Used as Formatter"
    category = "deterministic"

    # prose-rewriting cues; "rewrite" alone is not one (the format task already requires a concrete target representation)
    TONE = re.compile(r"(?i)\b(tone|style|polish|fluent|natural|friendly|professional|rephrase|paraphrase|tono|estilo|parafrase|redacci[oó]n)\b")

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or cc_procedure(step, ctx.profile(step)):
                continue
            p = ctx.profile(step)
            if not p.has("format") or p.primary in ("translate", "summarize", "generate", "reason", "code"):
                continue
            b = Builder()
            b.pro("prompt_text", f"format conversion requested: '{p.tasks['format'][0][:90]}'", 0.55 if p.primary == "format" else 0.3)
            _structured_input_evidence(b, p, 0.25, 0.55)
            tone = self.TONE.findall(step.static_text())
            if tone:
                b.con("prompt_text", f"prose rewriting cues: {sorted(set(t.lower() for t in tone))[:4]}", 0.5)
            if p.has("translate"):
                b.con("prompt_text", "translation is involved", 0.6)
            _common_counter(b, p)
            strong = p.primary == "format" and p.input_structured is True and not tone and not p.judgment
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.HIGH_CONFIDENCE if strong else EvidenceLevel.LIKELY,
                severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("The step changes how data is presented (format, casing, layout) without changing its meaning. "
                           "Serializers and templates do this exactly and for free."),
                current="An LLM call reformats data.",
                change="Replace with a serializer/template (json/yaml/csv libraries, a Markdown table template, datetime formatting).",
                alternative="Keep the LLM only for any field that genuinely needs rewording, and template the rest.",
                risk=Risk.LOW if strong else Risk.MEDIUM,
                risks=["Check that no implicit cleanup (typo fixing, normalization) was relied upon."],
                validation=FIDELITY_VALIDATION, requires_runtime=not strong, with_determinism=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens)
                yield f


@register
class LLMForSchemaValidation(Rule):
    id = "LLM-011"
    title = "LLM Used for Schema Validation"
    category = "deterministic"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or cc_procedure(step, ctx.profile(step)):
                continue
            p = ctx.profile(step)
            if not p.has("validate_schema"):
                continue
            b = Builder()
            primary = p.primary == "validate_schema"
            b.pro("prompt_text", f"structural check requested: '{p.tasks['validate_schema'][0][:100]}'", 0.6 if primary else 0.3)
            if p.output_space == "closed":
                b.pro("output", f"verdict output {p.labels[:4]}", 0.15)
            if p.input_structured is True:
                b.pro("input", "; ".join(p.input_evidence[:1]) or "structured input", 0.15)
            _common_counter(b, p)
            strong = primary and not p.has("validate_semantic") and not p.judgment
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.HIGH_CONFIDENCE if strong else EvidenceLevel.LIKELY,
                severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("Required fields, types, formats and ranges are what JSON Schema / pydantic validate exactly. An LLM "
                           "check is probabilistic: it can pass invalid records and fail valid ones."),
                current="An LLM call judges whether data has the required structure.",
                change="Express the constraints as a JSON Schema or pydantic model and validate in code; report the exact failing paths.",
                alternative="If some checks are semantic (plausibility, consistency with text), keep those in a separate, narrower LLM step.",
                risk=Risk.LOW if strong else Risk.MEDIUM,
                risks=["The prompt may contain implicit semantic checks; list every rule before replacing."],
                validation=FIDELITY_VALIDATION, requires_runtime=not strong, with_determinism=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens)
                yield f


@register
class DeterministicComputation(Rule):
    id = "LLM-026"
    title = "Deterministic Computation Delegated to LLM"
    category = "deterministic"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or cc_procedure(step, ctx.profile(step)):
                continue
            p = ctx.profile(step)
            if p.primary != "compute":
                continue
            b = Builder()
            b.pro("prompt_text", f"arithmetic/aggregation requested: '{p.tasks['compute'][0][:90]}'", 0.55)
            _structured_input_evidence(b, p, 0.3, 0.5)
            if p.output_space in ("structured", "closed") or p.short_output:
                b.pro("output", "numeric/short output", 0.1)
            _common_counter(b, p)
            f = finding(
                self, ctx, step, b, CLASS_B, severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning="Arithmetic over known values is exact in code; LLMs make arithmetic slips, especially with many items or decimals.",
                current="An LLM call computes totals/aggregates.",
                change="Compute in code (Decimal for money) and, if needed, let the LLM only phrase the result.",
                risk=Risk.LOW, risks=["Rounding and currency rules must be made explicit in code."],
                validation=FIDELITY_VALIDATION, requires_runtime=p.input_structured is not True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens)
                yield f


def _root_name(v) -> str:
    """`row["department_code"]` -> department_code; `order.country` -> country."""
    names = re.findall(r"[A-Za-z_]\w*", v.expression or v.name)
    quoted = re.findall(r"[\"']([A-Za-z_]\w*)[\"']", v.expression or v.name)
    return (quoted or names or [v.name])[-1]


@register
class Precomputation(Rule):
    id = "LLM-020"
    title = "Candidate for Precomputation"
    category = "deterministic"

    CATEGORICAL = re.compile(r"(?i)(^|_)(code|codigo|category|categoria|type|tipo|kind|status|estado|country|pais|language|lang|locale|"
                             r"idioma|currency|moneda|department|dept|departamento|region|tier|plan|segment|segmento|level|nivel|channel|canal)$")
    VARIETY = re.compile(r"(?i)\b(random|different each time|vary|varied|surprise|fresh|unique|new idea|aleatori|distint[oa] cada|variad|sorprend)")

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.framework == "claude_code" or step.step_kind == StepKind.AGENT or step.tool_names:
                continue
            if not step.prompt:
                continue
            dynamic = [v for v in step.variables() if v.source != VarSource.CONSTANT]
            p = ctx.profile(step)
            if not p.prompt_resolved:
                continue
            b = Builder()
            finite = None
            if not dynamic:
                b.pro("ir", "every prompt part is a compile-time constant: the request is identical on every call", 0.75, step.location)
            elif len(dynamic) == 1 and dynamic[0].domain and len(dynamic[0].domain) <= 50:
                finite = dynamic[0]
                b.pro("ir", f"the only runtime input is `{_root_name(finite)}`, typed with {len(finite.domain)} possible values "
                            f"{finite.domain[:6]}", 0.5, step.location)
                if p.output_space == "open" and not p.has("reason"):
                    b.pro("profile", "output depends only on that value (descriptive text per value)", 0.1)
            elif len(dynamic) == 1 and dynamic[0].structured is not False and self.CATEGORICAL.search(_root_name(dynamic[0])):
                finite = dynamic[0]
                b.pro("ir", f"the only runtime input is `{_root_name(finite)}`, a categorical-looking value (finite domain inferred from its name)", 0.4, step.location)
                if p.output_space == "open" and not p.has("reason"):
                    b.pro("profile", "output depends only on that value (descriptive text per category)", 0.1)
            else:
                continue
            mult = ctx.graph.multiplicity(step.id)
            if finite is not None and not finite.domain and not (mult.in_loop or step.attrs.get("entrypoints")):
                continue  # domain only guessed from the name and one call per run: nothing to amortize
            if mult.in_loop or step.attrs.get("entrypoints"):
                b.pro("graph", f"called repeatedly ({mult.per_execution}; entrypoints={step.attrs.get('entrypoints')})", 0.2)
            if step.temperature is not None and step.temperature > 0.3:
                b.con("params", f"temperature={step.temperature}: output variety may be intended", 0.35)
            if self.VARIETY.search(step.static_text()):
                b.con("prompt_text", f"prompt asks for variety: '{self.VARIETY.search(step.static_text()).group(0)}'", 0.7)
            if finite is not None:
                f = finding(
                    self, ctx, step, b, CLASS_B, cap=EvidenceLevel.LIKELY, severity=severity_for(ctx, step, Severity.LOW),
                    reasoning=(f"The prompt varies only with `{_root_name(finite)}`. If that value comes from a small known set "
                               "(catalog codes, categories), the answer for each value can be generated once and looked up."),
                    current=f"One LLM call per occurrence of `{_root_name(finite)}`, repeated for values already seen.",
                    change="Generate the output once per distinct value (offline over the catalog, or memoize by value at runtime) and look it up.",
                    alternative="Exact-match cache keyed on (model, prompt) with no expiry.",
                    risk=Risk.LOW, risks=["Confirm the domain is small and stable; free-form values defeat the lookup."],
                    validation="Count distinct values in data or traces; compare stored outputs with fresh generations for a sample.",
                    requires_runtime=True,
                )
                if f:
                    f.impact.static_potential = potential(ctx, step, None, None, "calls reduced to one per distinct value")
                    yield f
                continue
            f = finding(
                self, ctx, step, b, CLASS_B, severity=severity_for(ctx, step, Severity.LOW),
                reasoning="With no runtime inputs the model receives the same request every time; its answer can be generated once and stored.",
                current="An LLM call with a fully static prompt runs at request time.",
                change="Generate the output offline (build step or first run), review it, and load it from a file/constant; regenerate when the prompt changes.",
                alternative="Exact-match cache keyed on (model, prompt hash) if offline generation is impractical.",
                risk=Risk.LOW, risks=["If sampling variety is desired, precompute a pool of N outputs instead of one."],
                validation="Diff the stored output against fresh generations on k≥5 runs to confirm nothing request-specific is lost.",
                requires_runtime=False,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens, "removes the call at request time")
                yield f


@register
class DeterministicToolCalling(Rule):
    id = "LLM-017"
    title = "Deterministic Tool Calling Opportunity"
    category = "deterministic"

    ALWAYS = re.compile(r"(?i)\b(always|first|before (answering|responding|anything)|must (first )?(call|use|invoke)|siempre|primero|antes de responder)\b[^.\n]{0,40}\b(call|use|invoke|run|llama|usa|invoca|ejecuta)\s+(the\s+)?`?(\w[\w.-]*)`?")
    OUTPUT_TOOL = re.compile(r"(?i)^(record|extract|output|respond|answer|classify|format|submit|return|emit|structured|json|result)")
    INVESTIGATE = re.compile(r"(?i)\b(explor\w*|investigat\w*|comprehension|understand\w*|map (the|a) code\s?base|trace how|"
                             r"find every|where does|root cause|diagnos\w*|research\w*|investiga\w*|explora\w*|diagn[oó]stic\w*)\b")

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            b = Builder()
            tc = step.tool_choice
            forced = tc and tc not in ("auto", "none", "any", "required")
            if forced:
                if self.OUTPUT_TOOL.match(tc) and len(step.tool_names) <= 1:
                    continue  # forced tool used as a structured-output channel, not an action
                b.pro("params", f"tool_choice forces the model to call '{tc}' on every request", 0.6, step.location)
            m = self.ALWAYS.search(step.static_text())
            if m:
                b.pro("prompt_text", f"instructions fix the call: '{m.group(0)[:90]}'", 0.45)
            cmds = step.attrs.get("fixed_commands") or []
            cc = step.framework == "claude_code"
            if cc and len(cmds) >= 2:
                b.pro("prompt_text", f"agent instructions are a fixed command sequence: {cmds[:5]}", 0.45)
                interpretive = sorted(p.tasks.keys() & {"reason", "generate", "summarize", "classify", "decide", "validate_semantic", "extract"})
                inv = self.INVESTIGATE.search(step.static_text())
                if interpretive or p.judgment or inv:
                    why = interpretive or ("judgment cues" if p.judgment else f"investigative role: '{inv.group(0)}'")
                    b.con("prompt_text", f"the agent must also interpret the results ({why})", 0.4)
                else:
                    b.pro("prompt_text", "no interpretation task beyond running/reporting commands", 0.2)
                body_tokens = int(step.attrs.get("body_tokens") or 0)
                if body_tokens > 600:
                    b.con("prompt_text", f"long body (~{body_tokens} tokens): the commands are likely reference snippets "
                                         "among steps that need judgment", 0.4)
                chosen = [c for c in cmds if re.search(r"<[^<>]+>|…|\.\.\.|\{[^{}]+\}", c)]
                if len(chosen) * 2 >= len(cmds):
                    b.con("prompt_text", f"{len(chosen)}/{len(cmds)} commands take arguments the model fills in: {chosen[:2]}", 0.35)
            if not b.evidence:
                continue
            _common_counter(b, p)
            f = finding(
                self, ctx, step, b, CLASS_B, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("When a tool call is invariant (always the same tool, or a fixed sequence), deciding it with the model "
                           "adds a model turn and a chance to skip or reorder the call, without adding information."),
                current=("Claude Code agent that executes a fixed command sequence." if cc and cmds else
                         "The model is made to choose a tool call that is always the same."),
                change=("Run the fixed calls in code (or a script/hook) and pass their results to the model only if interpretation "
                        "is needed; for a pure command sequence, a script with exit codes replaces the agent."),
                alternative="Keep the LLM for argument generation only, invoking the tool deterministically with the produced arguments.",
                risk=Risk.MEDIUM,
                risks=["Arguments may depend on the input; only the *choice* of tool is invariant.",
                       "Agents may handle error recovery between commands that a naive script would not."],
                validation="Compare task success and turn count with the call hard-wired vs model-chosen on recorded tasks.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, None, None, "removes ≥1 model turn per run")
                yield f
