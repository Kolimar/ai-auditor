"""Brief for the AI agent that runs the auditor (Claude Code, Devin, Cursor...).

On unseen systems the static analysis finds about half of the labelled cases; most misses are instructions whose
wording the task lexicon does not recognise. An agent running the auditor can read those instructions itself. The
brief lists the steps the analysis could not settle (no evidence either way, or an LLM-use justification that may be
wrong), the weakest recommendations and a map of the workflow (reporting/workflow_map.py: what each step loads,
repeated text, code the auditor does not parse, external pieces), with a short rubric. It asks for findings labelled as
the agent's own judgement, written as JSON so that `ai-auditor report` can check every quote against the files: they
are reported apart and never count as measurements.
"""

from __future__ import annotations

from typing import Any

from ai_auditor.analyzers.finding import EvidenceLevel, Finding
from ai_auditor.reporting.workflow_map import build_map, render_map_markdown

RUBRIC = [
    ("LLM-001", "a decision made with fixed rules (thresholds, tables, if/then) -> code",
     "judgement with fuzzy or open criteria"),
    ("LLM-009", "parsing input that already has a fixed structure (JSON, CSV, log lines, fixed layouts) -> a parser",
     "free text, scans, OCR"),
    ("LLM-010", "pure format conversion (JSON to CSV, Markdown table, dates, casing) -> a serializer or template",
     "rewriting tone or content"),
    ("LLM-011", "checking required fields, types or ranges -> a schema validator", "judging content quality"),
    ("LLM-026", "exact arithmetic over known values (totals, taxes, unit conversions, date differences) -> code",
     "explaining a result computed elsewhere"),
    ("LLM-017", "the same commands in the same order whatever the content -> a script or hook",
     "reference snippets, alternatives, or commands chosen from what the agent finds"),
    ("LLM-020", "the same answer for a small, finite set of inputs -> a precomputed table", "inputs that vary freely"),
    ("LLM-003/018", "a large model chosen for a narrow task (few labels, field extraction) -> a smaller model",
     "files that do not choose the model"),
    ("LLM-004", "large context loaded on every request that the task does not need (long rules, long descriptions)",
     "context that is the subject of the task"),
    ("LLM-006", "two agents, skills or playbooks with the same role -> keep one", "similar wording, different jobs"),
    ("LLM-022", "JSON requested in prose and then parsed -> structured outputs", "output read by a person"),
    ("LLM-011", "the instructions ask the model to check what a sensor, hook, validator or script already checks -> drop "
                "it from the prompt", "a check the code cannot do"),
    # across the steps of a workflow (phases, agents calling agents, skills calling tools)
    ("LLM-005", "the same rule or text written in several files that load together (agent, stage, knowledge), or the "
                "same large text sent again to several phases -> keep it in one place, pass a summary or a reference",
     "each step needing a different part"),
    ("LLM-012", "an agent or phase whose only job is handing the work to another -> call that one directly",
     "a hop that isolates a large exploration or restricts tools"),
    ("LLM-025", "independent steps run one after another -> run them in parallel", "steps that use each other's output"),
    ("LLM-014", "work repeated on every run (cloning, installing, re-reading or re-summarising the same thing) -> "
                "cache it or do it once", "inputs that change on every run"),
    ("LLM-015/016", "whole repos, folders or documents put into context when a search or a slice would do",
     "a task whose subject is the whole document"),
    ("LLM-021", "a loop with no cap on turns, time or budget -> add one", "a loop waiting for a person"),
]

INSTRUCTIONS = [
    "Start from 'Workflow map': what each step loads, text repeated across files, code the auditor does not parse and "
    "external pieces. Those are measured facts: cite them as evidence.",
    "For each step under 'To review', open the file at that location, read the instructions and decide whether one "
    "of the patterns below applies. Report it only when the text shows it clearly, and quote the sentence.",
    "For each recommendation under 'To double-check', confirm or discard it with a one-line reason.",
    "Code that imports an LLM SDK is a step the auditor could not parse: read it with the same patterns. Code without "
    "one is deterministic: check whether the instructions ask the model to redo what that code already does.",
    "'External pieces' come from outside the audited folder. When the user asks for the whole workflow, fetch the "
    "ones that may hold agent instructions or LLM calls (skills, agents, prompts, MCP servers, tools built on an LLM; "
    "not well-known CLIs) read-only into a temporary folder, run the auditor on each with --for-agent, and then review "
    "the chain as a whole with the patterns below.",
    "Label your findings 'agent review', apart from the auditor's. Use HYPOTHESIS, or LIKELY when the instruction text "
    "or a measured fact leaves no doubt; never PROVEN or HIGH_CONFIDENCE, which need an experiment or structural "
    "evidence.",
    "Write the review as JSON (format below) and run `ai-auditor report PATH --review FILE`: it checks every quote "
    "against its file and renders the final report. Fix or drop what it marks as not verified.",
    "Open-ended generation, judgement under ambiguity, writing code and research do need an LLM: do not report them.",
    "Do not estimate savings in money or tokens beyond the measured ones; say what would go away (for example, one LLM "
    "call per run, or ~300 tokens loaded twice).",
    "Do not modify any file unless the user asks.",
]

ANSWER_FORMAT = """{
  "findings": [
    {"component": "step or file name", "file": "path relative to the audited folder", "rule": "LLM-005",
     "quote": "a sentence copied exactly from the file", "level": "HYPOTHESIS or LIKELY", "scope": "step or workflow",
     "change": "what to do", "also_in": ["other files with the same text, for repeated text"]}
  ],
  "confirmed": ["id of a tool recommendation you confirm"],
  "dismissed": [{"id": "id of a tool recommendation", "reason": "why it does not apply"}],
  "external": [{"ref": "an external piece", "audited": true, "notes": "what you found, or why you skipped it"}],
  "llm_justified": ["what does need an LLM, one line each"]
}"""


def _top_reason(f: Finding) -> str:
    pros = sorted((e for e in f.evidence if e.weight > 0), key=lambda e: -e.weight)
    text = (pros[0].description if pros else f.title).removesuffix(" []")
    return text if len(text) <= 120 else text[:117] + "..."


def build_brief(res: Any, findings: list[Finding], limit: int = 50) -> dict[str, Any]:
    """`res` is an AuditResult; `findings` the ones shown in the report."""
    steps = {s.id: s for s in res.ir.llm_steps() if not s.attrs.get("dead_code") and not s.attrs.get("non_production")}
    covered = {f.component_id for f in res.findings if f.actionable} | {r for f in res.findings if f.actionable for r in f.related}
    justified = {f.component_id: f for f in res.justified}
    unassessed, weak = [], []
    for sid, s in steps.items():
        if sid in covered:
            continue
        p = res.ctx.profile(s)
        item = {
            "component": s.name,
            "location": f"{s.location.file}:{s.location.line}" if s.location else "",
            "framework": s.framework,
            "kind": s.attrs.get("cc_type") or s.step_kind.value,
            "task": p.primary,
            "output": p.output_space,
        }
        if sid in justified:
            item["auditor"] = f"LLM use justified: {_top_reason(justified[sid])}"
            weak.append((justified[sid].confidence, item))
        else:
            item["auditor"] = "no evidence either way"
            unassessed.append(item)
    wmap = build_map(res)
    for c in wmap["code"]:
        if c["llm"]:
            unassessed.append({"component": c["file"], "location": f"{c['file']}:1", "framework": c["lang"],
                               "kind": "code (not parsed)", "auditor": f"imports {', '.join(c['llm'])}",
                               "task": "unknown", "output": "unknown"})
    review = unassessed + [item for _, item in sorted(weak, key=lambda t: t[0])]
    check = [
        {"id": f.id, "rule": f.rule_id, "component": f.component,
         "location": f"{f.location.file}:{f.location.line}" if f.location else "", "title": f.title}
        for f in findings if f.actionable and not f.superseded_by and f.level == EvidenceLevel.HYPOTHESIS
    ]
    return {
        "instructions": INSTRUCTIONS,
        "rubric": [{"rule": r, "is": a, "is_not": b} for r, a, b in RUBRIC],
        "review": review[:limit],
        "review_omitted": max(0, len(review) - limit),
        "double_check": check,
        "map": wmap,
        "external": wmap["external"],
        "answer_format": ANSWER_FORMAT,
    }


def render_brief_markdown(brief: dict[str, Any]) -> str:
    out = ["", "## Brief for the agent running the auditor", "",
           "The static analysis finds about half of what a reviewer would. You can read the instructions it could not "
           "settle. Findings from this review are your judgement, not measurements.", ""]
    out += [f"{i}. {line}" for i, line in enumerate(brief["instructions"], 1)]
    out += render_map_markdown(brief["map"])
    out += ["", "### Patterns", "", "| rule | is | is not |", "|---|---|---|"]
    out += [f"| {r['rule']} | {r['is']} | {r['is_not']} |" for r in brief["rubric"]]
    out += ["", f"### To review ({len(brief['review'])})", ""]
    if brief["review"]:
        out += ["| component | location | kind | auditor's view | task / output |", "|---|---|---|---|---|"]
        out += [f"| {s['component']} | `{s['location']}` | {s['framework']} {s['kind']} | {s['auditor']} | "
                f"{s['task']} / {s['output']} |" for s in brief["review"]]
    else:
        out.append("Nothing: every step has a recommendation.")
    if brief["review_omitted"]:
        out += ["", f"{brief['review_omitted']} more not listed: run the auditor on a subfolder to see them."]
    out += ["", f"### To double-check ({len(brief['double_check'])})", ""]
    if brief["double_check"]:
        out += [f"- `{c['id']}` {c['rule']} on {c['component']}" + (f" (`{c['location']}`)" if c["location"] else "")
                + f": {c['title']}" for c in brief["double_check"]]
    else:
        out.append("No HYPOTHESIS recommendations.")
    out += ["", "### Answer format", "", "Write this JSON to a file and run `ai-auditor report PATH --review FILE -f markdown`:",
            "", "```json", brief["answer_format"], "```", ""]
    return "\n".join(out)
