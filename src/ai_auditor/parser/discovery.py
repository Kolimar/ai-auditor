"""Project discovery: decide which extractor handles each file."""

from __future__ import annotations

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel: str
    # python | claude_agent | claude_skill | claude_command | claude_memory | mcp_config | prompt_file | devin_playbook |
    # cursor_rule | cursor_rules_file | cursor_command | loose_md | aidlc_stage | aidlc_scope | check_manifest |
    # knowledge | code | other
    kind: str
    framework: str = ""  # "aidlc" for files of an AI-DLC tree
    owner: str = ""  # knowledge: the step that reads it (a step name, or the rel path of its SKILL.md)

    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


# Markdown that documents a project rather than instructing an agent: never read as loose instructions
_DOC_NAMES = {"readme.md", "changelog.md", "contributing.md", "license.md", "code_of_conduct.md", "security.md"}
# reference material next to instructions: read by a step, never a step itself
_KNOWLEDGE_DIRS = {"knowledge", "references", "reference", "templates", "protocols", "memory", "context", "resources"}
_CLAUDE_SESSION_DIRS = {"projects", "shell-snapshots", "file-history", "todos", "debug", "session-env", "paste-cache", "plans",
                        "sessions", "jobs", "downloads", "backups", "cache", "chrome", "feedback", "state", "ide", "statsig",
                        "telemetry"}
# source code the auditor does not parse: listed for the agent, scanned for LLM calls and external programs
CODE_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh", ".bash", ".zsh", ".go", ".rb", ".rs", ".java", ".kt", ".cs", ".php"}


def classify(rel: str, loose_md: bool = False) -> str:
    parts = rel.split("/")
    name = parts[-1]
    if name.endswith(".py") or name.endswith(".ipynb"):
        return "python"
    if name.endswith(".devin.md"):
        return "devin_playbook"
    if name == ".cursorrules":
        return "cursor_rules_file"
    if ".cursor" in parts[:-1] and name.endswith(".mdc") and "rules" in parts[:-1]:
        return "cursor_rule"
    if ".cursor" in parts[:-1] and name.endswith(".md") and "commands" in parts[:-1]:
        return "cursor_command"
    if name == "SKILL.md":
        return "claude_skill"
    if name.endswith(".md") and "agents" in parts[:-1] and (".claude" in parts or "plugins" in parts or parts[0] == "agents"):
        return "claude_agent"
    if name.endswith(".md") and "commands" in parts[:-1] and (".claude" in parts or parts[0] == "commands"):
        return "claude_command"
    if name in ("CLAUDE.md", "AGENTS.md", "CLAUDE.local.md"):
        return "claude_memory"
    if name == ".mcp.json":
        return "mcp_config"
    if name.endswith(".prompty"):
        return "prompt_file"
    if loose_md and name.endswith(".md") and name.lower() not in _DOC_NAMES:
        return "loose_md"  # --md-instructions: a folder of playbooks/prompts exported from any tool
    return "other"


def classify_aidlc(sub: str) -> tuple[str, str] | None:
    """(kind, owner) of a Markdown file of an AI-DLC tree (awslabs/aidlc-workflows core, a plugin or an install);
    `sub` is relative to the tree root. Stages and agents are steps; knowledge, protocols, overlays, memory and
    templates are context read by them; scopes are routing config; sensors are deterministic checks."""
    parts = sub.split("/")
    if not sub.endswith(".md") or len(parts) < 2:
        return None
    if parts[0] in ("stages", "aidlc-common") and "stages" in parts[:-1]:
        return "aidlc_stage", ""
    if parts[0] == "knowledge":
        return "knowledge", parts[1] if len(parts) > 2 else ""
    if parts[0] in ("aidlc-common", "contributions", "memory", "templates"):
        return "knowledge", ""
    if parts[0] == "scopes":
        return "aidlc_scope", ""
    if parts[0] == "sensors":
        return "check_manifest", ""
    if parts[0] == "agents" and len(parts) == 2:
        return "claude_agent", ""
    return None


def _is_aidlc_root(path: Path, dirnames: list[str]) -> bool:
    return "aidlc-common" in dirnames or ".aidlc-plugin" in dirnames and (path / ".aidlc-plugin" / "plugin.json").is_file()


def discover(root: Path, exclude: list[str], loose_md: bool = False) -> list[SourceFile]:
    root = root.resolve()
    if root.is_file():
        # a file named on the command line is meant to be audited: classify it by its full path (an agent under
        # .claude/agents stays an agent) and read any other Markdown as instructions
        return [SourceFile(root, root.name, classify(root.as_posix().lstrip("/"), loose_md=True))]
    out: list[SourceFile] = []
    aidlc_roots: list[Path] = []
    skill_dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories instead of walking node_modules/.venv and filtering afterwards
        dirnames[:] = sorted(d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in exclude))
        # ~/.claude/plugins/marketplaces holds marketplace catalogs, which Claude Code never loads; installed plugins
        # live in plugins/cache
        if Path(dirpath).name == "plugins" and Path(dirpath).parent.name == ".claude" and "marketplaces" in dirnames:
            dirnames.remove("marketplaces")
        if Path(dirpath).name == ".claude":  # session data of the user's ~/.claude, not configuration
            dirnames[:] = [d for d in dirnames if d not in _CLAUDE_SESSION_DIRS]
        here = Path(dirpath)
        if _is_aidlc_root(here, dirnames):
            aidlc_roots.append(here)
        if "SKILL.md" in filenames:
            skill_dirs.append(here)
        aidlc = next((r for r in reversed(aidlc_roots) if here == r or r in here.parents), None)
        skill = next((d for d in reversed(skill_dirs) if here == d or d in here.parents), None)
        for fname in sorted(filenames):
            path = Path(dirpath) / fname
            rel = path.relative_to(root).as_posix()
            kind, framework, owner = classify(rel, loose_md), "", ""
            if aidlc is not None and (hit := classify_aidlc(path.relative_to(aidlc).as_posix())):
                (kind, owner), framework = hit, "aidlc"
            elif kind in ("other", "loose_md") and fname.endswith(".md") and fname.lower() not in _DOC_NAMES and (
                    skill is not None or kind == "loose_md" and _KNOWLEDGE_DIRS & set(rel.split("/")[:-1])):
                # a skill's references, or a knowledge folder of loose instructions
                kind, owner = "knowledge", (skill / "SKILL.md").relative_to(root).as_posix() if skill else ""
            elif kind == "other" and path.suffix in CODE_SUFFIXES and not fname.endswith(".d.ts"):
                kind = "code"
            if kind != "other" and path.is_file():
                out.append(SourceFile(path, rel, kind, framework, owner))
    return sorted(out, key=lambda sf: sf.rel)
