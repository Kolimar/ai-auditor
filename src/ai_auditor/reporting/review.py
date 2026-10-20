"""Check the agent's review against the files and render the final report.

The agent that ran ``analyze --for-agent`` writes its review as JSON (agent_brief.ANSWER_FORMAT). Every quote is looked
up in its file (case, whitespace and Markdown emphasis ignored) and gets its line number; for repeated text the other
files may hold a reworded copy (80% of the words). Quotes that are not found, unknown files or rules, levels an agent
review cannot have and unknown recommendation ids are marked as not verified. The report puts the auditor's
recommendations, the agent's verified findings, the workflow map and the external pieces in one fixed structure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ai_auditor.analyzers.finding import Finding
from ai_auditor.config import UsageError
from ai_auditor.reporting.workflow_map import render_map_markdown

AGENT_LEVELS = ("HYPOTHESIS", "LIKELY")


def load_review(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"cannot read the review {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("findings", []), list):
        raise UsageError(f"{path}: expected an object with a 'findings' list (see the brief's answer format)")
    return data


def _norm(text: str) -> str:
    text = re.sub(r"[*_`]+", "", text.lower())
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip(" .;:-")


def _locate(lines: list[str], quote: str) -> int | None:
    """Line where the quote starts; a quote may skip text with '...'."""
    parts = [p for p in (_norm(x) for x in re.split(r"\.\.\.|…", quote)) if len(p) >= 8] or [_norm(quote)]
    if not parts[0]:
        return None
    normed = [_norm(line) for line in lines]
    starts, pos = [], 0
    for n in normed:
        starts.append(pos)
        pos += len(n) + 1
    full = " ".join(normed)
    at = full.find(parts[0])
    if at < 0:
        return None
    cursor = at + len(parts[0])
    for p in parts[1:]:
        cursor = full.find(p, cursor)
        if cursor < 0:
            return None
    return max(i for i, s in enumerate(starts) if s <= at) + 1


def _locate_similar(lines: list[str], quote: str) -> int | None:
    exact = _locate(lines, quote)
    if exact:
        return exact
    words = set(re.findall(r"\w+", quote.lower()))
    if len(words) < 5:
        return None
    for size in (1, 2, 3):  # one line first, then a sentence wrapped over two or three
        for i in range(len(lines)):
            if len(words & set(re.findall(r"\w+", " ".join(lines[i:i + size]).lower()))) >= 0.8 * len(words):
                return i + 1
    return None


def verify_review(res: Any, review: dict[str, Any], findings: list[Finding], wmap: dict[str, Any]) -> dict[str, Any]:
    from ai_auditor.analyzers.engine import load_rules  # noqa: PLC0415

    root = Path(res.ir.root)
    base = root.parent if root.is_file() else root
    rules = set(load_rules()) | {"LLM-000"}
    cache: dict[str, list[str] | None] = {}

    def lines_of(rel: str) -> list[str] | None:
        if rel not in cache:
            p = (base / rel).resolve()
            cache[rel] = p.read_text(errors="replace").splitlines() if p.is_file() and base in (p, *p.parents) else None
        return cache[rel]

    out = []
    for i, f in enumerate(review.get("findings", []), 1):
        if not isinstance(f, dict):
            continue
        problems: list[str] = []
        rel = re.sub(r"^\./", "", str(f.get("file") or "").strip())
        rel = rel.split(":")[0] if re.search(r":\d+$", rel) else rel
        lines = lines_of(rel) if rel else None
        if lines is None:
            problems.append(f"file not found in the audited folder: '{rel}'" if rel else "no file")
        rule = str(f.get("rule") or "").strip()
        unknown = [r for r in re.findall(r"LLM-\d{3}", rule) if r not in rules]
        if not rule:
            problems.append("no rule")
        elif unknown:
            problems.append(f"unknown rule {', '.join(unknown)}")
        level = str(f.get("level") or "HYPOTHESIS").upper()
        if level not in AGENT_LEVELS:
            problems.append(f"level {level} needs an experiment or structural evidence: shown as LIKELY")
            level = "LIKELY"
        quote = str(f.get("quote") or "").strip()
        line = _locate(lines, quote) if lines is not None and quote else None
        if not quote:
            problems.append("no quote")
        elif lines is not None and line is None:
            problems.append("quote not found in the file")
        also = []
        for other in f.get("also_in") or []:
            orel = re.sub(r"^\./", "", str(other).split(":")[0] if re.search(r":\d+$", str(other)) else str(other))
            olines = lines_of(orel)
            oline = _locate_similar(olines, quote) if olines is not None and quote else None
            also.append({"file": orel, "line": oline})
            if oline is None:
                problems.append(f"text not found in {orel}")
        out.append({"n": i, "component": str(f.get("component") or ""), "file": rel, "line": line, "rule": rule,
                    "quote": quote, "level": level, "scope": "workflow" if f.get("scope") == "workflow" else "step",
                    "change": str(f.get("change") or ""), "also_in": also, "verified": not problems, "problems": problems})

    tool = {f.id: f for f in findings if f.actionable and not f.superseded_by}
    errors = []
    confirmed = []
    for fid in review.get("confirmed") or []:
        (confirmed if fid in tool else errors).append(fid if fid in tool else f"confirmed id not found: {fid}")
    dismissed = {}
    for d in review.get("dismissed") or []:
        fid = d.get("id") if isinstance(d, dict) else d
        if fid in tool:
            dismissed[fid] = str(d.get("reason") or "") if isinstance(d, dict) else ""
        else:
            errors.append(f"dismissed id not found: {fid}")
    notes = {str(e.get("ref")): e for e in review.get("external") or [] if isinstance(e, dict)}
    external = [{**e, "audited": bool(notes.get(e["ref"], {}).get("audited")), "notes": str(notes.get(e["ref"], {}).get("notes") or "")}
                for e in wmap["external"]]
    known = {e["ref"] for e in wmap["external"]}
    external += [{"kind": "other", "ref": ref, "used_by": "", "location": "", "audited": bool(e.get("audited")),
                  "notes": str(e.get("notes") or "")} for ref, e in notes.items() if ref not in known]
    return {"findings": out, "confirmed": confirmed, "dismissed": dismissed,
            "unreviewed": [fid for fid in tool if fid not in confirmed and fid not in dismissed],
            "external": external, "llm_justified": [str(x) for x in review.get("llm_justified") or []], "errors": errors}


_RANK = {"LIKELY": 2, "HYPOTHESIS": 1}  # the agent's levels, on the auditor's EvidenceLevel scale


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def render_report(res: Any, findings: list[Finding], wmap: dict[str, Any], v: dict[str, Any]) -> str:
    from ai_auditor.reporting.render import _kinds, _summary  # noqa: PLC0415

    s = _summary(res)
    tool = [f for f in findings if f.actionable and not f.superseded_by]
    ok = [f for f in v["findings"] if f["verified"]]
    bad = [f for f in v["findings"] if not f["verified"]]
    audited = sum(1 for e in v["external"] if e["audited"])
    top = sorted([(int(f.level), 0, f"{f.rule_id} — {f.component}: {f.recommended_change}") for f in tool if f.id not in v["dismissed"]]
                 + [(_RANK[f["level"]], f["scope"] == "workflow", f"{f['rule']} — {f['component']}: {f['change']}") for f in ok],
                 key=lambda t: (-t[0], -t[1]))[:3]
    out = ["# AI workflow audit", "", f"`{s['root']}`", "", "## Summary", "",
           f"- Analysed: {s['files']} files · {s['llm_steps']} steps ({_kinds(s)}) · {wmap['context_files']} context files · "
           f"{len(wmap['code'])} code files · {len(v['external'])} external pieces ({audited} audited by the agent)",
           f"- Auditor (deterministic, no LLM calls): {len(tool)} recommendations — {len(v['confirmed'])} confirmed, "
           f"{len(v['dismissed'])} dismissed, {len(v['unreviewed'])} not reviewed",
           f"- Agent review (judgement, not measurement): {len(v['findings'])} findings — {len(ok)} verified against the "
           f"files, {len(bad)} not verified", ""]
    if top:
        out += ["Main improvements:", ""] + [f"{i}. {_cell(t)}" for i, (_, _, t) in enumerate(top, 1)] + [""]
    out += ["## Recommendations from the auditor", ""]
    if tool:
        out += ["| id | rule | component | location | level | change | agent |", "|---|---|---|---|---|---|---|"]
        for f in tool:
            verdict = ("confirmed" if f.id in v["confirmed"] else f"dismissed: {v['dismissed'][f.id]}" if f.id in v["dismissed"]
                       else "not reviewed")
            out.append(f"| `{f.id}` | {f.rule_id} | {f.component} | `{f.location or '-'}` | {f.level} | {_cell(f.recommended_change)} | {_cell(verdict)} |")
    else:
        out.append("None.")
    out += ["", "## Agent review", "", "The agent's judgement, not a measurement. Every quote below was found in its file.", ""]
    for scope, title in (("step", "### Steps"), ("workflow", "### Workflow")):
        rows = [f for f in ok if f["scope"] == scope]
        if not rows:
            continue
        out += [title, "", "| # | component | rule | evidence | level | change |", "|---|---|---|---|---|---|"]
        for f in rows:
            where = f"`{f['file']}:{f['line']}`" + "".join(f", `{a['file']}:{a['line']}`" for a in f["also_in"])
            out.append(f"| {f['n']} | {f['component']} | {f['rule']} | \"{_cell(f['quote'])}\" ({where}) | {f['level']} | {_cell(f['change'])} |")
        out.append("")
    if not ok:
        out += ["No verified findings.", ""]
    if bad or v["errors"]:
        out += ["### Not verified", "", "Left out of the counts above until fixed:", ""]
        out += [f"- #{f['n']} {f['rule']} on {f['component'] or f['file']}: {'; '.join(f['problems'])}" for f in bad]
        out += [f"- {e}" for e in v["errors"]] + [""]
    out += ["## External pieces", ""]
    if v["external"]:
        out += ["| piece | kind | used by | agent |", "|---|---|---|---|"]
        out += [f"| `{e['ref']}` | {e['kind']} | {e['used_by'] or '-'} | {_cell(('audited: ' if e['audited'] else 'not audited') + (' ' + e['notes'] if e['notes'] else ''))} |"
                for e in v["external"]]
    else:
        out.append("None found.")
    out += ["", "## What does need an LLM", ""] + ([f"- {x}" for x in v["llm_justified"]] or ["Not stated by the agent."])
    out += ["", "## Facts used", ""] + render_map_markdown(wmap, limit=15)[1:] + [""]
    return "\n".join(out)


def report_json(res: Any, findings: list[Finding], wmap: dict[str, Any], v: dict[str, Any]) -> str:
    from ai_auditor.reporting.render import _summary  # noqa: PLC0415

    tool = [{"id": f.id, "rule": f.rule_id, "component": f.component, "location": str(f.location or ""), "level": str(f.level),
             "change": f.recommended_change} for f in findings if f.actionable and not f.superseded_by]
    return json.dumps({"summary": _summary(res), "auditor": tool, "review": v, "map": wmap}, indent=2, ensure_ascii=False, default=str)
