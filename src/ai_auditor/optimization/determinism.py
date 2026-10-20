"""Determinism score: how appropriate it looks to replace an LLM step with deterministic code.

Explainable additive heuristic (base 50, contributions clamped to 0..100). It is
NOT ground truth: there is no validated task-complexity taxonomy in the
literature. Each contribution is listed with its evidence,
and the golden set measures how well the bands separate real cases.

Bands: 0-30 generative reasoning · 31-60 model-dependent · 61-80 small-model
candidate · 81-95 strong deterministic candidate · 96-100 deterministic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ai_auditor.ir.model import LLMStep, OutputKind, StepKind

if TYPE_CHECKING:
    from ai_auditor.optimization.profile import TaskProfile

BANDS = [(30, "generative"), (60, "model_dependent"), (80, "small_model_candidate"), (95, "strong_deterministic_candidate"),
         (100, "deterministic")]


def band(score: float) -> str:
    for upper, name in BANDS:
        if score <= upper:
            return name
    return "deterministic"


def determinism_score(p: TaskProfile, step: LLMStep) -> dict[str, Any]:
    parts: list[tuple[str, float, str]] = []

    def add(name: str, pts: float, why: str) -> None:
        parts.append((name, pts, why))

    if not p.prompt_resolved:
        return {"score": None, "band": "insufficient_evidence", "contributions": [],
                "note": "prompt instructions could not be resolved statically"}
    if p.output_space == "closed":
        n = len(p.labels)
        add("closed_output", 12 if n <= 12 else 6, f"closed output ({n} labels: {p.labels[:6]}) from {p.label_sources}")
    elif p.output_space == "structured":
        add("structured_output", 4, "structured output contract")
    elif p.output_space == "open":
        add("open_output", -25, "open-ended output")
    if step.output.kind in (OutputKind.ENUM, OutputKind.BOOLEAN):
        add("enforced_labels", 5, f"labels enforced by output contract ({step.output.schema_name or step.output.kind.value})")
    if p.controls_branch:
        add("drives_branch", 5, "output only drives a code branch")
    rules = len(p.explicit_rules)
    if rules >= 2:
        add("explicit_rules", 20, f"{rules} explicit rule statements, e.g. '{p.explicit_rules[0][:80]}'")
    elif rules == 1:
        add("explicit_rules", 8, f"1 explicit rule statement: '{p.explicit_rules[0][:80]}'")
    if p.input_structured is True:
        add("structured_input", 15, "; ".join(p.input_evidence[:2]) or "structured input")
    elif p.input_structured is False:
        add("free_text_input", -20, "; ".join(p.input_evidence[:2]) or "free-text input")
    mech = [t for t in ("format", "validate_schema", "compute") if p.has(t)]
    if mech and p.primary in mech:
        add("mechanical_task", 25, f"primary task is mechanical ({p.primary}): '{p.tasks[p.primary][0][:80]}'")
    elif mech:
        add("mechanical_subtask", 8, f"mechanical sub-task present ({mech[0]})")
    if p.primary == "extract" and p.input_structured is True:
        add("parse_structured", 15, "extraction from structured input")
    open_tasks = [t for t in ("generate", "reason", "summarize", "translate", "code", "conversation") if p.has(t)]
    if open_tasks and p.primary in open_tasks:
        add("generative_task", -35, f"primary task is {p.primary}: '{p.tasks[p.primary][0][:80]}'")
    elif open_tasks:
        add("generative_subtask", -10, f"also asks to {open_tasks[0]}")
    if p.has("validate_semantic"):
        add("semantic_validation", -20, f"semantic verification: '{p.tasks['validate_semantic'][0][:80]}'")
    if p.judgment:
        add("judgment_markers", -min(30, 8 * len(p.judgment)), f"judgment cues: {p.judgment[:3]}")
    if p.reasoning_requested and p.reasoning_consumed is not False:
        add("reasoning", -10, f"reasoning requested: {p.reasoning_requested[0][:60]}")
    if step.step_kind == StepKind.AGENT and len(step.tool_names) > 2:
        add("tool_orchestration", -10, f"agent orchestrates {len(step.tool_names)} tools")
    if p.few_shot >= 3 and p.output_space == "closed":
        add("few_shot_consistency", 5, f"{p.few_shot} few-shot examples with closed outputs (distillation data)")
    score = max(0.0, min(100.0, 50 + sum(pts for _, pts, _ in parts)))
    return {"score": round(score), "band": band(score),
            "contributions": [{"feature": n, "points": pts, "evidence": why} for n, pts, why in parts],
            "note": "heuristic; see calibration in evaluation report"}
