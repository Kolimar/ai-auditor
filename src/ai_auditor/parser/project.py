"""Build the SystemIR for a project, with a content-addressed cache.

Claude Code files are extracted (and cached) per file. Python is analysed as a
whole project (cross-module data flow), so its cache key is the combined hash of
every Python file: if nothing changed, nothing is re-parsed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from ai_auditor import __version__
from ai_auditor.config import AuditConfig
from ai_auditor.ir.model import INSTRUCTION_FRAMEWORKS, Diagnostic, FileRecord, LLMStep, NodeKind, SourceLocation, SystemIR
from ai_auditor.parser.claude_code import EXTRACTOR_VERSION as CC_VERSION
from ai_auditor.parser.claude_code import extract_claude_file, link_claude_code
from ai_auditor.parser.discovery import discover
from ai_auditor.parser.python.extractor import EXTRACTOR_VERSION as PY_VERSION
from ai_auditor.parser.python.extractor import PythonProjectExtractor, non_production_path
from ai_auditor.parser.python.index import build_index


def cache_dir_for(root: Path) -> Path:
    """Outside the audited project (never write into the system under audit): $AI_AUDITOR_CACHE, else
    $XDG_CACHE_HOME/ai-auditor, else ~/.cache/ai-auditor; one subdirectory per audited root."""
    base = os.environ.get("AI_AUDITOR_CACHE") or os.path.join(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache", "ai-auditor")
    target = root if root.is_dir() else root.parent
    return Path(base) / hashlib.sha256(str(target.resolve()).encode()).hexdigest()[:16]


class _Cache:
    def __init__(self, root: Path, enabled: bool) -> None:
        self.dir = cache_dir_for(root)
        self.enabled = enabled
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> SystemIR | None:
        if not self.enabled:
            return None
        p = self.dir / f"{key}.json"
        if p.exists():
            try:
                ir = SystemIR.from_dict(json.loads(p.read_text()))
                self.hits += 1
                return ir
            except Exception:
                return None
        self.misses += 1
        return None

    def put(self, key: str, ir: SystemIR) -> None:
        if not self.enabled:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{key}.json").write_text(json.dumps(ir.to_dict(), ensure_ascii=False))
        except OSError:
            pass  # caching is an optimization; never fail the audit because of it


def extract_project(root: Path, config: AuditConfig, use_cache: bool = True) -> tuple[SystemIR, dict]:
    root = root.resolve()
    files = discover(root, config.exclude, config.markdown_instructions)
    if config.notebooks == "skip":
        files = [sf for sf in files if not sf.rel.endswith(".ipynb")]
    cache = _Cache(root, use_cache)
    ir = SystemIR(root=str(root))

    for sf in files:
        if sf.kind == "python":
            continue
        digest = sf.sha256()
        key = hashlib.sha256(f"{__version__}|{CC_VERSION}|{sf.kind}|{sf.rel}|{digest}".encode()).hexdigest()[:32]
        part = cache.get(key)
        if part is None:
            try:
                part = extract_claude_file(sf)
                cache.put(key, part)
            except Exception as exc:  # noqa: BLE001 - one bad file must not hide the rest of the report
                part = _crashed(root, f"{sf.rel}: {type(exc).__name__}: {exc}")
        ir.merge(part)
        ir.files.append(FileRecord(sf.rel, digest, sf.kind))

    py_files = [sf for sf in files if sf.kind == "python"]
    if py_files:
        digests = [(sf.rel, sf.sha256()) for sf in py_files]
        key = hashlib.sha256((f"{__version__}|{PY_VERSION}|" + "|".join(f"{r}:{d}" for r, d in digests)).encode()).hexdigest()[:32]
        part = cache.get(key)
        if part is None:
            index, errors = build_index(root if root.is_dir() else root.parent, [(sf.path, sf.rel) for sf in py_files])
            try:
                part = PythonProjectExtractor(index).extract()
                _apply_deferred(part)
                cache.put(key, part)
            except Exception as exc:  # noqa: BLE001 - reported loudly; never cached
                part = _crashed(root, f"python extractor: {type(exc).__name__}: {exc}")
            for rel, err in errors:
                part.warn("PARSE_ERROR", f"{rel}: {err}", SourceLocation(rel, 1))
        ir.merge(part)
        ir.files += [FileRecord(r, d, "python") for r, d in digests]

    for node in ir.nodes.values():  # any framework: a SKILL.md under examples/ is an example too
        if node.location and non_production_path(node.location.file) and not node.attrs.get("non_production"):
            node.attrs["non_production"] = True
    if config.notebooks != "production":
        for node in ir.nodes.values():
            if node.location and node.location.file.endswith(".ipynb"):
                node.attrs["non_production"] = True
                node.attrs["non_production_reason"] = "exploratory notebook (set `notebooks: production` to audit it)"
    _dedupe_memory(ir)
    _dedupe_claude_code(ir)
    link_claude_code(ir)
    for step in ir.llm_steps():
        if step.model.raw is None and not step.model.inherited:
            ir.warn("UNRESOLVED_MODEL", f"model of '{step.name}' could not be resolved statically", step.location)
    stats = {"files": len(files), "cache_hits": cache.hits, "cache_misses": cache.misses}
    return ir, stats


def _crashed(root: Path, message: str) -> SystemIR:
    """An extractor bug: return an empty partial IR with an error diagnostic (the report says results are partial)."""
    part = SystemIR(root=str(root))
    part.diagnostics.append(Diagnostic("error", "EXTRACTOR_CRASH", message + " — results are PARTIAL; please report this"))
    return part


def _dedupe_memory(ir: SystemIR) -> None:
    """CLAUDE.md -> AGENTS.md symlinks: one file on disk is one context source (keep the CLAUDE.md name)."""
    by_real: dict[str, list] = {}
    for node in ir.of_kind(NodeKind.CONTEXT_SOURCE):
        if node.attrs.get("realpath"):
            by_real.setdefault(node.attrs["realpath"], []).append(node)
    for nodes in by_real.values():
        if len(nodes) < 2:
            continue
        nodes.sort(key=lambda n: (n.attrs.get("loaded_by") != "claude_code", not n.attrs.get("always_loaded"), n.name))
        keep = nodes[0]
        keep.attrs["aliases"] = [n.name for n in nodes[1:]]
        keep.attrs["loaded_by"] = "claude_code" if any(n.attrs.get("loaded_by") == "claude_code" for n in nodes) else keep.attrs["loaded_by"]
        keep.attrs["always_loaded"] = any(n.attrs.get("always_loaded") for n in nodes)
        for n in nodes[1:]:
            del ir.nodes[n.id]


def _dedupe_claude_code(ir: SystemIR) -> None:
    """The same plugin can be present several times (marketplace clone, install cache, versions). Identical
    definitions are one component: keep the first path, report the copies."""
    seen: dict[tuple, str] = {}
    dupes: dict[str, list[str]] = {}
    for step in sorted(ir.llm_steps(), key=lambda s: (s.location.file if s.location else "")):
        if step.framework not in INSTRUCTION_FRAMEWORKS:
            continue
        key = (step.attrs.get("cc_type"), step.name, hashlib.sha1(step.static_text().encode()).hexdigest(),
               tuple(step.tool_names), step.model.raw)
        if key in seen:
            dupes.setdefault(seen[key], []).append(step.location.file if step.location else step.id)
            del ir.nodes[step.id]
        else:
            seen[key] = step.id
    for keep, copies in dupes.items():
        node = ir.nodes[keep]
        node.attrs["identical_copies"] = copies
        ir.warn("DUPLICATE_DEFINITION", f"'{node.name}' has {len(copies)} identical cop{'y' if len(copies) == 1 else 'ies'}, analysed once", node.location)


def _apply_deferred(ir: SystemIR) -> None:
    """Attributes set on a step from another function (e.g. json.loads of its output in the caller)."""
    for nid in [n for n in ir.nodes if n.startswith("attr:")]:
        node = ir.nodes.pop(nid)
        target = ir.nodes.get(node.attrs["target"])
        if isinstance(target, LLMStep):
            target.attrs[node.attrs["key"]] = node.attrs["value"]
    for step in ir.llm_steps():
        step.attrs.pop("_loops", None)
    ir.edges = [e for e in ir.edges if e.src in ir.nodes and e.dst in ir.nodes]
    assert all(n.kind != NodeKind.CODE_STEP or n.name != "deferred-attr" for n in ir.nodes.values())
