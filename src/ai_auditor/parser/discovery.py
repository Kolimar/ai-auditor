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
    # cursor_rule | cursor_rules_file | cursor_command | loose_md | other
    kind: str

    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


# Markdown that documents a project rather than instructing an agent: never read as loose instructions
_DOC_NAMES = {"readme.md", "changelog.md", "contributing.md", "license.md", "code_of_conduct.md", "security.md"}


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


def discover(root: Path, exclude: list[str], loose_md: bool = False) -> list[SourceFile]:
    root = root.resolve()
    if root.is_file():
        # a file named on the command line is meant to be audited: classify it by its full path (an agent under
        # .claude/agents stays an agent) and read any other Markdown as instructions
        return [SourceFile(root, root.name, classify(root.as_posix().lstrip("/"), loose_md=True))]
    out: list[SourceFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories instead of walking node_modules/.venv and filtering afterwards
        dirnames[:] = sorted(d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in exclude))
        # ~/.claude/plugins/marketplaces holds marketplace catalogs, which Claude Code never loads; installed plugins
        # live in plugins/cache
        if Path(dirpath).name == "plugins" and Path(dirpath).parent.name == ".claude" and "marketplaces" in dirnames:
            dirnames.remove("marketplaces")
        for fname in sorted(filenames):
            path = Path(dirpath) / fname
            rel = path.relative_to(root).as_posix()
            kind = classify(rel, loose_md)
            if kind != "other" and path.is_file():
                out.append(SourceFile(path, rel, kind))
    return sorted(out, key=lambda sf: sf.rel)
