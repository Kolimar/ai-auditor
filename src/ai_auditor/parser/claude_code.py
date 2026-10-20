"""Extractor for Markdown agent instructions: Claude Code (subagents, skills, commands, memory files, MCP config),
Devin playbooks, Cursor rules and commands, and loose ``.md`` files read with ``--md-instructions``.

Mapping to the IR:

* subagent ``.claude/agents/*.md`` -> LLMStep(kind=agent); body = system prompt,
  ``description`` = always-loaded routing text, ``model`` alias or ``inherit``.
* skill ``SKILL.md`` / command ``.md`` -> LLMStep(kind=agent, attrs.cc_type=skill|command):
  instructions executed by the invoking agent; description always loaded,
  body loaded on invocation. Bundled scripts are recorded (deterministic code
  that already exists next to the instructions).
* ``CLAUDE.md`` / ``AGENTS.md`` -> CONTEXT_SOURCE injected into every session.
* ``.mcp.json`` -> one TOOL node per MCP server (its tool list is only known at runtime).
* Devin ``*.devin.md``, Cursor ``.cursor/commands/*.md`` and loose ``.md`` -> like a command: instructions the
  user hands to an agent that has its full toolset.
* Cursor ``.cursorrules`` and ``.cursor/rules/*.mdc`` with ``alwaysApply: true`` -> CONTEXT_SOURCE added to every
  request; any other ``.mdc`` rule -> like a skill (description offered to the agent, body read on demand).
* AI-DLC stages -> LLMStep(cc_type=stage), run inline by their ``lead_agent``; scopes -> CONTEXT_SOURCE(role=config);
  sensors -> deterministic TOOL nodes.
* Knowledge (AI-DLC ``knowledge/<agent>/``, a skill's references, knowledge folders of loose instructions) ->
  CONTEXT_SOURCE read by its owner or by the files that reference it (``link_context``).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from ai_auditor.ir.model import (
    INSTRUCTION_FRAMEWORKS,
    EdgeKind,
    LLMStep,
    ModelRef,
    Node,
    NodeKind,
    PromptPart,
    SourceLocation,
    StepKind,
    SystemIR,
    stable_id,
)
from ai_auditor.parser.discovery import SourceFile
from ai_auditor.parser.tokens import count_tokens

EXTRACTOR_VERSION = "cc-7"  # bump whenever the extracted IR changes (it keys the IR cache)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
# Commands the instructions tell the model to run: `git status`, `npm test`, `dbt run --select x`, or lines of a shell
# code block. Known tools are accepted alone; any other CLI needs a flag, a path or a subcommand-like second word.
_KNOWN_CLI = re.compile(r"(git|npm|pnpm|yarn|npx|pytest|python3?|uv|make|cargo|go|docker|kubectl|ls|cat|grep|rg|find|curl|gh|bash|sh)")
_CMD = re.compile(r"`([^`\n]{1,160})`")
_SUBCOMMANDS = {"run", "build", "test", "plan", "apply", "deploy", "install", "compile", "clean", "lint", "format", "fmt", "check",
                "upload", "push", "pull", "start", "stop", "exec", "query", "tasks", "dags", "migrate", "generate", "init", "sync",
                "release", "publish", "serve", "watch", "bump", "version", "validate", "flash", "monitor", "seed", "snapshot",
                "backfill", "clear", "trigger", "refresh", "update", "upgrade", "export", "import", "diff", "status", "list", "ls"}
_NOT_CLI = {"the", "a", "an", "if", "for", "and", "or", "is", "to", "of", "in", "on", "this", "that", "el", "la", "los", "las",
            "un", "una", "de", "y", "o", "en", "que", "true", "false", "null", "none"}
_SHELL_FENCE = {"", "bash", "sh", "shell", "console", "zsh", "terminal", "powershell", "ps1", "cmd", "bat", "fish"}
_SCRIPT_SUFFIXES = {".py", ".sh", ".js", ".ts", ".mjs", ".rb"}
# file kind -> (cc_type, framework) of the step it becomes
_STEP_KINDS = {
    "claude_agent": ("agent", "claude_code"), "claude_skill": ("skill", "claude_code"), "claude_command": ("command", "claude_code"),
    "devin_playbook": ("command", "devin"), "cursor_command": ("command", "cursor"), "cursor_rule": ("skill", "cursor"),
    "loose_md": ("command", "markdown"), "aidlc_stage": ("stage", "aidlc"),
}
# a clause that states a policy or gives examples lists *permitted* commands, not steps to run
_POLICY = re.compile(r"(?i)\b(only|allowed|permitted|never|do not|don't|must not|forbidden|prohibited|read-only|e\.g\.|such as|"
                     r"for example|solo|s[oó]lo|nunca|permitid[oa]s?|prohibid[oa]s?|por ejemplo)\b")
# between consecutive commands of one clause: a sequence ("A, then B, then C") rather than an enumeration (allowlist)
_SEQUENCE = re.compile(r"(?i)\b(then|and then|followed by|afterwards|after that|next|finally|luego|despu[eé]s|y luego|finalmente)\b|->|→|&&|;")
_RUN_VERB = re.compile(r"(?i)\b(run|execute|invoke|ejecuta|corre|lanza)\b")
_BARE_SEARCH = {"ls", "cat", "grep", "rg", "find"}  # bare search utilities are tool mentions, not invocations


def _is_command(text: str, run_context: bool = False) -> bool:
    s = re.sub(r"^\s*[$>]\s+", "", text).strip()
    if not s:
        return False
    first, *rest = s.split()
    if _KNOWN_CLI.fullmatch(first) or re.fullmatch(r"(\./|bin/|scripts/)[\w./-]*[\w-]", first):
        return True  # ./deploy.sh, scripts/release.py (a bare `scripts/` directory is not a command)
    if not rest or not re.fullmatch(r"[a-z][a-z0-9_.-]{1,30}", first) or first in _NOT_CLI:
        return False
    # "Run `rake spec`": after an explicit run verb any `tool word` pair is an invocation
    return any(t.startswith("-") or "/" in t or ":" in t for t in rest) or rest[0] in _SUBCOMMANDS or (
        run_context and all(re.fullmatch(r"[a-z0-9_.:=/@-]+", t) for t in rest))


def _clause_commands(clause: str) -> list[str]:
    run = bool(_RUN_VERB.search(clause))
    spans = [m for m in _CMD.finditer(clause) if _is_command(m.group(1), run)]
    if len(spans) >= 3:  # three or more in one clause: a sequence only if every gap says so, otherwise an allowlist
        gaps = [clause[a.end():b.start()] for a, b in zip(spans, spans[1:])]
        if not all(_SEQUENCE.search(g) for g in gaps):
            return []
    return [m.group(1).strip() for m in spans]


def procedure_commands(body: str) -> list[str]:
    """Commands that read as steps of a procedure: inline (not in policy/example clauses, not an enumeration of 3+ in
    one clause) or lines of a shell code block (unless the block is introduced by a policy line); bare search
    utilities excluded."""
    out: list[str] = []
    prohibited = False  # inside a section whose heading forbids something ("## NEVER run the real installer")
    fence: str | None = None  # language of the open code block
    fence_policy = False
    heredoc: str | None = None  # terminator of an open heredoc inside a shell block (its lines are data)
    previous = ""
    lines = re.sub(r"[ \t]*\\\n\s*", " ", body).splitlines()  # join shell line continuations
    for line in lines:
        m = re.match(r"\s{0,3}(```|~~~)\s*([\w+-]*)", line)
        if m:
            if fence is None:
                fence, fence_policy = m.group(2).lower(), bool(_POLICY.search(previous))
            else:
                fence = None
            continue
        if fence is not None:
            if heredoc is not None:
                if line.strip() == heredoc:
                    heredoc = None
                continue
            hd = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
            if hd:
                heredoc = hd.group(1)
            if fence in _SHELL_FENCE and not prohibited and not fence_policy:
                cmd = re.sub(r"^\s*[$>]\s+", "", line).strip()
                if cmd and not cmd.startswith("#") and _is_command(cmd):
                    out.append(cmd)
            continue
        if line.strip():
            previous = line
        if re.match(r"\s{0,3}#{1,6}\s", line):
            prohibited = bool(_POLICY.search(line))
            continue
        if prohibited:
            continue
        for clause in re.split(r"(?<=[.;!?])\s+(?=[A-Z0-9¿¡])", line):
            if not _POLICY.search(clause):
                out += _clause_commands(clause)
    return list(dict.fromkeys(c for c in out if c not in _BARE_SEARCH))


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, int, str | None]:
    """Return (frontmatter, body, body_start_line, error)."""
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text, 1, None
    raw = m.group(1)
    body_line = text[: m.end()].count("\n") + 1
    try:
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            raise ValueError("frontmatter is not a mapping")
        return data, text[m.end():], body_line, None
    except Exception as exc:  # tolerate sloppy frontmatter: fall back to key: value lines
        data = {}
        for line in raw.splitlines():
            if ":" in line and not line.startswith((" ", "\t")):
                k, _, v = line.partition(":")
                data[k.strip()] = v.strip()
        return data, text[m.end():], body_line, str(exc)


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    return [str(value)]


def _model(value: Any) -> ModelRef:
    if value is None or str(value).strip().lower() in ("", "inherit"):
        return ModelRef(raw=None if value is None else str(value), inherited=True)
    return ModelRef(raw=str(value).strip(), provider="anthropic")


def _description(fm: dict[str, Any]) -> str:
    parts = [str(fm.get("description") or "").strip(), str(fm.get("when_to_use") or "").strip()]
    return "\n".join(p for p in parts if p)


def extract_claude_file(sf: SourceFile) -> SystemIR:
    ir = SystemIR(root="")
    text = sf.path.read_text(errors="replace")
    loc = SourceLocation(sf.rel, 1)

    if sf.kind == "claude_memory":
        # Only project-root memory (or .claude/CLAUDE.md) is read at session start; a nested CLAUDE.md is loaded when
        # Claude works on files in that subtree. AGENTS.md is read by Codex and other agents, not by Claude Code itself.
        root_level = "/" not in sf.rel or sf.rel.startswith(".claude/") and sf.rel.count("/") == 1
        name = sf.rel.split("/")[-1]
        ir.add(
            Node(
                id=stable_id("ctx", sf.rel),
                kind=NodeKind.CONTEXT_SOURCE,
                name=name if sf.rel.count("/") == 0 else sf.rel,
                location=loc,
                attrs={
                    "framework": "claude_code",
                    "always_loaded": root_level,
                    "loading": ("session start" if root_level else "on demand (nested: loaded when working in that directory)"),
                    "loaded_by": "codex/other agents" if name == "AGENTS.md" else "claude_code",
                    "realpath": str(sf.path.resolve()),
                    "est_tokens": count_tokens(text),
                    "lines": text.count("\n") + 1,
                    "imports": re.findall(r"(?m)(?:^|\s)@([\w./-]+\.\w+)", text),
                    "text": text,
                },
            )
        )
        return ir

    if sf.kind in ("cursor_rules_file", "cursor_rule"):
        fm, body, _, err = parse_frontmatter(text)
        if sf.kind == "cursor_rules_file" or str(fm.get("alwaysApply")).lower() == "true":
            if err:
                ir.warn("FRONTMATTER_ERROR", f"invalid YAML frontmatter: {err}", loc)
            # added to every Cursor request, like a root CLAUDE.md is to every Claude Code session
            ir.add(
                Node(
                    id=stable_id("ctx", sf.rel),
                    kind=NodeKind.CONTEXT_SOURCE,
                    name=sf.rel,
                    location=loc,
                    attrs={
                        "framework": "cursor",
                        "always_loaded": True,
                        "loading": "every request",
                        "loaded_by": "cursor",
                        "realpath": str(sf.path.resolve()),
                        "est_tokens": count_tokens(body),
                        "lines": body.count("\n") + 1,
                        "imports": [],
                        "text": body,
                    },
                )
            )
            return ir

    if sf.kind in ("knowledge", "aidlc_scope"):
        fm, body, _, _ = parse_frontmatter(text)
        config = sf.kind == "aidlc_scope"
        ir.add(
            Node(
                id=stable_id("ctx", sf.rel),
                kind=NodeKind.CONTEXT_SOURCE,
                name=sf.rel,
                location=loc,
                attrs={
                    "framework": sf.framework or "markdown",
                    "role": "config" if config else "knowledge",
                    "always_loaded": False,
                    "loading": "read by the AI-DLC orchestrator" if config else "read by the step that owns or references it",
                    "loaded_by": sf.framework or "markdown",
                    "owner": sf.owner,
                    "realpath": str(sf.path.resolve()),
                    "est_tokens": count_tokens(text),
                    "lines": text.count("\n") + 1,
                    "imports": [],
                    "text": text,
                },
            )
        )
        return ir

    if sf.kind == "check_manifest":
        fm, body, _, _ = parse_frontmatter(text)
        ir.add(
            Node(
                id=stable_id("check", sf.rel),
                kind=NodeKind.TOOL,
                name=str(fm.get("id") or Path(sf.rel).stem),
                location=loc,
                attrs={"framework": sf.framework, "deterministic": True, "check": True, "command": fm.get("command"),
                       "description": fm.get("description"), "fire_on": fm.get("fire_on")},
            )
        )
        return ir

    if sf.kind == "mcp_config":
        try:
            servers = (json.loads(text) or {}).get("mcpServers", {})
        except json.JSONDecodeError as exc:
            ir.warn("PARSE_ERROR", f".mcp.json is not valid JSON: {exc}", loc)
            return ir
        for name, cfg in servers.items():
            ir.add(
                Node(
                    id=stable_id("mcp", sf.rel, name),
                    kind=NodeKind.TOOL,
                    name=f"mcp:{name}",
                    location=loc,
                    attrs={"framework": "claude_code", "mcp_server": True, "transport": (cfg or {}).get("type"),
                           "tool_count": None, "tool_tokens": None},
                )
            )
        return ir

    fm, body, body_line, err = parse_frontmatter(text)
    if err:
        ir.warn("FRONTMATTER_ERROR", f"invalid YAML frontmatter: {err}", loc)
    cc_type, framework = _STEP_KINDS[sf.kind]
    framework = sf.framework or framework  # an agent of an AI-DLC tree is an AI-DLC agent
    path = Path(sf.rel)
    if sf.kind == "claude_skill":
        default_name = path.parent.name
    elif sf.kind == "devin_playbook":
        default_name = path.name[: -len(".devin.md")]
    else:
        default_name = path.stem
    # an AI-DLC stage is identified by its slug; its `name` is a display title
    name = str((fm.get("slug") if sf.kind == "aidlc_stage" else None) or fm.get("name") or default_name)
    desc = _description(fm)

    prompt: list[PromptPart] = []
    if desc:
        prompt.append(PromptPart(role="description", text=desc, location=SourceLocation(sf.rel, 1), always_loaded=True))
    if body.strip():
        prompt.append(PromptPart(role="system", text=body.strip(), location=SourceLocation(sf.rel, body_line)))

    tools_key = "tools" if cc_type == "agent" else "allowed-tools"
    tools = _as_list(fm.get(tools_key))
    model = _model(fm.get("model")) if (cc_type == "agent" or "model" in fm) else ModelRef(inherited=True)

    attrs: dict[str, Any] = {
        "cc_type": cc_type,
        "frontmatter_keys": sorted(fm),
        # outside Claude Code there is no tool list: the agent runs the instructions with its full toolset
        "tools_inherited": (cc_type == "agent" and tools_key not in fm) if framework == "claude_code" else True,
        "fixed_commands": procedure_commands(body),
        "body_tokens": count_tokens(body),
        "body_lines": body.count("\n") + 1,
        "preloaded_skills": _as_list(fm.get("skills")),
        "effort": fm.get("effort"),
        "context": fm.get("context"),
        "disable_model_invocation": bool(fm.get("disable-model-invocation")),
        "provenance": {"model": "literal" if "model" in fm else "absent"},
    }
    if sf.kind == "aidlc_stage":
        attrs.update(lead_agent=fm.get("lead_agent"), support_agents=_as_list(fm.get("support_agents")),
                     sensors=_as_list(fm.get("sensors")), mode=fm.get("mode"), execution=fm.get("execution"))
    if sf.kind == "claude_skill":
        skill_dir = sf.path.parent
        attrs["bundled_scripts"] = sorted(
            p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.suffix in _SCRIPT_SUFFIXES
        )

    max_turns = fm.get("maxTurns")
    ir.add(
        LLMStep(
            id=stable_id("cc", sf.rel),
            kind=NodeKind.LLM_STEP,
            name=name,
            location=loc,
            attrs=attrs,
            step_kind=StepKind.AGENT,
            framework=framework,
            model=model,
            prompt=prompt,
            tool_names=tools,
            max_iterations=int(max_turns) if isinstance(max_turns, int) else None,
            description=desc or None,
            thinking={"effort": fm["effort"]} if fm.get("effort") else None,
        )
    )
    return ir


def link_claude_code(ir: SystemIR) -> None:
    """Cross-file edges: delegation by name mention, preloaded skills, memory injection."""
    steps = [s for s in ir.llm_steps() if s.framework in INSTRUCTION_FRAMEWORKS]
    by_name = {s.name: s for s in steps}
    distinctive = {n for n in by_name if "-" in n or "_" in n}
    plain_lower = {n.lower(): n for n in by_name if n not in distinctive}
    for s in steps:
        body = s.static_text({"system"})
        targets: set[str] = set(s.attrs.get("preloaded_skills", []))
        # Only distinctive names (with - or _) or explicitly qualified mentions, to avoid linking on common words.
        tokens = set(re.findall(r"(?<![\w-])[\w][\w-]*(?<!-)(?![\w-])", body))
        targets |= (tokens & distinctive) - {s.name}
        # "X agent", subagent_type: X, or a slash command "/x" (not a path segment like docs/x or /usr/x)
        qualified = re.findall(r"\b([\w-]+)\s+(?:sub)?agent|subagent_type[\"'\s:=]+([\w-]+)|(?<![\w/.~-])/([\w-]+)(?![\w/.-])", body, re.I)
        for groups in qualified:
            for g in groups:
                name = plain_lower.get(g.lower())
                if name and name != s.name:
                    targets.add(name)
        text = body + "\n" + (s.description or "")
        for t in sorted(targets):
            if t not in by_name:
                continue
            n = re.escape(t)
            # "the notes produced by the paper-summarizer agent" / "paper-summarizer's output": consumes its output
            consumes = re.search(rf"(?i)\b(produced|written|generated|created|returned|output|left|saved) by (the )?`?{n}\b"
                                 rf"|`?{n}`?'s (output|notes?|summar(y|ies)|results?|reports?|files?)\b"
                                 rf"|\b(output|notes|summaries|results|reports?|files) (of|from) (the )?`?{n}\b", text)
            if consumes:
                ir.link(by_name[t].id, s.id, EdgeKind.DATA_FLOW, via="consumes_output")
            else:
                ir.link(s.id, by_name[t].id, EdgeKind.DELEGATES, via="name_mention")
    for ctx in ir.of_kind(NodeKind.CONTEXT_SOURCE):
        if ctx.attrs.get("framework") != "claude_code" or not ctx.attrs.get("always_loaded") or ctx.attrs.get("loaded_by") != "claude_code":
            continue
        for s in steps:
            if s.attrs.get("cc_type") == "agent":
                ir.link(ctx.id, s.id, EdgeKind.INJECTS_CONTEXT, always_loaded=True)


# a Markdown file another instruction tells the agent to read: "Follow stage-protocol.md", "read per
# `{{HARNESS_DIR}}/knowledge/shared/rules.md`", "[guide](docs/guide.md)"
_MD_REF = re.compile(r"(?<![\w./{}<>-])([\w.{](?:[\w.{}-]*/)*[\w.-]+\.md)\b")
_READ_VERB = re.compile(r"(?i)\b(follow|read|load|see|consult|per|apply|use|according to|sigue|segu[ií]|lee|le[eé]r?|"
                        r"carga|carg[aá]|consulta|consult[aá]|seg[uú]n|aplica|aplic[aá]|usa|us[aá])\b")


def md_references(text: str) -> list[str]:
    out: list[str] = []
    for m in _MD_REF.finditer(text):
        ref = m.group(1)
        if any(c in ref for c in "<>*$") or ref.startswith("http"):
            continue  # placeholders and globs name outputs or patterns, not a file to read
        before = text[max(0, m.start() - 80):m.start()].rsplit("\n", 1)[-1]
        ref = re.sub(r"^(?:\{\{\w+\}\}/|\./|\.claude/)+", "", ref)
        if "{" in ref or "}" in ref:
            continue  # a path template: openspec/changes/{change-name}/design.md
        if "/" in ref or before.endswith("](") or _READ_VERB.search(before):
            out.append(ref)
    return list(dict.fromkeys(out))


def _context_node(rel: str, location: SourceLocation | None, text: str, framework: str) -> Node:
    return Node(
        id=stable_id("ctx", rel), kind=NodeKind.CONTEXT_SOURCE, name=rel, location=location,
        attrs={"framework": framework, "role": "knowledge", "always_loaded": False,
               "loading": "read by the files that reference it", "loaded_by": framework, "owner": "",
               "est_tokens": count_tokens(text), "lines": text.count("\n") + 1, "imports": [], "text": text},
    )


def link_context(ir: SystemIR) -> None:
    """Knowledge -> the step that owns its folder; referenced Markdown -> the files that tell the agent to read it.
    A loose .md that another file tells the agent to read is context, not a step. References to files outside the
    audited folder are recorded as `missing_refs`."""
    md: dict[str, Node] = {}
    for n in ir.nodes.values():
        if n.location and n.location.file.endswith(".md") and (
                isinstance(n, LLMStep) and n.framework in INSTRUCTION_FRAMEWORKS or n.kind == NodeKind.CONTEXT_SOURCE):
            md[n.location.file] = n

    def text_of(n: Node) -> str:
        return n.static_text() if isinstance(n, LLMStep) else str(n.attrs.get("text") or "")

    def resolve(ref: str, src: str) -> str | None:
        if ref.startswith(".."):
            ref = os.path.normpath(os.path.join(os.path.dirname(src), ref))
        hits = [rel for rel in md if (rel == ref or rel.endswith("/" + ref)) and rel != src]
        # the same name in several places (core and a plugin): the closest one to the referencing file
        return min(hits, key=lambda h: (-len(os.path.commonprefix([h, src])), len(h))) if hits else None

    refs = {rel: [(r, resolve(r, rel)) for r in md_references(text_of(n))] for rel, n in md.items()}
    referenced = {t for pairs in refs.values() for _, t in pairs if t}
    for rel in referenced:
        n = md[rel]
        if isinstance(n, LLMStep) and n.framework == "markdown":
            del ir.nodes[n.id]
            md[rel] = ir.add(_context_node(rel, n.location, n.static_text(), "markdown"))
    steps = [s for s in ir.llm_steps() if s.framework in INSTRUCTION_FRAMEWORKS]
    by_name = {s.name: s for s in steps}
    by_file = {s.location.file: s for s in steps if s.location}
    for n in ir.of_kind(NodeKind.CONTEXT_SOURCE):
        owner = by_name.get(n.attrs.get("owner") or "") or by_file.get(n.attrs.get("owner") or "")
        if owner is not None:
            # AI-DLC loads an agent's knowledge folder with its persona; a skill reads its bundled files on demand
            ir.link(n.id, owner.id, EdgeKind.INJECTS_CONTEXT, via="owner" if n.attrs.get("framework") == "aidlc" else "bundled")
    root = Path(ir.root) if ir.root else None
    if root is not None and root.is_file():
        root = root.parent
    for rel, pairs in refs.items():
        src = md[rel]
        for ref, target in pairs:
            if target is None:
                here = (root / rel).parent if root else None
                # a file on disk that is not instructions (docs, examples) is not missing, just not read as context
                if root is None or not any((d / ref).exists() for d in (here, *(here.parents if here else ())) if root in (d, *d.parents)):
                    src.attrs.setdefault("missing_refs", []).append(ref)
            elif md[target].kind == NodeKind.CONTEXT_SOURCE:
                ir.link(md[target].id, src.id, EdgeKind.INJECTS_CONTEXT, via="reference")
