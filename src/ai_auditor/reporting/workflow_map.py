"""Deterministic facts about a workflow, for the agent that reviews it.

The rules judge one step at a time; an agent reviewing a whole workflow needs the structure around them: what each
step loads into its context (its own text, its lead agent, knowledge, referenced files), text repeated across files
that load together, code the auditor does not parse (scanned for LLM SDK imports and programs it starts), and pieces
from outside the audited folder (cloned repos, downloads, packages, programs, files referenced but not present).
Everything here is measured from the files; whether it is a problem is the agent's call.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ai_auditor.ir.model import INSTRUCTION_FRAMEWORKS, EdgeKind, LLMStep, Node, NodeKind
from ai_auditor.parser.python.extractor import non_production_path
from ai_auditor.parser.tokens import count_tokens


def _base(res: Any) -> Path:
    root = Path(res.ir.root)
    return root.parent if root.is_file() else root


def _live(s: LLMStep) -> bool:
    return s.framework in INSTRUCTION_FRAMEWORKS and not s.attrs.get("dead_code") and not s.attrs.get("non_production")


def _text(n: Node) -> str:
    return n.static_text() if isinstance(n, LLMStep) else str(n.attrs.get("text") or "")


def _tokens(n: Node) -> int:
    return count_tokens(n.static_text()) if isinstance(n, LLMStep) else int(n.attrs.get("est_tokens") or 0)


def _file(n: Node) -> str:
    return n.location.file if n.location else n.name


# ------------------------------------------------------------------------------------------------ context load

def load_sets(res: Any) -> list[dict[str, Any]]:
    """Per step: the files that end up in its context. An AI-DLC stage runs with its lead agent's persona and that
    agent's knowledge. `files` is what loads directly: the step, its lead agent, their knowledge and always-loaded
    memory, and the files any of those tell the agent to read; `reachable` adds what those files reference in turn
    (read only if the agent follows every reference)."""
    ir = res.ir
    by_name = {s.name: s for s in ir.llm_steps() if s.framework in INSTRUCTION_FRAMEWORKS}
    feeds: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for e in ir.edges:
        if e.kind == EdgeKind.INJECTS_CONTEXT and e.src in ir.nodes:
            feeds[e.dst].append((e.src, {"reference": 1, "bundled": 2}.get(e.attrs.get("via"), 0)))
    checks = {n.name: n for n in ir.of_kind(NodeKind.TOOL) if n.attrs.get("check")}
    out = []
    for s in ir.llm_steps():
        if not _live(s):
            continue
        members: list[tuple[Node, str]] = [(s, "itself")]
        lead = by_name.get(str(s.attrs.get("lead_agent") or "")) if s.attrs.get("cc_type") == "stage" else None
        if lead is not None:
            members.append((lead, "lead agent"))
        depth = {m.id: 0 for m, _ in members}
        queue = [m.id for m, _ in members]
        while queue:  # breadth first, so each file gets its smallest number of reference hops
            nid = queue.pop(0)
            for src, hop in feeds.get(nid, []):
                if src not in depth:
                    depth[src] = depth[nid] + hop
                    queue.append(src)
                    n = ir.nodes[src]
                    how = ("always loaded" if n.attrs.get("always_loaded") else "referenced" if hop == 1 else
                           "bundled, on demand" if hop == 2 else n.attrs.get("role") or "context")
                    members.append((n, how))
        direct = [(n, how) for n, how in members if depth[n.id] <= 1]
        files = [{"file": _file(n), "tokens": _tokens(n), "as": how} for n, how in direct]
        further = [n for n, _ in members if depth[n.id] > 1]
        missing = sorted({r for n, _ in direct for r in n.attrs.get("missing_refs", [])})
        out.append({"step": s.name, "kind": f"{s.framework} {s.attrs.get('cc_type') or s.step_kind.value}",
                    "location": _file(s), "files": files, "tokens": sum(f["tokens"] for f in files),
                    "reachable": {"files": len(further), "tokens": sum(_tokens(n) for n in further)},
                    "missing": missing, "runs": _runs(res, s, checks)})
    return sorted(out, key=lambda d: -d["tokens"])


def _runs(res: Any, s: LLMStep, checks: dict[str, Node]) -> list[str]:
    """Local scripts the step tells the agent to run, and the sensors its stage declares."""
    base = _base(res)
    here = (base / s.location.file).parent if s.location else base
    out = []
    for _, rx in (e for e in _EXTERNAL if e[0] == "script"):
        for m in rx.finditer(s.static_text()):
            ref = m.group(1).rstrip(".,;:")
            if _present(base, here, ref):
                out.append(re.sub(r"^\{\{\w+\}\}/", "", ref))
    out += [f"sensor {name}" for name in s.attrs.get("sensors") or [] if name in checks]
    return list(dict.fromkeys(out))


# ------------------------------------------------------------------------------------------------ repeated text

_MIN_WORDS = 8


def _units(text: str):
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("```", "|-", "---")):
            continue
        for piece in re.split(r"(?<=[.!?;])\s+", line):
            words = re.findall(r"\w+", piece.lower())
            if len(words) >= _MIN_WORDS:
                yield piece.strip(" -*>#|`"), words


def repeated_text(res: Any, sets: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    """Sentences (8+ words) that appear, identical or nearly (80% of the words of the shorter one), in two or more
    files. `together` names the steps that load two or more of those files into the same context."""
    nodes = [n for n in res.ir.nodes.values()
             if (isinstance(n, LLMStep) and _live(n)) or (n.kind == NodeKind.CONTEXT_SOURCE and n.attrs.get("role") != "config")]
    units: list[tuple[str, str, frozenset[str]]] = []
    for n in nodes:
        for text, words in _units(_text(n)):
            units.append((_file(n), text, frozenset(words)))
    parent = list(range(len(units)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    exact: dict[frozenset[str], int] = {}
    shingles: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for i, (_, text, words) in enumerate(units):
        if words in exact:
            parent[find(i)] = find(exact[words])
            continue
        exact[words] = i
        seq = re.findall(r"\w+", text.lower())
        for k in range(len(seq) - 3):
            shingles[tuple(seq[k:k + 4])].append(i)
    for members in shingles.values():
        if len(members) > 40:  # boilerplate shared by many sentences: the exact pass already grouped real copies
            continue
        for a_i, a in enumerate(members):
            for b in members[a_i + 1:]:
                if units[a][0] == units[b][0] or find(a) == find(b):
                    continue
                wa, wb = units[a][2], units[b][2]
                if len(wa & wb) >= 0.8 * min(len(wa), len(wb)):
                    parent[find(b)] = find(a)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(units)):
        groups[find(i)].append(i)
    base = _base(res)
    raw: dict[str, list[str]] = {}

    def line_of(file: str, text: str) -> int:
        if file not in raw:
            try:
                raw[file] = (base / file).read_text(errors="replace").splitlines()
            except OSError:
                raw[file] = []
        return next((i for i, line in enumerate(raw[file], 1) if text in line), None) or \
            next((i for i, line in enumerate(raw[file], 1) if text[:40] in line), 1)

    out = []
    for idx in groups.values():
        files = sorted({units[i][0] for i in idx})
        if len(files) < 2:
            continue
        text = max((units[i][1] for i in idx), key=len)
        together = sorted({d["step"] for d in sets if len({f["file"] for f in d["files"]} & set(files)) >= 2})
        where = [f"{f}:{line_of(f, next(units[i][1] for i in idx if units[i][0] == f))}" for f in files]
        out.append({"text": text if len(text) <= 200 else text[:197] + "...", "files": where, "tokens": count_tokens(text),
                    "together": together})
    out.sort(key=lambda r: (not r["together"], -r["tokens"] * (len(r["files"]) - 1)))
    return out[:limit]


# ------------------------------------------------------------------------------------------------ code

_LLM_IMPORT = re.compile(
    r"""(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|\bimport\s+)["']("""
    r"""@anthropic-ai/[\w-]+|openai|@openai/[\w-]+|@google/genai|@google/generative-ai|@google-cloud/vertexai|"""
    r"""@aws-sdk/client-bedrock[\w-]*|ai|@ai-sdk/[\w-]+|langchain|@langchain/[\w-]+|@mistralai/mistralai|cohere-ai|"""
    r"""groq-sdk|ollama|llamaindex|@huggingface/inference)["']""")
_LLM_URL = re.compile(r"api\.anthropic\.com|api\.openai\.com|bedrock-runtime|generativelanguage\.googleapis\.com|"
                      r"api\.mistral\.ai|api\.groq\.com|openrouter\.ai")
_SPAWN_JS = re.compile(r"\b(?:spawnSync|spawn|execSync|execFileSync|execFile|fork)\s*\(|(?<![.\w])exec\s*\(")
_SPAWN_ANY = re.compile(r"\bBun\.spawn(?:Sync)?\s*\(|\bBun\.\$`|\bexeca\s*\(|\bsubprocess\.(?:run|Popen|call|check_call|"
                        r"check_output)\s*\(|\bos\.(?:system|popen)\s*\(")
_PROGRAM = re.compile(r"""(?:spawnSync|spawn|execSync|execFileSync|execFile|Bun\.spawn(?:Sync)?|execa)\s*\(\s*\[?\s*["'`]"""
                      r"""([\w./-]+)|subprocess\.\w+\(\s*\[\s*["']([\w./-]+)["']|os\.system\(\s*["']([\w./-]+)""")
_ENV_DEFAULT = re.compile(r"""process\.env\.(\w+)\s*(?:\?\?|\|\|)\s*["']([\w-]+)["']|os\.environ\.get\(\s*["'](\w+)["']\s*,\s*["']([\w-]+)["']""")
_REPO_URL = re.compile(r"https?://(?:www\.)?(github\.com|gitlab\.com|bitbucket\.org)/([\w.-]+)/([\w.-]+?)(?:\.git)?"
                       r"(?=[\"'`\s)/]|$)(?!/(?:issues|pull|blob|tree|wiki|discussions|releases|actions|commit))")
_CLONE_LIST = re.compile(r"""["']git["']\s*,\s*["']clone["']""")
_COMMENT = re.compile(r"^\s*(?://|#|\*|/\*)")
_RUNTIMES = {"git", "node", "bun", "deno", "npm", "npx", "pnpm", "yarn", "python", "python3", "sh", "bash", "zsh", "uv",
             "uvx", "pip", "pip3", "ls", "cat", "echo", "rm", "mkdir", "cp", "mv", "which", "env", "test", "true", "false",
             "tar", "chmod", "printf", "sed", "grep", "find", "head", "tail", "sort", "xargs", "open", "code"}
_LANG = {".ts": "ts", ".tsx": "ts", ".js": "js", ".mjs": "js", ".cjs": "js", ".sh": "sh", ".bash": "sh", ".zsh": "sh",
         ".py": "py"}


def code_files(res: Any) -> list[dict[str, Any]]:
    """Code the auditor does not parse (and Python, for what it reaches outside): LLM SDK imports or endpoints,
    programs it starts and external repos it names."""
    base = _base(res)
    out = []
    for rec in res.ir.files:
        if rec.extractor not in ("code", "python") or non_production_path(rec.path):
            continue
        path = base / rec.path
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        code = [(i, line) for i, line in enumerate(lines, 1) if not _COMMENT.match(line)]
        body = "\n".join(line for _, line in code)
        is_js = path.suffix in (".ts", ".tsx", ".js", ".mjs", ".cjs")
        spawns = [i for i, line in code if _SPAWN_ANY.search(line) or (is_js and "child_process" in text and _SPAWN_JS.search(line))]
        programs = {next(g for g in m.groups() if g) for m in _PROGRAM.finditer(body)}
        if spawns:  # a program name taken from the environment, with a literal default: `process.env.X ?? "tool"`
            for m in _ENV_DEFAULT.finditer(body):
                programs.add(f"{m.group(2) or m.group(4)} (env {m.group(1) or m.group(3)})")
        programs = sorted(p for p in programs if p.split(" ")[0].split("/")[-1] not in _RUNTIMES)
        repos = sorted({f"https://{m.group(1)}/{m.group(2)}/{m.group(3)}" for m in _REPO_URL.finditer(body)})
        clone_lines = [i for i, line in code if _CLONE_LIST.search(line) or re.search(r"\bgit clone\b", line)]
        llm = sorted({m.group(1) for m in _LLM_IMPORT.finditer(body)} | {m.group(0) for m in _LLM_URL.finditer(body)})
        out.append({"file": rec.path, "lang": _LANG.get(path.suffix, path.suffix.lstrip(".")), "lines": len(lines),
                    "parsed": rec.extractor == "python", "llm": [] if rec.extractor == "python" else llm,
                    "starts_programs": spawns[:5], "programs": programs, "repos": repos, "clones": clone_lines[:5]})
    return out


# ------------------------------------------------------------------------------------------------ external pieces

_OPTS = r"(?:-{1,2}[\w-]+(?:[ =](?!https?:|git@)\S+)?\s+)*"
_EXTERNAL = [
    ("repo", re.compile(rf"\b(?:git clone|gh repo clone)\s+{_OPTS}([^\s`'\"]+)")),
    ("download", re.compile(r"\b(?:curl|wget)\b[^\n`]*?(https?://[^\s`'\"|)]+)([^\n`]*)")),
    ("package", re.compile(r"\b(?:uvx|pipx run)\s+--from\s+([^\s`'\"]+)")),
    ("package", re.compile(r"\b(?:uvx|pipx run|npx|bunx)\s+(?:-y\s+)?([@\w][\w@./:+-]*)")),
    ("script", re.compile(r"(?<![\w/.])((?:\./|scripts/|bin/)[\w./-]+\.(?:sh|py|js|mjs|ts|rb))\b")),
    ("script", re.compile(r"\b(?:bash|sh|python3?|node|bun)\s+([\w./{}-]+\.(?:sh|py|js|mjs|ts))\b")),
]
# placeholders and local addresses are not something to fetch
_NOT_A_PIECE = re.compile(r"[$<>]|^file:|localhost|127\.0\.0\.1|0\.0\.0\.0|example\.(?:com|org)")
# a download is code or instructions when it is run by a shell or is a script, document or archive; API calls are not
_FETCHED_CODE = re.compile(r"\.(?:sh|py|js|mjs|ps1|md|txt|ya?ml|tar\.gz|tgz|zip)$")
_PIPED = re.compile(r"\|\s*(?:sudo\s+)?(?:ba|z)?sh\b|\|\s*python")


def _present(base: Path, here: Path, ref: str) -> bool:
    ref = re.sub(r"^\{\{\w+\}\}/", "", ref)
    return any((d / ref).exists() for d in (here, *here.parents) if d == base or base in d.parents)


def external_pieces(res: Any, code: list[dict[str, Any]]) -> list[dict[str, str]]:
    base = _base(res)
    out: dict[tuple[str, str], dict[str, str]] = {}

    def add(kind: str, ref: str, used_by: str, location: str) -> None:
        e = out.setdefault((kind, ref), {"kind": kind, "ref": ref, "used_by": "", "location": location, "users": []})
        if used_by and used_by not in e["users"]:
            e["users"].append(used_by)
            e["used_by"] = ", ".join(e["users"][:3]) + (f" and {len(e['users']) - 3} more" if len(e["users"]) > 3 else "")

    for s in res.ir.llm_steps():
        if not _live(s):
            continue
        here = (base / s.location.file).parent if s.location else base
        for kind, rx in _EXTERNAL:
            for m in rx.finditer(s.static_text()):
                ref = m.group(1).rstrip(".,;:")
                if _NOT_A_PIECE.search(ref):
                    continue
                if kind == "download" and not (_FETCHED_CODE.search(ref) or _PIPED.search(m.group(2))):
                    continue
                if kind == "script" and _present(base, here, ref):
                    continue  # it ships with the audited files
                add(kind, ref, s.name, _file(s))
    for n in res.ir.nodes.values():
        for ref in n.attrs.get("missing_refs", []):
            add("file", ref, n.name if isinstance(n, LLMStep) else _file(n), _file(n))
    for c in code:
        for repo in c["repos"]:
            add("repo", repo, c["file"], c["file"])
        if c["clones"] and not c["repos"]:
            add("repo", "(URL built at run time)", c["file"], f"{c['file']}:{c['clones'][0]}")
        for prog in c["programs"]:
            add("program", prog, c["file"], c["file"])
    for node in res.ir.of_kind(NodeKind.TOOL):
        if node.attrs.get("mcp_server"):
            add("mcp", node.name, "", _file(node))
    order = ["repo", "download", "package", "program", "script", "mcp", "file"]
    return sorted(out.values(), key=lambda e: order.index(e["kind"]))


# ------------------------------------------------------------------------------------------------ map

def build_map(res: Any) -> dict[str, Any]:
    sets = load_sets(res)
    code = code_files(res)
    checks = [{"name": n.name, "command": n.attrs.get("command"), "location": _file(n)}
              for n in res.ir.of_kind(NodeKind.TOOL) if n.attrs.get("check")]
    ctx = res.ir.of_kind(NodeKind.CONTEXT_SOURCE)
    loaded = {f["file"] for d in sets for f in d["files"]}
    unread = sorted(_file(n) for n in ctx if n.attrs.get("role") == "knowledge" and _file(n) not in loaded
                    and not any(p in ("tests", "test", "examples", "docs") for p in _file(n).split("/")[:-1]))
    return {
        "steps": sets,
        "context_files": sum(1 for n in ctx if n.attrs.get("role") != "config"),
        "config_files": sum(1 for n in ctx if n.attrs.get("role") == "config"),
        "checks": checks,
        "unread_knowledge": unread,
        "repeated": repeated_text(res, sets),
        "code": code,
        "external": external_pieces(res, code),
    }


def render_map_markdown(m: dict[str, Any], limit: int = 25) -> list[str]:
    kinds: dict[str, int] = defaultdict(int)
    for d in m["steps"]:
        kinds[d["kind"].split(" ", 1)[1]] += 1
    out = ["", "### Workflow map", "",
           f"Steps: {len(m['steps'])} ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items())) or 'none'}) · context "
           f"files: {m['context_files']} · config: {m['config_files']} · deterministic checks: {len(m['checks'])} · code "
           f"files: {len(m['code'])}", ""]
    if m["steps"]:
        out += ["What each step loads into its context (its text, lead agent, knowledge, always-loaded memory and the files "
                "they tell the agent to read; tokens are estimates), what more it can reach by following references, and "
                "what it runs:", "",
                "| step | kind | loads | ~tokens | + reachable | runs | referenced, not in the folder |",
                "|---|---|---|---|---|---|---|"]
        for d in m["steps"][:limit]:
            loads = ", ".join(f"`{f['file']}` ({f['as']}, {f['tokens']})" for f in d["files"])
            more = f"{d['reachable']['files']} files, {d['reachable']['tokens']}" if d["reachable"]["files"] else "-"
            out.append(f"| {d['step']} (`{d['location']}`) | {d['kind']} | {loads} | {d['tokens']} | {more} | "
                       f"{', '.join(d['runs']) or '-'} | {', '.join(d['missing']) or '-'} |")
        if len(m["steps"]) > limit:
            out.append(f"\n{len(m['steps']) - limit} more steps in the JSON output (`-f json`).")
    if m["checks"]:
        out += ["", "Deterministic checks (sensors, hooks): " + "; ".join(
            f"{c['name']} (`{c['command']}`)" if c["command"] else c["name"] for c in m["checks"])]
    if m["unread_knowledge"]:
        out += ["", f"Knowledge no step was found to read ({len(m['unread_knowledge'])}): "
                + ", ".join(f"`{f}`" for f in m["unread_knowledge"][:15]) + (" ..." if len(m["unread_knowledge"]) > 15 else "")]
    out += ["", f"### Repeated text ({len(m['repeated'])})", ""]
    if m["repeated"]:
        out += ["Sentences found in several files. 'Loaded together by' means they end up twice in the same context.", "",
                "| text | files | ~tokens | loaded together by |", "|---|---|---|---|"]
        out += [f"| {r['text'].replace('|', '/')} | {', '.join(f'`{f}`' for f in r['files'])} | {r['tokens']} | "
                f"{', '.join(r['together']) or '-'} |" for r in m["repeated"][:limit]]
    else:
        out.append("None found.")
    unparsed = [c for c in m["code"] if not c["parsed"]]
    out += ["", f"### Code the auditor does not parse ({len(unparsed)})", ""]
    if unparsed:
        langs: dict[str, int] = defaultdict(int)
        for c in unparsed:
            langs[c["lang"]] += 1
        llm = [c for c in unparsed if c["llm"]]
        out.append(f"{', '.join(f'{v} {k}' for k, v in sorted(langs.items()))}. Imports of an LLM SDK or calls to an LLM API: "
                   + (", ".join(f"`{c['file']}` ({', '.join(c['llm'])})" for c in llm) if llm else
                      "none found (import scan): read them as deterministic code."))
    noteworthy = [c for c in m["code"] if c["starts_programs"] or c["repos"] or c["clones"]]
    if noteworthy:
        out += ["", "| file | starts programs (lines) | programs | repos |", "|---|---|---|---|"]
        out += [f"| `{c['file']}` | {', '.join(map(str, c['starts_programs'])) or '-'} | {', '.join(c['programs']) or '-'} | "
                f"{', '.join(c['repos']) or ('cloned, URL built at run time' if c['clones'] else '-')} |" for c in noteworthy[:limit]]
    if not m["code"]:
        out.append("No code files.")
    out += ["", f"### External pieces ({len(m['external'])})", ""]
    if m["external"]:
        out += [f"- {e['kind']} `{e['ref']}`" + (f" — used by {e['used_by']}" if e["used_by"] else "")
                + (f" (`{e['location']}`)" if e["location"] and e["location"] != e["used_by"] else "")
                for e in m["external"][:limit * 2]]
    else:
        out.append("None found.")
    return out
