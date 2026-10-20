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
    kind: str  # python | claude_agent | claude_skill | claude_command | claude_memory | mcp_config | prompt_file | other

    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def classify(rel: str) -> str:
    parts = rel.split("/")
    name = parts[-1]
    if name.endswith(".py") or name.endswith(".ipynb"):
        return "python"
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
    return "other"


def discover(root: Path, exclude: list[str]) -> list[SourceFile]:
    root = root.resolve()
    if root.is_file():
        return [SourceFile(root, root.name, classify(root.name))]
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
            kind = classify(rel)
            if kind != "other" and path.is_file():
                out.append(SourceFile(path, rel, kind))
    return sorted(out, key=lambda sf: sf.rel)
