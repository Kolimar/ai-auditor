"""Validation-related rules: redundant LLM validators, retries in place of validation, free-text parsing."""

from __future__ import annotations

from typing import Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import EvidenceLevel, Finding, Risk, Severity
from ai_auditor.ir.model import Enforcement, LLMStep, OutputKind
from ai_auditor.rules._common import CLASS_B, CLASS_C, Builder, finding, potential, severity_for, skip_step

STRUCTURED_PROVIDERS = {"anthropic", "openai", "google", "litellm", "langchain", "openai_agents", "pydantic_ai"}


def _upstream_guarantee(ctx: AnalysisContext, step: LLMStep) -> list[str]:
    """Mechanisms that already guarantee the structure of `step`'s output."""
    out = []
    if step.output.enforcement == Enforcement.CONSTRAINED and step.output.kind in (OutputKind.SCHEMA, OutputKind.ENUM, OutputKind.JSON, OutputKind.TOOL_CALL):
        out.append(f"constrained decoding ({step.output.kind.value}{' ' + step.output.schema_name if step.output.schema_name else ''})")
    for v in ctx.graph.validators_of(step.id):
        if v.attrs.get("kind") == "schema":
            out.append(f"code schema validation ({v.attrs.get('detail')}) at {v.location}")
    return out


@register
class RedundantLLMValidation(Rule):
    id = "LLM-002"
    title = "Redundant LLM Validation"
    category = "deterministic"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            if not (p.has("validate_schema") or p.primary in ("validate_schema",) or
                    any(k in step.static_text().lower() for k in ("validate", "verify", "check that", "valida", "verifica", "comprueba"))):
                continue
            producers = [n for n in ctx.graph.producers(step.id) if isinstance(n, LLMStep)]
            guarantees: list[tuple[LLMStep, list[str]]] = [(u, g) for u in producers if (g := _upstream_guarantee(ctx, u))]
            if not guarantees:
                continue
            b = Builder()
            for u, g in guarantees:
                b.pro("graph", f"validates output of '{u.name}', which is already guaranteed by {', '.join(g)}", 0.45, u.location)
            if p.has("validate_schema"):
                b.pro("prompt_text", f"checks structural properties: '{p.tasks['validate_schema'][0][:90]}'", 0.3)
            if p.has("validate_semantic"):
                b.con("prompt_text", f"also checks semantics not covered by a schema: '{p.tasks['validate_semantic'][0][:80]}'", 0.75)
            if p.judgment:
                b.con("prompt_text", f"judgment cues {p.judgment[:3]}", 0.3)
            if p.risk_domains:
                b.con("prompt_text", f"risk domain {sorted(p.risk_domains)}", 0.2)
            structural_only = p.has("validate_schema") and not p.has("validate_semantic") and not p.judgment
            f = finding(
                self, ctx, step, b, CLASS_C, cap=EvidenceLevel.HIGH_CONFIDENCE if structural_only else EvidenceLevel.LIKELY,
                severity=severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("The properties this LLM step checks are already enforced upstream. A second, probabilistic check adds a "
                           "call and latency and cannot catch what the deterministic mechanism already rules out."),
                current=f"LLM validation of the output of {[u.name for u, _ in guarantees]}.",
                change="Remove the LLM validation step and rely on the existing schema enforcement; keep a code-level assertion for business rules.",
                alternative="If semantic checks are needed, rewrite this step to check only those, with an explicit rubric.",
                risk=Risk.LOW if structural_only else Risk.MEDIUM,
                risks=["The validator might also catch semantic errors nobody listed; inspect its historical rejections first."],
                validation=("From traces: count how often this validator rejected an output. Zero rejections in n runs bounds the "
                            "rejection rate below 3/n (95%). Then A/B without the step on a held-out set."),
                requires_runtime=not structural_only, with_determinism=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 1.0, p.static_tokens)
                yield f


@register
class RetryInsteadOfValidation(Rule):
    id = "LLM-008"
    title = "Retry Instead of Validation"
    category = "reliability"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            retries = ctx.graph.retry_policies_of(step.id)
            if not retries:
                continue
            b = Builder()
            constrained = step.output.enforcement == Enforcement.CONSTRAINED
            parsed = step.attrs.get("parsed_as_json") or step.attrs.get("parsed_with_regex")
            unbounded = any(r.attrs.get("unbounded") for r in retries)
            relevant = False
            for r in retries:
                trig = r.attrs.get("trigger")
                if trig == "format":
                    b.pro("code", f"retries on parse/validation errors {r.attrs.get('exceptions')} ({r.attrs.get('mechanism')}, max={r.attrs.get('max_attempts')})", 0.6, r.location)
                    relevant = True
                elif trig in ("mixed", "any") and parsed:
                    b.pro("code", f"retries on {r.attrs.get('exceptions') or 'any exception'} around output parsing", 0.35, r.location)
                    relevant = True
            if not relevant:
                continue
            if parsed:
                b.pro("code", "the model output is parsed as JSON/regex after a free-text generation", 0.2)
            if constrained:
                b.con("ir", "output already uses constrained decoding: retries are re-asking for semantic validation", 0.6)
            if (step.framework or "") not in STRUCTURED_PROVIDERS:
                b.con("ir", f"structured outputs support for framework '{step.framework}' unknown", 0.2)
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.LIKELY,
                severity=Severity.HIGH if unbounded else severity_for(ctx, step, Severity.MEDIUM),
                reasoning=("Each format failure costs a full extra call (and latency). Schema-constrained decoding makes the "
                           "output syntactically valid by construction, so these retries disappear. Effects of constrained "
                           "decoding on reasoning quality are disputed, so quality is checked separately."),
                current="Free-text generation, then parse; on failure the call is repeated." + (" The retry has no attempt limit." if unbounded else ""),
                change=("Use the provider's structured outputs (JSON Schema / response_format / output_config.format / output_type) "
                        "and validate once; cap remaining retries at 1–2 and alert on exhaustion."),
                alternative="Deterministic repair (strip code fences, json-repair) before re-asking the model.",
                risk=Risk.LOW, risks=["Very complex schemas may not be supported by constrained decoding."],
                validation="From traces: retry rate by exception type; after the change, compare validity rate, retries/call and task quality on the same inputs.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, None, None, "removes retry calls caused by malformed output")
                yield f


@register
class FreeTextParsedAsStructure(Rule):
    id = "LLM-022"
    title = "Free-Text Output Parsed as Structure"
    category = "reliability"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.output.enforcement == Enforcement.CONSTRAINED:
                continue
            if not (step.attrs.get("parsed_as_json") or step.attrs.get("parsed_with_regex")):
                continue
            if any(r.attrs.get("trigger") in ("format", "mixed", "any") for r in ctx.graph.retry_policies_of(step.id)):
                continue  # reported as LLM-008, which subsumes this
            b = Builder()
            how = "json.loads" if step.attrs.get("parsed_as_json") else "regex"
            b.pro("code", f"output of a free-text generation is parsed with {how}", 0.55, step.location)
            if "json" in step.static_text().lower():
                b.pro("prompt_text", "the prompt asks for JSON in prose instead of enforcing it", 0.2)
            if step.attrs.get("json_parse_guarded"):
                b.pro("code", "parsing is wrapped in try/except, i.e. failures are expected", 0.1)
            if (step.framework or "") not in STRUCTURED_PROVIDERS:
                b.con("ir", f"structured outputs support for '{step.framework}' unknown", 0.2)
            f = finding(
                self, ctx, step, b, CLASS_B, cap=EvidenceLevel.LIKELY, severity=severity_for(ctx, step, Severity.LOW),
                reasoning="Asking for JSON in the prompt does not guarantee it; malformed output becomes exceptions or silent fallbacks downstream.",
                current=f"Prompt-only JSON, parsed with {how}.",
                change="Enforce the shape with structured outputs (JSON Schema / pydantic output type) and validate the parsed object.",
                risk=Risk.LOW, risks=["Check provider support for the schema features you use."],
                validation="Measure parse-failure rate from traces before/after; check task quality on a fixed sample.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, None, "reliability: removes parse failures and their fallbacks")
                yield f
