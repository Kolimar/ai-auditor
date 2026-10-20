"""Python extractor: AST + lightweight intra/inter-procedural data flow -> IR.

What it recovers per LLM step: model, prompt parts (with variable origins),
output contract, tools, parameters, enclosing loops/retries, validations of its
output, branches it controls, and which other steps consume its output.

Inter-procedural facts are computed as function summaries and iterated to a
fixpoint (a few rounds), so ``label = classify(t); if label == "x": ...`` in one
function links the step inside ``classify`` to the branch in the caller, and a
generic ``ask(prompt)`` helper is materialized as one step per call site.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from ai_auditor.ir.model import (
    EdgeKind,
    Enforcement,
    LLMStep,
    Node,
    NodeKind,
    OutputKind,
    OutputSpec,
    PromptPart,
    PromptVariable,
    SourceLocation,
    StepKind,
    SystemIR,
    VarSource,
    stable_id,
)
from ai_auditor.parser.python import registry as R
from ai_auditor.parser.python.index import Module, ProjectIndex
from ai_auditor.parser.python.resolve import MISSING, Resolver, Template, _dotted, collect_assigns, name_hint, src
from ai_auditor.parser.tokens import count_tokens

EXTRACTOR_VERSION = "py-6"  # bump whenever the extracted IR changes (it keys the IR cache)
_MAX_ROUNDS = 4
FnNode = ast.FunctionDef | ast.AsyncFunctionDef


# ----------------------------------------------------------------------------- helpers
_NON_PROD_DIRS = {"tests", "test", "testing", "examples", "example", "samples", "sample", "docs"}


def non_production_path(rel: str) -> bool:
    """Test suites, examples, samples and docs: analyzed for the graph, never reported as production findings."""
    *dirs, name = rel.split("/")
    return any(d in _NON_PROD_DIRS or d.endswith("_tests") or d.startswith("tests_") for d in dirs) or \
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def attr_chain(func: ast.expr) -> list[str]:
    parts: list[str] = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    elif isinstance(cur, ast.Call):
        parts.append("()")
    return list(reversed(parts))


def receiver_of(func: ast.expr, depth: int) -> ast.expr | None:
    cur = func
    for _ in range(depth):
        if not isinstance(cur, ast.Attribute):
            return None
        cur = cur.value
    return cur


def kw(call: ast.Call, *names: str) -> ast.expr | None:
    for k in call.keywords:
        if k.arg in names:
            return k.value
    return None


def exc_names(handler: ast.ExceptHandler) -> set[str]:
    t = handler.type
    if t is None:
        return {"*"}
    elts = t.elts if isinstance(t, ast.Tuple) else [t]
    return {e.attr if isinstance(e, ast.Attribute) else getattr(e, "id", "?") for e in elts}


def is_dead_test(test: ast.expr) -> bool:
    return isinstance(test, ast.Constant) and not test.value


def labels_in(test: ast.AST) -> list[str]:
    out: list[str] = []
    for n in ast.walk(test):
        if isinstance(n, ast.Compare):
            for c in [n.left, *n.comparators]:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    out.append(c.value)
                elif isinstance(c, (ast.List, ast.Tuple, ast.Set)):
                    out += [e.value for e in c.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("startswith", "endswith"):
            out += [a.value for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return list(dict.fromkeys(out))


@dataclass
class Summary:
    returns: frozenset[str] = frozenset()  # step ids whose output the function returns
    param_flows: dict[str, frozenset[str]] = field(default_factory=dict)  # param -> steps whose prompt uses it
    reach: frozenset[str] = frozenset()  # all steps executed by calling this function (transitive)

    def key(self) -> tuple:
        return (self.returns, tuple(sorted(self.param_flows.items())), self.reach)


@dataclass
class FnResult:
    steps: dict[str, LLMStep] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[tuple[str, str, EdgeKind, dict]] = field(default_factory=list)
    returns: set[str] = field(default_factory=set)
    param_flows: dict[str, set[str]] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)  # project calls: callee, loops, retries, line
    sequence: list[dict[str, Any]] = field(default_factory=list)
    agent_vars: dict[str, str] = field(default_factory=dict)
    pending_delegations: list[tuple[str, str]] = field(default_factory=list)  # (step id, agent var name)
    invocations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Ctx:
    mod: Module
    fn: FnNode | None
    qualname: str
    cls_name: str | None

    @property
    def component(self) -> str:
        if self.fn is None:
            return self.mod.rel.rsplit("/", 1)[-1].removesuffix(".py")
        return self.fn.name


# ----------------------------------------------------------------------------- analyzer
class PythonProjectExtractor:
    def __init__(self, index: ProjectIndex) -> None:
        self.index = index
        self.summaries: dict[str, Summary] = {}
        self.wrappers: dict[str, tuple[Module, FnNode]] = {}
        self._assigns: dict[int, dict[str, list[tuple[int, ast.expr]]]] = {}
        self.callers: dict[str, int] = {}
        self.agent_steps: dict[tuple[str, str], str] = {}  # (module, var) -> step id

    # -- entry -------------------------------------------------------------------
    def extract(self) -> SystemIR:
        ctxs = self._contexts()
        self._find_wrappers(ctxs)
        results: dict[str, FnResult] = {}
        deps = self._static_deps(ctxs)
        todo = ctxs
        for _ in range(_MAX_ROUNDS):
            # a function's analysis depends only on the summaries of the project functions it calls (and on the agent
            # table): later rounds re-run just the functions whose dependencies changed
            results.update({c.qualname: FunctionAnalyzer(self, c).run() for c in todo})
            new = self._summarize(results)
            agents = {k: v for r in results.values() for k, v in r.agent_vars.items()}
            changed = {k for k, v in new.items() if self.summaries.get(k, Summary()).key() != v.key()} | \
                {k for k in self.summaries if k not in new}
            stable = agents == self.agent_steps and not changed
            agents_changed = agents != self.agent_steps
            self.summaries, self.agent_steps = new, agents  # type: ignore[assignment]
            if stable:
                break
            todo = ctxs if agents_changed else [c for c in ctxs if deps[c.qualname] & changed]
            if not todo:
                break
        return self._emit(ctxs, results)

    def _static_deps(self, ctxs: list[Ctx]) -> dict[str, set[str]]:
        """Project functions each context calls (directly or through a materialized wrapper's body)."""
        direct: dict[str, set[str]] = {}
        for c in ctxs:
            body = c.fn if c.fn is not None else c.mod.tree
            res = Resolver(self.index, c.mod, c.fn, {}, cls_name=c.cls_name)
            out: set[str] = set()
            for n in ast.walk(body):
                if isinstance(n, ast.Call):
                    hit = res._project_function(n)
                    if hit is not None:
                        out.add(self.qualname_of(*hit))
            direct[c.qualname] = out
        return {qn: ds | set().union(*(direct.get(w, set()) for w in ds if w in self.wrappers)) for qn, ds in direct.items()}

    def _contexts(self) -> list[Ctx]:
        out: list[Ctx] = []
        seen: set[int] = set()
        for mod in self.index.by_rel.values():
            out.append(Ctx(mod, None, f"{mod.name}:<module>", None))
            for qn, fn in mod.functions.items():
                if id(fn) in seen:
                    continue
                seen.add(id(fn))
                cls = qn.split(".")[0] if "." in qn else None
                out.append(Ctx(mod, fn, f"{mod.name}:{qn}", cls))
        return out

    def assigns_of(self, fn: FnNode) -> dict[str, list[tuple[int, ast.expr]]]:
        hit = self._assigns.get(id(fn))
        if hit is None:
            hit = self._assigns[id(fn)] = collect_assigns(fn)
        return hit

    def qualname_of(self, mod: Module, fn: FnNode) -> str:
        for qn, f in mod.functions.items():
            if f is fn:
                return f"{mod.name}:{qn}"
        return f"{mod.name}:{fn.name}"

    def _find_wrappers(self, ctxs: list[Ctx]) -> None:
        """A wrapper is a function with a direct LLM call whose prompt comes from its parameters."""
        for c in ctxs:
            if c.fn is None:
                continue
            calls = [n for n in ast.walk(c.fn) if isinstance(n, ast.Call)]
            if not calls:
                continue
            res = Resolver(self.index, c.mod, c.fn, {}, cls_name=c.cls_name)

            def llm_calls(r: Resolver) -> list[ast.Call]:
                out = []
                for node in calls:
                    m = match_direct(node, r, self)
                    if m is not None and m[0] in ("sdk", "func", "lc"):
                        out.append(node)
                return out

            candidates = llm_calls(res)
            if not candidates and LLM_CALL_HINT.search(src(c.mod, c.fn)):
                # the client may be created locally (client = OpenAI() inside the function): resolve with assignments
                candidates = llm_calls(Resolver(self.index, c.mod, c.fn, collect_assigns(c.fn), cls_name=c.cls_name))
            if not candidates:
                continue
            params = set(res.params) - {"self", "cls"}
            if not params:
                continue
            res = Resolver(self.index, c.mod, c.fn, collect_assigns(c.fn), cls_name=c.cls_name)  # assignments only when needed
            dead = {id(n) for st in ast.walk(c.fn) if isinstance(st, ast.If) and is_dead_test(st.test)
                    for b in st.body for n in ast.walk(b)}
            for node in candidates:
                if id(node) in dead:
                    continue
                prompt_exprs = [k.value for k in node.keywords if k.arg in PROMPT_KWARGS] + list(node.args)
                used = {n.id for e in prompt_exprs for n in ast.walk(e) if isinstance(n, ast.Name)}
                # follow one level of local assignment (messages = [...] built from params)
                for name in list(used):
                    for _, v in res.assigns.get(name, []):
                        used |= {n.id for n in ast.walk(v) if isinstance(n, ast.Name)}
                if not used & params:
                    continue
                # Generic helper only if the function contributes (almost) no instructions of its own:
                # `classify(text)` with its own system prompt is a step; `ask(prompt)` is a wrapper.
                static = "".join(_static_prompt_text(e, res) for e in prompt_exprs) + _chain_template_text(node, res)
                static = GENERIC_ASSISTANT.sub("", re.sub(r"\{[^{}]*\}", "", static))
                if len(re.findall(r"\w+", static)) < 3:
                    self.wrappers[c.qualname] = (c.mod, c.fn)
                    break
        if not self.wrappers:
            return
        # count project call sites of each wrapper (only calls whose name matches a wrapper's)
        short = {qn.rsplit(":", 1)[-1].rsplit(".", 1)[-1] for qn in self.wrappers}
        for c in ctxs:
            body = c.fn if c.fn is not None else c.mod.tree
            res = None
            for node in ast.walk(body):
                if not isinstance(node, ast.Call):
                    continue
                fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
                if fname not in short:
                    continue
                res = res or Resolver(self.index, c.mod, c.fn, {}, cls_name=c.cls_name)
                hit = res._project_function(node)
                if hit:
                    qn = self.qualname_of(*hit)
                    if qn in self.wrappers and qn != c.qualname:
                        self.callers[qn] = self.callers.get(qn, 0) + 1

    def _summarize(self, results: dict[str, FnResult]) -> dict[str, Summary]:
        reach: dict[str, set[str]] = {qn: set(r.steps) for qn, r in results.items()}
        for _ in range(6):  # transitive closure over the (small) call graph
            changed = False
            for qn, r in results.items():
                for call in r.calls:
                    extra = reach.get(call["callee"], set()) - reach[qn]
                    if extra:
                        reach[qn] |= extra
                        changed = True
            if not changed:
                break
        return {
            qn: Summary(frozenset(r.returns), {p: frozenset(s) for p, s in r.param_flows.items()}, frozenset(reach[qn]))
            for qn, r in results.items()
        }

    # -- emission ------------------------------------------------------------------
    def _emit(self, ctxs: list[Ctx], results: dict[str, FnResult]) -> SystemIR:
        ir = SystemIR(root="")
        for r in results.values():
            for s in r.steps.values():
                if s.id not in ir.nodes:
                    ir.add(s)
            for n in r.nodes.values():
                if n.id not in ir.nodes:
                    ir.add(n)
        seen_edges: set[tuple] = set()

        def link(a: str, b: str, kind: EdgeKind, attrs: dict) -> None:
            key = (a, b, kind)
            if a in ir.nodes and b in ir.nodes and a != b and key not in seen_edges:
                seen_edges.add(key)
                ir.link(a, b, kind, **attrs)

        agent_map: dict[tuple[str, str], str] = {}
        for r in results.values():
            agent_map.update({k: v for k, v in r.agent_vars.items()})  # type: ignore[arg-type]
        for qn, r in results.items():
            for a, b, kind, attrs in r.edges:
                link(a, b, kind, attrs)
            modname = qn.split(":")[0]
            for sid, var in r.pending_delegations:
                target = agent_map.get((modname, var)) or next((v for (m, n), v in agent_map.items() if n == var), None)
                if target:
                    link(sid, target, EdgeKind.DELEGATES, {"via": "handoff/tool"})
            for inv in r.invocations:
                target = agent_map.get((modname, inv["var"])) or next((v for (m, n), v in agent_map.items() if n == inv["var"]), None)
                if not target or target not in ir.nodes:
                    continue
                step = ir.nodes[target]
                assert isinstance(step, LLMStep)
                if inv["template"] is not None and not any(p.role == "user" for p in step.prompt):
                    t = inv["template"]
                    step.prompt.append(PromptPart("user", t.text, t.variables, inv["location"]))
                if inv.get("max_turns") is not None:
                    step.max_iterations = inv["max_turns"]
                    step.attrs.setdefault("provenance", {})["max_iterations"] = "literal"
                for t in inv["taint"]:
                    link(t, target, EdgeKind.DATA_FLOW, {"via": "agent_input"})
                for lp in inv["loops"]:
                    link(lp, target, EdgeKind.CONTAINS, {"via": "invocation"})
            # loops / retries in the caller apply to every step reachable through the call
            for call in r.calls:
                reach = self.summaries.get(call["callee"], Summary()).reach
                for sid in reach:
                    for lp in call["loops"]:
                        link(lp, sid, EdgeKind.CONTAINS, {"via": "call", "line": call["line"]})
                    for rt in call["retries"]:
                        link(rt, sid, EdgeKind.RETRIES, {"via": "call"})
                    if call.get("entry"):
                        node = ir.nodes.get(sid)
                        if node is not None:
                            node.attrs.setdefault("entrypoints", [])
                            if call["entry"] not in node.attrs["entrypoints"]:
                                node.attrs["entrypoints"].append(call["entry"])
        # entrypoint propagation through more than one call level
        self._propagate_entrypoints(ir, results)
        # orchestrating functions with >= 2 sequential LLM operations become workflow nodes
        for c in ctxs:
            r = results[c.qualname]
            if len(r.sequence) >= 2:
                wid = stable_id("wf", c.qualname)
                if wid not in ir.nodes:
                    ir.add(Node(wid, NodeKind.WORKFLOW, c.component, SourceLocation(c.mod.rel, getattr(c.fn, "lineno", 1)),
                                {"sequence": r.sequence, "qualname": c.qualname}))
                for item in r.sequence:
                    for sid in item["steps"]:
                        link(wid, sid, EdgeKind.CONTAINS, {})
        return ir

    def _propagate_entrypoints(self, ir: SystemIR, results: dict[str, FnResult]) -> None:
        entry_of: dict[str, set[str]] = {}
        for qn, r in results.items():
            for call in r.calls:
                if call.get("entry"):
                    entry_of.setdefault(call["callee"], set()).add(call["entry"])
        for _ in range(4):
            for qn, r in results.items():
                for call in r.calls:
                    for e in entry_of.get(qn, ()):  # caller's entry flows to callee
                        entry_of.setdefault(call["callee"], set()).add(e)
        for qn, entries in entry_of.items():
            for sid in self.summaries.get(qn, Summary()).reach:
                node = ir.nodes.get(sid)
                if node is not None:
                    lst = node.attrs.setdefault("entrypoints", [])
                    for e in sorted(entries):
                        if e not in lst:
                            lst.append(e)


PROMPT_KWARGS = {"messages", "system", "input", "instructions", "contents", "prompt"}


def fq_name(func: ast.expr, res: Resolver) -> str | None:
    chain = attr_chain(func)
    if not chain or chain[0] == "()":
        return None
    base = chain[0]
    fq = res.mod.imports.get(base)
    if fq is None:
        if base in res.mod.functions or base in res.mod.classes:
            fq = f"{res.mod.name}.{base}"
        else:
            return None
    return ".".join([fq, *chain[1:]])


def ctor_fq(expr: ast.expr | None, res: Resolver, depth: int = 0) -> str | None:
    """Fully-qualified constructor that produced the value of `expr`, if traceable."""
    if expr is None or depth > 5:
        return None
    if isinstance(expr, ast.Call):
        f = expr.func
        # x.with_structured_output(...) / x.bind_tools(...) keep x's type
        if isinstance(f, ast.Attribute) and f.attr in ("with_structured_output", "bind_tools", "bind", "with_retry",
                                                        "with_config", "with_options"):
            return ctor_fq(f.value, res, depth + 1)
        return fq_name(f, res)
    if isinstance(expr, ast.Name):
        if expr.id in res.bindings:
            caller, e = res.bindings[expr.id]
            return ctor_fq(e, caller, depth + 1)
        lv = res.local_value(expr.id, getattr(expr, "lineno", None))
        if lv is not None:
            return ctor_fq(lv, res, depth + 1)
        mv = res.module_value(expr.id)
        if mv is not None:
            r = res if mv[0] is res.mod else res.foreign(mv[0])
            return ctor_fq(mv[1], r, depth + 1)
        return res.mod.imports.get(expr.id)
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == "self" and res.cls_name:
        v = res.mod.instance_attrs.get(f"{res.cls_name}.{expr.attr}")
        return ctor_fq(v, res, depth + 1) if v is not None else None
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr):  # LCEL: prompt | llm | parser
        for side in (expr.right, expr.left):
            got = ctor_fq(side, res, depth + 1)
            if got and (got in R.CHAT_MODEL_CTORS or got.startswith("langchain")):
                return got
    return None


def match_direct(call: ast.Call, res: Resolver, ex: PythonProjectExtractor) -> tuple[str, Any] | None:
    """Classify a call: ('sdk', CallSig) | ('func', fw) | ('lc', provider) | ('agent', (fq, AgentSig)) |
    ('run', None) | ('wrapper', qualname) | None."""
    f = call.func
    fq = fq_name(f, res)
    if fq in R.AGENT_CTORS:
        return "agent", (fq, R.AGENT_CTORS[fq])
    if fq in R.FUNC_SIGS:
        return "func", R.FUNC_SIGS[fq]
    if isinstance(f, ast.Attribute) and f.attr in R.AGENT_RUN_METHODS:
        if fq and fq.startswith("agents.Runner"):
            return "run", None
        recv = ctor_fq(f.value, res)
        if recv in R.AGENT_CTORS:
            return "run", None
    chain = attr_chain(f)
    for sig in R.CALL_SIGS:
        n = len(sig.chain)
        if len(chain) > n and tuple(chain[-n:]) == sig.chain:
            recv = receiver_of(f, n)
            mod = ctor_fq(recv, res) if recv is not None else None
            if mod and any(mod.startswith(m) for m in sig.client_modules):
                return "sdk", sig
            if mod is None:
                kws = {k.arg for k in call.keywords}
                if "model" in kws and kws & R.LLM_KWARG_EVIDENCE:
                    return "sdk", sig
    if isinstance(f, ast.Attribute) and f.attr in R.INVOKE_METHODS:
        recv = ctor_fq(f.value, res)
        if recv in R.CHAT_MODEL_CTORS:
            return "lc", R.CHAT_MODEL_CTORS[recv]
    hit = res._project_function(call)
    if hit is not None:
        qn = ex.qualname_of(*hit)
        if qn in ex.wrappers and ex.callers.get(qn, 0) > 0:
            return "wrapper", qn
    return None


class FunctionAnalyzer:
    def __init__(self, ex: PythonProjectExtractor, ctx: Ctx) -> None:
        self.ex = ex
        self.ctx = ctx
        self.mod = ctx.mod
        self.assigns = ex.assigns_of(ctx.fn) if ctx.fn is not None else {}
        self.res = Resolver(ex.index, ctx.mod, ctx.fn, self.assigns, self._classify, cls_name=ctx.cls_name)
        self.out = FnResult()
        self.taint: dict[str, set[str]] = {}
        self.ctl: list[set[str]] = []  # taint of the enclosing branch conditions (implicit flow)
        self.branch: list[str] = []  # enclosing if-branches as "line:col:body|else" (mutually exclusive paths)
        self.origin: dict[str, tuple[VarSource, str | None]] = {}
        self.loops: list[str] = []
        self.retries: list[str] = []
        self.trys: list[set[str]] = []
        self.gather_depth = 0
        self.call_step: dict[int, str] = {}
        self.history_vars: set[str] = set()
        self.entry: str | None = self._entry_kind()
        self.is_wrapper_def = ctx.qualname in ex.wrappers and ex.callers.get(ctx.qualname, 0) > 0
        self.decorator_retry: str | None = None
        self.top_level_ids: set[int] = set()

    # -- context -------------------------------------------------------------------
    def _entry_kind(self) -> str | None:
        fn = self.ctx.fn
        if fn is None:
            return None
        for d in fn.decorator_list:
            target = d.func if isinstance(d, ast.Call) else d
            if isinstance(target, ast.Attribute) and target.attr in R.WEB_DECORATORS:
                return "web"
        return None

    def loc(self, node: ast.AST) -> SourceLocation:
        return SourceLocation(self.mod.rel, getattr(node, "lineno", None), getattr(node, "end_lineno", None))

    # -- main ------------------------------------------------------------------------
    def run(self) -> FnResult:
        fn = self.ctx.fn
        if fn is None:
            self._module_level()
            return self.out
        self._decorator_retry(fn)
        if self.decorator_retry:
            self.retries.append(self.decorator_retry)
        self.top_level_ids = {id(s) for s in fn.body}
        self.walk(fn.body)
        if any(isinstance(k, tuple) for k in self.call_step):
            self._mark_full_document_expansion(fn)
        return self.out

    def _mark_full_document_expansion(self, fn: ast.AST) -> None:
        """`docs = retriever.invoke(q)` then `open(d.metadata["path"]).read() for d in docs`: hits are swapped for whole files."""
        retr_vars: dict[str, str] = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                rid = self.call_step.get(("retr", id(n.value)))  # type: ignore[call-overload]
                if rid:
                    retr_vars.update({tg.id: rid for tg in n.targets if isinstance(tg, ast.Name)})
        if not retr_vars:
            return
        for n in ast.walk(fn):
            iters = [g.iter for g in n.generators] if isinstance(n, (ast.ListComp, ast.GeneratorExp, ast.SetComp)) else \
                [n.iter] if isinstance(n, (ast.For, ast.AsyncFor)) else []
            for it in iters:
                rid = retr_vars.get(it.id) if isinstance(it, ast.Name) else None
                if rid and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("read", "read_text")
                               for c in ast.walk(n)):
                    self.out.nodes[rid].attrs["full_documents"] = True

    def _module_level(self) -> None:
        stmts = []
        for st in self.mod.tree.body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if isinstance(st, ast.If) and "__name__" in src(self.mod, st.test):
                self.entry = "script"
                self.walk(st.body)
                self.entry = None
                continue
            stmts.append(st)
        self.top_level_ids = {id(s) for s in stmts}
        self.walk(stmts)

    def _decorator_retry(self, fn: FnNode) -> None:
        for d in fn.decorator_list:
            call = d if isinstance(d, ast.Call) else None
            target = d.func if call else d
            fq = fq_name(target, self.res) or ""
            if fq in R.TENACITY_RETRY or fq.endswith("tenacity.retry") or (isinstance(target, ast.Name) and target.id == "retry"
                                                                          and "tenacity" in str(self.mod.imports.get("retry", ""))):
                max_attempts = None
                excs: set[str] = set()
                if call:
                    for n in ast.walk(call):
                        if isinstance(n, ast.Call):
                            nm = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                            if nm == "stop_after_attempt" and n.args:
                                v = self.res.const(n.args[0])
                                max_attempts = v if isinstance(v, int) else None
                            if nm in ("retry_if_exception_type",):
                                for a in n.args:
                                    for e in (a.elts if isinstance(a, ast.Tuple) else [a]):
                                        excs.add(e.attr if isinstance(e, ast.Attribute) else getattr(e, "id", "?"))
                    if fq.startswith("backoff"):
                        mt = kw(call, "max_tries")
                        v = self.res.const(mt) if mt is not None else MISSING
                        max_attempts = v if isinstance(v, int) else None
                        excs |= {getattr(a, "attr", getattr(a, "id", "?")) for a in call.args[1:2]}
                has_stop = call is not None and (kw(call, "stop") is not None or kw(call, "max_tries") is not None)
                rid = stable_id("retry", self.mod.rel, d.lineno)
                self.out.nodes[rid] = Node(rid, NodeKind.RETRY, f"retry:{fn.name}", self.loc(d), {
                    "mechanism": "decorator", "max_attempts": max_attempts, "unbounded": not has_stop,
                    "exceptions": sorted(excs), "trigger": _trigger(excs)})
                self.decorator_retry = rid

    # -- statements ----------------------------------------------------------------------
    def walk(self, stmts: list[ast.stmt]) -> None:
        for st in stmts:
            self.visit(st)

    def visit(self, st: ast.stmt) -> None:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            value = st.value
            if value is None:
                return
            targets = st.targets if isinstance(st, ast.Assign) else [st.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            for t in targets:
                if isinstance(t, ast.Tuple):
                    names += [e.id for e in t.elts if isinstance(e, ast.Name)]
            self.scan(value, assign_to=names[0] if names else None, stmt=st)
            tset = self.taint_of(value) | self._ctl()
            for n in names:
                if isinstance(st, ast.AugAssign):
                    self.taint.setdefault(n, set()).update(tset)
                else:
                    self.taint[n] = set(tset)
                org = self._origin_of(value)
                if org:
                    self.origin[n] = org
            return
        if isinstance(st, ast.Expr):
            self.scan(st.value, stmt=st)
            v = st.value
            # kept.append(doc) / seen.add(x): the container now carries its arguments' taint (and the branch's)
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Name) \
                    and v.func.attr in ("append", "extend", "add", "insert", "update", "setdefault", "appendleft"):
                extra = self._ctl().union(*(self.taint_of(a) for a in v.args))
                if extra:
                    self.taint.setdefault(v.func.value.id, set()).update(extra)
            return
        if isinstance(st, ast.Return):
            if st.value is not None:
                self.scan(st.value, stmt=st)
                self.out.returns |= self.taint_of(st.value) | self._ctl()
            return
        if isinstance(st, ast.If):
            if is_dead_test(st.test) or self._const_false(st.test):
                self.walk(st.orelse)
                return
            self.scan(st.test, stmt=st)
            self.control_sink(st.test, st)
            self.ctl.append(self.taint_of(st.test))
            self.branch.append(f"{st.lineno}:{st.col_offset}:body")
            self.walk(st.body)
            self.branch[-1] = f"{st.lineno}:{st.col_offset}:else"
            self.walk(st.orelse)
            self.branch.pop()
            self.ctl.pop()
            return
        if isinstance(st, (ast.For, ast.AsyncFor, ast.While)):
            self.visit_loop(st)
            return
        if isinstance(st, ast.Try) or (hasattr(ast, "TryStar") and isinstance(st, ast.TryStar)):
            caught: set[str] = set()
            for h in st.handlers:
                caught |= exc_names(h)
            self.trys.append(caught)
            self.walk(st.body)
            self.trys.pop()
            for h in st.handlers:
                self.walk(h.body)
            self.walk(st.orelse)
            self.walk(st.finalbody)
            return
        if isinstance(st, (ast.With, ast.AsyncWith)):
            for item in st.items:
                self.scan(item.context_expr, stmt=st)
            self.walk(st.body)
            return
        if isinstance(st, ast.Match):
            self.scan(st.subject, stmt=st)
            labels = []
            for case in st.cases:
                for n in ast.walk(case.pattern):
                    if isinstance(n, ast.MatchValue) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                        labels.append(n.value.value)
            self.control_sink(st.subject, st, extra_labels=labels)
            for case in st.cases:
                self.walk(case.body)
            return
        if isinstance(st, ast.Assert):
            self.scan(st.test, stmt=st)
            steps = self.taint_of(st.test)
            if steps:
                self.add_validation(st, steps, "assert", src(self.mod, st.test))
            return
        for child in ast.iter_child_nodes(st):
            if isinstance(child, ast.expr):
                self.scan(child, stmt=st)

    # -- loops and retries -------------------------------------------------------------------
    def visit_loop(self, st: ast.For | ast.AsyncFor | ast.While) -> None:
        retry = self._retry_loop(st)
        if retry is not None:
            rid, attrs = retry
            self.out.nodes[rid] = Node(rid, NodeKind.RETRY, f"retry-loop:{self.ctx.component}", self.loc(st), attrs)
            self.retries.append(rid)
            if not isinstance(st, ast.While):
                self.scan(st.iter, stmt=st)
            self.walk(st.body)
            self.retries.pop()
            self.walk(st.orelse)
            return
        lid = stable_id("loop", self.mod.rel, st.lineno, st.col_offset)
        attrs: dict[str, Any] = {"bounded": None}
        if isinstance(st, (ast.For, ast.AsyncFor)):
            self.scan(st.iter, stmt=st)
            it_src = src(self.mod, st.iter)
            attrs.update(bounded=True, iter=it_src[:120], batch_data=self._is_batch_iter(st.iter),
                         target=src(self.mod, st.target))
            tset = self.taint_of(st.iter)
            for n in ast.walk(st.target):
                if isinstance(n, ast.Name):
                    self.taint[n.id] = set(tset)
        else:
            self.scan(st.test, stmt=st)
            attrs.update(_while_bound(st, self.res))
            if self.taint_of(st.test):
                self.control_sink(st.test, st)
            if self._waits_for_human(st.body):
                attrs["human_turn"] = True  # a REPL: every iteration blocks on a person, not on the model
        self.out.nodes[lid] = Node(lid, NodeKind.LOOP, f"loop:{self.ctx.component}", self.loc(st), attrs)
        self.loops.append(lid)
        self.walk(st.body)
        self.loops.pop()
        self.walk(st.orelse)
        # agentic loop: a loop that re-calls the model and exits on its output
        node = self.out.nodes[lid]
        inner = [s for s in self.out.steps.values() if lid in s.attrs.get("_loops", [])]
        if inner and isinstance(st, ast.While):
            node.attrs["agentic"] = any(s.tool_names or s.attrs.get("tools_count") for s in inner) or bool(self.history_vars)

    HUMAN_INPUT = {"input", "raw_input", "getpass", "chat_input", "readline", "receive_json", "receive_text", "receive_bytes"}

    def _waits_for_human(self, body: list[ast.stmt]) -> bool:
        """input()/getpass()/sys.stdin.readline()/Prompt.ask()/st.chat_input()/websocket.receive_json() in the loop body
        or in a helper it calls."""
        def direct(nodes: list[ast.stmt]) -> bool:
            for n in (x for st in nodes for x in ast.walk(st)):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if name in self.HUMAN_INPUT and (name != "readline" or "stdin" in attr_chain(f)) or \
                        name == "ask" and "Prompt" in attr_chain(f) or name == "prompt" and attr_chain(f)[:1] in (["click"], ["typer"]):
                    return True
            return False
        if direct(body):
            return True
        for n in (x for st in body for x in ast.walk(st)):
            if isinstance(n, ast.Call):
                hit = self.res._project_function(n)
                if hit is not None and direct(hit[1].body):
                    return True
        return False

    BATCH_SOURCE = re.compile(r"(?i)(\bcsv\.|\breader\b|DictReader|iterrows|itertuples|read_csv|read_json|read_parquet|\.jsonl\b|readlines|"
                              r"load_dataset|\bdataset\b|fetchall|fetchmany|\.query\(|\.scan\(|glob\(|listdir|iterdir|os\.walk)")

    def _const_false(self, test: ast.expr) -> bool:
        """`if FLAG:` where FLAG is a module constant bound to False and never reassigned in the module."""
        if not isinstance(test, ast.Name):
            return False
        mv = self.res.module_value(test.id)
        if not mv or not isinstance(mv[1], ast.Constant) or mv[1].value is not False:
            return False
        tree = mv[0].tree
        assigned = sum(1 for n in ast.walk(tree) for t in getattr(n, "targets", []) if isinstance(t, ast.Name) and t.id == test.id)
        globals_ = any(isinstance(n, ast.Global) and test.id in n.names for n in ast.walk(tree))
        return assigned == 1 and not globals_

    def _is_batch_iter(self, it: ast.expr) -> bool:
        """Loop over an external dataset (file, table, directory), not over a small in-memory collection."""
        if self.BATCH_SOURCE.search(src(self.mod, it)):
            return True
        for n in ast.walk(it):
            if isinstance(n, ast.Name):
                v = self.res.local_value(n.id)
                if v is not None and (self.BATCH_SOURCE.search(src(self.mod, v)) or re.search(r"(?i)\bopen\(|json\.load\(|\.read_text\(|\.read_bytes\(|yaml\.(safe_)?load\(|tomllib\.load\(|pickle\.load\(", src(self.mod, v))):
                    return True
        return False

    def _retry_loop(self, st: ast.For | ast.AsyncFor | ast.While) -> tuple[str, dict] | None:
        tries = [n for n in st.body if isinstance(n, ast.Try)]
        if not tries:
            return None
        t = tries[0]
        # the model call may sit inside the try or just before it (call, then try: parse)
        has_llm = any(isinstance(n, ast.Call) and self._is_llm_like(n) for b in st.body for n in ast.walk(b))
        exits = any(isinstance(n, (ast.Return, ast.Break)) for b in t.body + t.orelse for n in ast.walk(b))
        if not (has_llm and exits):
            return None
        excs: set[str] = set()
        for h in t.handlers:
            excs |= exc_names(h)
        max_attempts: int | None = None
        unbounded = False
        if isinstance(st, (ast.For, ast.AsyncFor)):
            if isinstance(st.iter, ast.Call) and getattr(st.iter.func, "id", "") == "range" and st.iter.args:
                v = self.res.const(st.iter.args[-1] if len(st.iter.args) == 1 else st.iter.args[1])
                max_attempts = v if isinstance(v, int) else None
        else:
            b = _while_bound(st, self.res)
            unbounded = b["bounded"] is False or (b["bounded"] is None and is_true_const(st.test))
            max_attempts = b.get("max")
        rid = stable_id("retry", self.mod.rel, st.lineno, st.col_offset)
        return rid, {"mechanism": "loop", "max_attempts": max_attempts, "unbounded": unbounded,
                     "exceptions": sorted(excs), "trigger": _trigger(excs)}

    def _is_llm_like(self, call: ast.Call) -> bool:
        if match_direct(call, self.res, self.ex) is not None:
            return True
        hit = self.res._project_function(call)
        if hit is not None:
            return bool(self.ex.summaries.get(self.ex.qualname_of(*hit), Summary()).reach)
        return False

    # -- expressions ---------------------------------------------------------------------------
    def scan(self, expr: ast.expr, assign_to: str | None = None, stmt: ast.stmt | None = None) -> None:
        """Visit calls inside an expression (innermost first) and record LLM steps and sinks."""
        calls = [n for n in ast.walk(expr) if isinstance(n, ast.Call)]
        gather = any(_is_parallel_call(c) for c in calls)
        if gather:
            self.gather_depth += 1
        for call in reversed(calls):  # inner calls first (evaluation order approximation)
            self.visit_call(call, assign_to if call is expr else None, stmt)
        if gather:
            self.gather_depth -= 1
        # dict dispatch: HANDLERS[label](...) / ROUTES.get(label)
        for n in ast.walk(expr):
            if isinstance(n, ast.Subscript) and self.taint_of(n.slice):
                keys = self.res.const(n.value)
                labels = [k for k in keys if isinstance(k, str)] if isinstance(keys, dict) else []
                self.control_sink(n.slice, n, extra_labels=labels, kind="dispatch")

    def visit_call(self, call: ast.Call, assign_to: str | None, stmt: ast.stmt | None) -> None:
        m = match_direct(call, self.res, self.ex)
        if m is not None:
            kind, info = m
            if kind == "run":
                self.record_invocation(call, stmt)
                return
            if kind in ("sdk", "func", "lc") and self.is_wrapper_def:
                return  # materialized at each call site instead
            step = self.make_step(call, kind, info, assign_to)
            if step is not None:
                self.register_step(step, call, stmt)
            return
        self.sinks(call)
        hit = self.res._project_function(call)
        if hit is not None:
            callee = self.ex.qualname_of(*hit)
            summ = self.ex.summaries.get(callee, Summary())
            params = [a.arg for a in hit[1].args.posonlyargs + hit[1].args.args]
            if params and params[0] in ("self", "cls") and isinstance(call.func, ast.Attribute):
                params = params[1:]
            bound: list[tuple[str, ast.expr]] = list(zip(params, call.args))
            bound += [(k.arg, k.value) for k in call.keywords if k.arg]
            for p, a in bound:
                for s in summ.param_flows.get(p, ()):
                    for t in self.taint_of(a):
                        self.out.edges.append((t, s, EdgeKind.DATA_FLOW, {"via": f"{callee}({p})"}))
                    for n in ast.walk(a):
                        if isinstance(n, ast.Name) and n.id in self.res.params:
                            self.out.param_flows.setdefault(n.id, set()).add(s)
            self.out.calls.append({"callee": callee, "loops": list(self.loops), "retries": list(self.retries),
                                   "line": call.lineno, "entry": self.entry})
            if summ.reach and stmt is not None and id(stmt) in self.top_level_ids and not self.loops:
                deps = set()
                for a in call.args + [k.value for k in call.keywords]:
                    deps |= self.taint_of(a)
                self.out.sequence.append({"steps": sorted(summ.reach), "deps": sorted(deps), "line": call.lineno,
                                          "parallel": self.gather_depth > 0, "via": callee})

    # -- step construction ------------------------------------------------------------------------
    def make_step(self, call: ast.Call, kind: str, info: Any, assign_to: str | None) -> LLMStep | None:
        res = self.res
        target_call = call
        framework = provider = None
        sig: R.CallSig | None = None
        if kind == "wrapper":
            wmod, wfn = self.ex.wrappers[info]
            inner_call = next((n for n in ast.walk(wfn) if isinstance(n, ast.Call)
                               and (mm := match_direct(n, Resolver(self.ex.index, wmod, wfn, collect_assigns(wfn)), self.ex))
                               and mm[0] in ("sdk", "func", "lc")), None)
            if inner_call is None:
                return None
            params = [a.arg for a in wfn.args.posonlyargs + wfn.args.args]
            bindings = {p: (self.res, a) for p, a in zip(params, call.args)}
            bindings.update({k.arg: (self.res, k.value) for k in call.keywords if k.arg})
            res = Resolver(self.ex.index, wmod, wfn, collect_assigns(wfn), self._classify, bindings)
            kind, info = match_direct(inner_call, res, self.ex) or ("sdk", None)
            target_call = inner_call
        if kind == "sdk":
            sig = info
            framework, provider = sig.framework, sig.provider
        elif kind == "func":
            framework, provider = info, None
        elif kind == "lc":
            framework, provider = "langchain", info or None

        sid = stable_id("step", self.mod.rel, call.lineno, call.col_offset)
        if kind == "agent":
            return self.make_agent(call, info, assign_to, sid)
        step = LLMStep(id=sid, kind=NodeKind.LLM_STEP, name=self.ctx.component, location=self.loc(call),
                       step_kind=StepKind.CALL, framework=framework)
        prov: dict[str, str] = {}
        step.attrs["qualname"] = self.ctx.qualname
        if target_call is not call:
            step.attrs["wrapper"] = self.ex.qualname_of(*self.ex.wrappers[self._wrapper_qn(call)]) if self._wrapper_qn(call) else None
            step.attrs["wrapper_location"] = str(SourceLocation(res.mod.rel, target_call.lineno))
        if kind == "lc":
            self._fill_langchain(step, target_call, res, prov)
        else:
            self._fill_sdk(step, target_call, res, sig, prov)
        if provider and not step.model.provider:
            step.model.provider = provider
        step.attrs["provenance"] = prov
        return step

    def _wrapper_qn(self, call: ast.Call) -> str | None:
        hit = self.res._project_function(call)
        return self.ex.qualname_of(*hit) if hit else None

    def _model(self, step: LLMStep, expr: ast.expr | None, res: Resolver, prov: dict[str, str]) -> None:
        if expr is None:
            prov["model"] = "absent"
            return
        v = res.const(expr)
        if isinstance(v, str):
            step.model.raw = v
            prov["model"] = "config" if res.is_config_value(expr) else "literal"
            step.model.dynamic = prov["model"] == "config"
        else:
            step.model.raw = None
            step.model.dynamic = True
            step.attrs["model_expr"] = src(res.mod, expr)[:120]
            prov["model"] = "unresolved"
        if step.model.raw and ":" in step.model.raw:  # pydantic-ai "openai:gpt-4o"
            p, _, m = step.model.raw.partition(":")
            step.model.provider, step.model.raw = p, m
        elif step.model.raw and "/" in step.model.raw:  # litellm "anthropic/claude-..."
            p, _, m = step.model.raw.partition("/")
            step.model.provider, step.model.raw = p, m

    def _num(self, step: LLMStep, field_: str, expr: ast.expr | None, res: Resolver, prov: dict[str, str]) -> Any:
        if expr is None:
            prov[field_] = "absent"
            return None
        v = res.const(expr)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            prov[field_] = "literal"
            return v
        prov[field_] = "unresolved"
        return None

    def _fill_sdk(self, step: LLMStep, call: ast.Call, res: Resolver, sig: R.CallSig | None, prov: dict[str, str]) -> None:
        fw = step.framework
        self._model(step, kw(call, "model"), res, prov)
        step.temperature = self._num(step, "temperature", kw(call, "temperature"), res, prov)
        max_tok = self._num(step, "max_tokens", kw(call, "max_tokens", "max_completion_tokens", "max_output_tokens"), res, prov)
        cache = kw(call, "cache_control") is not None
        parts: list[PromptPart] = []
        config = kw(call, "config", "generation_config")
        cfg_kw: dict[str, ast.expr] = {}
        if isinstance(config, ast.Call):
            cfg_kw = {k.arg: k.value for k in config.keywords if k.arg}
        elif isinstance(config, ast.Dict):
            cfg_kw = {k.value: v for k, v in zip(config.keys, config.values) if isinstance(k, ast.Constant)}
        if cfg_kw:
            step.temperature = step.temperature if step.temperature is not None else self._num(step, "temperature", cfg_kw.get("temperature"), res, prov)
            max_tok = max_tok or self._num(step, "max_tokens", cfg_kw.get("max_output_tokens"), res, prov)
        system = kw(call, "system", "instructions") or cfg_kw.get("system_instruction")
        if system is not None:
            t, c = self.template_or_blocks(system, res)
            cache = cache or c
            parts.append(PromptPart("system", t.text, t.variables, self.loc(system)))
            self._taint_edges(step, t)
        msgs = kw(call, "messages", "input", "contents")
        if msgs is None and call.args and fw in ("litellm", "google", "ollama"):
            msgs = call.args[0] if fw != "google" else (call.args[1] if len(call.args) > 1 else None)
        if msgs is not None:
            mparts, c = self.messages(msgs, res, step)
            cache = cache or c
            parts += mparts
        step.prompt = parts
        step.cache_control = cache
        tools = kw(call, "tools") or cfg_kw.get("tools")
        if tools is not None:
            self._tools(step, tools, res)
        tc = kw(call, "tool_choice")
        if tc is not None:
            step.tool_choice = _tool_choice(res.const(tc))
        thinking = kw(call, "thinking", "reasoning", "reasoning_effort") or cfg_kw.get("thinking_config")
        if thinking is not None:
            v = res.const(thinking)
            step.thinking = v if isinstance(v, dict) else {"value": v if v is not MISSING else src(res.mod, thinking)}
            if isinstance(step.thinking, dict) and step.thinking.get("type") == "disabled":
                step.thinking = None
        step.output = self._output_sdk(call, res, sig, cfg_kw, max_tok)
        if step.tool_choice and step.tool_choice not in ("auto", "none", "any", "required") and step.output.kind == OutputKind.UNKNOWN:
            step.output = OutputSpec(OutputKind.TOOL_CALL, Enforcement.CONSTRAINED, max_tokens=max_tok)
        mr = kw(call, "max_retries")
        if mr is not None:  # instructor-style validation re-ask
            v = res.const(mr)
            rid = stable_id("retry", self.mod.rel, call.lineno, "kw")
            self.out.nodes[rid] = Node(rid, NodeKind.RETRY, f"retry-kw:{self.ctx.component}", self.loc(call), {
                "mechanism": "kwarg", "max_attempts": (v + 1) if isinstance(v, int) else None, "unbounded": False,
                "exceptions": ["ValidationError"], "trigger": "format"})
            self.out.edges.append((rid, step.id, EdgeKind.RETRIES, {}))

    def _output_sdk(self, call: ast.Call, res: Resolver, sig: R.CallSig | None, cfg_kw: dict, max_tok: Any) -> OutputSpec:
        out = OutputSpec(max_tokens=max_tok)
        cand = None
        for name in (sig.structured_args if sig else ("response_format",)):
            v = kw(call, name)
            if v is not None:
                cand = (name, v)
                break
        if cand is None and cfg_kw.get("response_schema") is not None:
            cand = ("response_schema", cfg_kw["response_schema"])
        if cand is None and cfg_kw.get("response_mime_type") is not None:
            if res.const(cfg_kw["response_mime_type"]) == "application/json":
                return OutputSpec(OutputKind.JSON, Enforcement.CONSTRAINED, max_tokens=max_tok)
        if cand is None:
            if sig and sig.structured_by_default:
                out.kind, out.enforcement = OutputKind.SCHEMA, Enforcement.CONSTRAINED
            return out
        name, expr = cand
        value = res.const(expr)
        schema_cls = None
        if isinstance(expr, ast.Name) and value is MISSING:
            schema_cls = expr.id
        elif isinstance(value, dict):
            typ = value.get("type")
            fmt = value.get("format") if isinstance(value.get("format"), dict) else None
            if fmt:
                typ = fmt.get("type")
            if typ == "json_object":
                return OutputSpec(OutputKind.JSON, Enforcement.CONSTRAINED, max_tokens=max_tok)
            if typ in ("json_schema", "json"):
                out.kind, out.enforcement = OutputKind.SCHEMA, Enforcement.CONSTRAINED
                return out
        else:
            # dict literal with non-constant parts (e.g. {"format": {"type": "json_schema", "schema": Model.model_json_schema()}})
            text = src(res.mod, expr)
            if "json_schema" in text or "model_json_schema" in text:
                out.kind, out.enforcement = OutputKind.SCHEMA, Enforcement.CONSTRAINED
                return out
            if "json_object" in text:
                return OutputSpec(OutputKind.JSON, Enforcement.CONSTRAINED, max_tokens=max_tok)
        out.kind, out.enforcement = OutputKind.SCHEMA, Enforcement.CONSTRAINED
        if schema_cls:
            self._apply_schema_class(out, schema_cls, res)
        return out

    def _apply_schema_class(self, out: OutputSpec, name: str, res: Resolver) -> None:
        mc = res.index.model_class(res.mod, name)
        out.schema_name = name
        if mc:
            out.schema_fields = mc.fields
            if mc.labels:
                out.labels = mc.labels
                if len(mc.fields) <= 1 or mc.is_enum:
                    out.kind = OutputKind.ENUM

    def _fill_langchain(self, step: LLMStep, call: ast.Call, res: Resolver, prov: dict[str, str]) -> None:
        f = call.func
        assert isinstance(f, ast.Attribute)
        # find constructor and chain pieces
        ctor_call: ast.Call | None = None
        prompt_tmpl: ast.Call | None = None
        structured: ast.expr | None = None
        stack = [f.value]
        seen = 0
        while stack and seen < 20:
            seen += 1
            e = stack.pop()
            if isinstance(e, ast.Name):
                v = res.local_value(e.id) or (res.module_value(e.id) or (None, None))[1]
                if v is not None:
                    stack.append(v)
            elif isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
                stack += [e.left, e.right]
            elif isinstance(e, ast.Call):
                fn = e.func
                if isinstance(fn, ast.Attribute) and fn.attr == "with_structured_output":
                    structured = e.args[0] if e.args else None
                    stack.append(fn.value)
                elif isinstance(fn, ast.Attribute) and fn.attr in ("from_messages", "from_template"):
                    prompt_tmpl = e
                elif fq_name(fn, res) in R.CHAT_MODEL_CTORS:
                    ctor_call = e
                elif isinstance(fn, ast.Attribute):
                    stack.append(fn.value)
        if ctor_call is not None:
            self._model(step, kw(ctor_call, "model", "model_name") or (ctor_call.args[0] if ctor_call.args else None), res, prov)
            step.temperature = self._num(step, "temperature", kw(ctor_call, "temperature"), res, prov)
        parts: list[PromptPart] = []
        if prompt_tmpl is not None and prompt_tmpl.args:
            arg = prompt_tmpl.args[0]
            if isinstance(arg, (ast.List, ast.Tuple)):
                for el in arg.elts:
                    if isinstance(el, ast.Tuple) and len(el.elts) == 2:
                        role = res.const(el.elts[0])
                        t = res.text(el.elts[1])
                        parts.append(PromptPart({"human": "user", "ai": "assistant"}.get(str(role), str(role)), t.text,
                                                [*t.variables, *_braces(t.text)], self.loc(el)))
            else:
                t = res.text(arg)
                parts.append(PromptPart("user", t.text, [*t.variables, *_braces(t.text)], self.loc(arg)))
        if call.args:
            a = call.args[0]
            if isinstance(a, ast.Dict):
                for k, v in zip(a.keys, a.values):
                    if isinstance(k, ast.Constant):
                        var = self._classify(v, res)
                        var.name = str(k.value)
                        for p in parts:
                            for pv in p.variables:
                                if pv.name == var.name and pv.source == VarSource.UNKNOWN:
                                    pv.source, pv.origin, pv.structured, pv.expression = var.source, var.origin, var.structured, var.expression
                        for t in self.taint_of(v):
                            self.out.edges.append((t, step.id, EdgeKind.DATA_FLOW, {}))
            elif not parts:
                mparts, cache = self.messages(a, res, step)
                parts = mparts
                step.cache_control = cache
        step.prompt = parts
        if structured is not None:
            step.output = OutputSpec(OutputKind.SCHEMA, Enforcement.CONSTRAINED)
            if isinstance(structured, ast.Name):
                self._apply_schema_class(step.output, structured.id, res)

    def make_agent(self, call: ast.Call, info: tuple[str, R.AgentSig], assign_to: str | None, sid: str) -> LLMStep:
        fq, sig = info
        res = self.res
        name = None
        for a in sig.name_args:
            v = res.const(kw(call, a))
            if isinstance(v, str):
                name = v
                break
        name = name or assign_to or self.ctx.component
        step = LLMStep(id=sid, kind=NodeKind.LLM_STEP, name=name, location=self.loc(call), step_kind=StepKind.AGENT,
                       framework=sig.framework)
        prov: dict[str, str] = {}
        model_expr = kw(call, *sig.model_args)
        if model_expr is None and sig.model_positional and call.args:
            model_expr = call.args[0]
        self._model(step, model_expr, res, prov)
        parts = []
        for a in sig.prompt_args:
            e = kw(call, a)
            if e is not None:
                t = res.text(e)
                parts.append(PromptPart("system", t.text, t.variables, self.loc(e)))
                self._taint_edges(step, t)
        step.prompt = parts
        tools = kw(call, *sig.tools_args)
        if tools is not None:
            self._tools(step, tools, res)
        for a in sig.output_args:
            e = kw(call, a)
            if e is not None:
                step.output = OutputSpec(OutputKind.SCHEMA, Enforcement.CONSTRAINED)
                lits = _literal_annotation(e)
                if lits:
                    step.output = OutputSpec(OutputKind.ENUM, Enforcement.CONSTRAINED, labels=lits)
                elif isinstance(e, ast.Name):
                    self._apply_schema_class(step.output, e.id, res)
                elif isinstance(e, ast.Name) and e.id in ("str",):
                    step.output = OutputSpec(OutputKind.FREE_TEXT, Enforcement.NONE)
        for a in sig.delegate_args:
            e = kw(call, a)
            if isinstance(e, (ast.List, ast.Tuple)):
                for el in e.elts:
                    target = el.args[0] if isinstance(el, ast.Call) and el.args else el
                    if isinstance(target, ast.Name):
                        self.out.pending_delegations.append((sid, target.id))
        if isinstance(tools, (ast.List, ast.Tuple)):  # agent.as_tool(...) -> delegation with return
            for el in tools.elts:
                if isinstance(el, ast.Call) and isinstance(el.func, ast.Attribute) and el.func.attr == "as_tool" \
                        and isinstance(el.func.value, ast.Name):
                    self.out.pending_delegations.append((sid, el.func.value.id))
        mi = kw(call, *sig.max_iter_args) if sig.max_iter_args else None
        if mi is not None:
            v = res.const(mi)
            step.max_iterations = v if isinstance(v, int) else None
            prov["max_iterations"] = "literal" if isinstance(v, int) else "unresolved"
        else:
            prov["max_iterations"] = "sdk_default" if sig.default_bounded else "absent"
        ms = kw(call, "model_settings")
        if isinstance(ms, ast.Call):
            step.temperature = self._num(step, "temperature", kw(ms, "temperature"), res, prov)
            tc = kw(ms, "tool_choice")
            if tc is not None:
                step.tool_choice = _tool_choice(res.const(tc))
        step.attrs.update(provenance=prov, qualname=self.ctx.qualname, sdk_default_bounded=sig.default_bounded)
        if assign_to:
            self.out.agent_vars[(self.mod.name, assign_to)] = sid  # type: ignore[index]
        return step

    def register_step(self, step: LLMStep, call: ast.Call, stmt: ast.stmt | None) -> None:
        step.attrs["_loops"] = list(self.loops)
        if self.entry:
            step.attrs.setdefault("entrypoints", []).append(self.entry)
        if non_production_path(self.mod.rel):
            step.attrs["non_production"] = True
        self.out.steps[step.id] = step
        self.call_step[id(call)] = step.id
        for lp in self.loops:
            self.out.edges.append((lp, step.id, EdgeKind.CONTAINS, {}))
        for rt in self.retries:
            self.out.edges.append((rt, step.id, EdgeKind.RETRIES, {}))
        # data-flow edges from prompt variables
        for p in step.prompt:
            for v in p.variables:
                self._var_edges(step, v)
        # agent constructors define an agent; only their invocations (record_invocation) execute it
        if stmt is not None and id(stmt) in self.top_level_ids and not self.loops and step.step_kind != StepKind.AGENT:
            deps = {e[0] for e in self.out.edges if e[1] == step.id and e[2] == EdgeKind.DATA_FLOW}
            self.out.sequence.append({"steps": [step.id], "deps": sorted(deps), "line": call.lineno,
                                      "parallel": self.gather_depth > 0})

    def _var_edges(self, step: LLMStep, v: PromptVariable) -> None:
        for t in v.__dict__.get("_taint", ()):
            if t != step.id:
                self.out.edges.append((t, step.id, EdgeKind.DATA_FLOW, {"var": v.name}))
        if v.source == VarSource.RETRIEVAL and v.origin:
            self.out.edges.append((v.origin, step.id, EdgeKind.RETRIEVES, {}))
        if v.source == VarSource.PARAMETER and self.ctx.fn is not None:
            self.out.param_flows.setdefault(v.name.split(".")[0].split("[")[0], set()).add(step.id)
            # template placeholders are renamed to their key ({"text": result["answer"]}): the parameter is the expression root
            root = re.match(r"[A-Za-z_]\w*", v.expression or "")
            if root and root.group(0) in self.res.params:
                self.out.param_flows.setdefault(root.group(0), set()).add(step.id)
        for pname in v.__dict__.get("_params", ()):
            self.out.param_flows.setdefault(pname, set()).add(step.id)

    def _taint_edges(self, step: LLMStep, t: Template) -> None:
        pass  # handled in register_step via variables

    # -- prompts --------------------------------------------------------------------------------
    def template_or_blocks(self, expr: ast.expr, res: Resolver) -> tuple[Template, bool]:
        """A string-ish expression or a list of content blocks [{"type": "text", "text": ..., "cache_control": ...}]."""
        node = expr
        if isinstance(node, ast.Name) and node.id not in res.params and node.id not in res.bindings:
            v = res.local_value(node.id) or (res.module_value(node.id) or (None, None))[1]
            if isinstance(v, ast.List):
                node = v
        if isinstance(node, ast.List):
            out = Template()
            cache = False
            for el in node.elts:
                if isinstance(el, ast.Dict):
                    d = {k.value: v for k, v in zip(el.keys, el.values) if isinstance(k, ast.Constant)}
                    cache = cache or "cache_control" in d
                    if "text" in d:
                        out = out + res.text(d["text"]) + Template("\n")
                    elif d.get("type") is not None:
                        out = out + Template(f"[{src(res.mod, d['type'])} block]")
                else:
                    out = out + res.text(el)
            return out, cache
        return res.text(expr), False

    def messages(self, expr: ast.expr, res: Resolver, step: LLMStep) -> tuple[list[PromptPart], bool]:
        node = expr
        appended: list[ast.expr] = []
        history = False
        if isinstance(node, ast.Name) and node.id not in res.params and node.id not in res.bindings:
            name = node.id
            v = res.local_value(name)
            if v is None:
                mv = res.module_value(name)
                v = mv[1] if mv else None
            body = res.fn if res.fn is not None else None
            if body is not None:
                for n in ast.walk(body):
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                            and n.func.value.id == name and n.func.attr in ("append", "extend") and n.args:
                        appended.append(n.args[0])
                        if self.loops or any(isinstance(p, (ast.While, ast.For)) for p in _ancestors(body, n)):
                            history = True
            if v is not None:
                node = v
            if history:
                self.history_vars.add(name)
                step.attrs["history_accumulates"] = True
                step.attrs["history_trimmed"] = _has_trim(body, name) if body else False
                caps = [self.out.nodes[lid].attrs.get("max") for lid in self.loops
                        if lid in self.out.nodes and self.out.nodes[lid].attrs.get("bounded") is True]
                caps = [c for c in caps if isinstance(c, int)]
                if caps:
                    step.attrs["history_bound"] = min(caps)  # the loop cap also caps how long the history grows
        if not isinstance(node, (ast.List, ast.Tuple)) and not appended:
            if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call, ast.Name, ast.Attribute, ast.Subscript)):
                t = res.text(node)
                return [PromptPart("user", t.text, t.variables, self.loc(expr))], False
            return [], False
        elements = list(node.elts) if isinstance(node, (ast.List, ast.Tuple)) else []
        elements += appended
        parts: list[PromptPart] = []
        cache = False
        for el in elements:
            role, content = None, None
            if isinstance(el, ast.Dict):
                d = {k.value: v for k, v in zip(el.keys, el.values) if isinstance(k, ast.Constant)}
                r = res.const(d.get("role")) if d.get("role") is not None else "user"
                role, content = (r if isinstance(r, str) else "user"), d.get("content") or d.get("parts")
            elif isinstance(el, ast.Call):
                cname = el.func.attr if isinstance(el.func, ast.Attribute) else getattr(el.func, "id", "")
                role = {"SystemMessage": "system", "HumanMessage": "user", "AIMessage": "assistant"}.get(cname)
                content = (el.args[0] if el.args else kw(el, "content")) if role else None
            elif isinstance(el, ast.Tuple) and len(el.elts) == 2:
                r = res.const(el.elts[0])
                role, content = (str(r) if r is not MISSING else "user"), el.elts[1]
            if content is None:
                if not isinstance(el, ast.Dict):
                    t = res.text(el)
                    parts.append(PromptPart("history" if history else "user", t.text, t.variables, self.loc(el)))
                continue
            t, c = self.template_or_blocks(content, res)
            cache = cache or c
            parts.append(PromptPart(role or "user", t.text, t.variables, self.loc(el)))
        return parts, cache

    def _tools(self, step: LLMStep, expr: ast.expr, res: Resolver) -> None:
        node = expr
        if isinstance(node, ast.Name):
            v = res.local_value(node.id) or (res.module_value(node.id) or (None, None))[1]
            if v is not None:
                node = v
        names: list[str] = []
        if isinstance(node, (ast.List, ast.Tuple)):
            for el in node.elts:
                val = res.const(el)
                if isinstance(val, dict):
                    fn = val.get("function") if isinstance(val.get("function"), dict) else val
                    nm = fn.get("name") if isinstance(fn, dict) else None
                    names.append(str(nm) if nm is not MISSING and nm else "?")
                elif isinstance(el, ast.Dict):
                    d = {k.value: v for k, v in zip(el.keys, el.values) if isinstance(k, ast.Constant)}
                    nm = res.const(d.get("name")) if d.get("name") is not None else MISSING
                    names.append(nm if isinstance(nm, str) else "?")
                elif isinstance(el, ast.Name):
                    names.append(el.id)
                elif isinstance(el, ast.Call) and isinstance(el.func, ast.Attribute) and el.func.attr == "as_tool":
                    names.append(src(res.mod, el.func.value))
                else:
                    names.append(src(res.mod, el)[:40])
            step.tool_names = names
            step.attrs["tools_count"] = len(names)
            step.attrs["tools_tokens"] = count_tokens(src(res.mod, node))
        else:
            step.attrs["tools_count"] = None
            step.attrs["tools_expr"] = src(res.mod, expr)[:80]

    # -- variables and taint -----------------------------------------------------------------------
    def _ctl(self) -> set[str]:
        return set().union(*self.ctl) if self.ctl else set()

    def taint_of(self, expr: ast.expr | None) -> set[str]:
        """Which LLM steps' outputs this value carries.

        A call to an LLM (or to a project function that runs LLM steps) yields *its*
        output, not its arguments'; deterministic calls (``x.strip()``, ``json.loads``,
        pure project helpers) pass their arguments' taint through.
        """
        if expr is None:
            return set()
        out: set[str] = set()
        stack: list[ast.AST] = [expr]
        while stack:
            n = stack.pop()
            if isinstance(n, ast.Name):
                out |= self.taint.get(n.id, set())
                continue
            if isinstance(n, ast.Call):
                sid = self.call_step.get(id(n))
                if sid:
                    out.add(sid)
                    continue
                if match_direct(n, self.res, self.ex) is not None:
                    continue
                hit = self.res._project_function(n)
                if hit:
                    summ = self.ex.summaries.get(self.ex.qualname_of(*hit), Summary())
                    if summ.reach:
                        out |= summ.returns
                        continue
            if isinstance(n, (ast.Lambda, ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)) and n is not expr:
                pass
            stack.extend(ast.iter_child_nodes(n))
        return out

    def _origin_of(self, value: ast.expr) -> tuple[VarSource, str | None] | None:
        for n in ast.walk(value):
            if isinstance(n, ast.Call):
                rid = self.call_step.get(("retr", id(n)))  # type: ignore[call-overload]
                if rid:
                    return VarSource.RETRIEVAL, rid
                name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if name in ("read", "read_text", "readlines", "load", "read_csv"):
                    return VarSource.FILE, None
                if name in ("input",) or "request" in src(self.mod, n.func):
                    return VarSource.USER_INPUT, None
            if isinstance(n, ast.Name) and n.id in self.origin:
                return self.origin[n.id]
        return None

    def _classify(self, node: ast.expr, res: Resolver) -> PromptVariable:
        text = src(res.mod, node)
        name = text[:80]
        var = PromptVariable(name=name, expression=text[:200])
        an = self if res is self.res else None
        taint = (an.taint_of(node) if an else set())
        root = node
        if isinstance(node, ast.Call) and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Name) \
                and node.args[0].id in res.params and res._project_function(node) is not None:
            dom = _param_domain(res, node.args[0].id)
            if dom:  # label_for(category): a project function of a finite-domain parameter has at most that many values
                var.source, var.domain = VarSource.PARAMETER, dom
                var.__dict__["_taint"], var.__dict__["_params"] = taint, {node.args[0].id}
                return var
        while isinstance(root, (ast.Attribute, ast.Subscript, ast.Call)):
            if isinstance(root, ast.Call):
                fname = root.func.attr if isinstance(root.func, ast.Attribute) else getattr(root.func, "id", "")
                if fname in ("dumps", "to_json", "model_dump_json", "json"):
                    var.structured = True
                if fname in ("str", "repr", "dumps", "to_json", "model_dump_json") and root.args:
                    root = root.args[0]
                    continue
                if isinstance(root.func, ast.Attribute):
                    root = root.func.value
                    continue
                break
            root = root.value
        params: set[str] = set()
        if isinstance(root, ast.Name):
            rid = root.id
            if rid in res.bindings:
                caller, expr = res.bindings[rid]
                inner = caller.classify_hook(expr, caller) if caller.classify_hook else PromptVariable(rid)
                inner.name = name if inner.name == rid else inner.name
                if var.structured is not None:
                    inner.structured = var.structured
                return inner
            if taint:
                var.source, var.origin = VarSource.LLM_OUTPUT, sorted(taint)[0]
            elif an and rid in an.origin:
                var.source, var.origin = an.origin[rid]
            elif rid in res.params:
                var.source = VarSource.PARAMETER
                params.add(rid)
                if root is node or isinstance(node, ast.Attribute) and node.value is root:
                    var.domain = _param_domain(res, rid)
            elif an and rid in an.history_vars:
                var.source = VarSource.HISTORY
            else:
                lv = res.local_value(rid)
                if lv is not None and an:
                    org = an._origin_of(lv)
                    if org:
                        var.source, var.origin = org
                    for n in ast.walk(lv):
                        if isinstance(n, ast.Name) and n.id in res.params:
                            params.add(n.id)
                            if var.source == VarSource.UNKNOWN:
                                var.source = VarSource.PARAMETER
        rebound = isinstance(root, ast.Name) and (root.id in res.bindings or len(res.assigns.get(root.id, ())) > 1)
        if var.source == VarSource.UNKNOWN and not params and not taint and not rebound and res.const(node) is not MISSING:
            var.source = VarSource.CONSTANT  # module/local literal (list of tiers, dict of rates): same value on every call
        if var.structured is None:
            var.structured = name_hint(text)
        if isinstance(node, (ast.Dict, ast.List)) and var.structured is None:
            var.structured = True
        var.__dict__["_taint"] = taint
        var.__dict__["_params"] = params
        return var

    # -- sinks ------------------------------------------------------------------------------------------
    def sinks(self, call: ast.Call) -> None:
        f = call.func
        fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        fq = fq_name(f, self.res) or ""
        args = list(call.args) + [k.value for k in call.keywords]
        tainted = set().union(*(self.taint_of(a) for a in args)) if args else set()
        # retrieval
        if fname in R.RETRIEVAL_METHODS and self._looks_like_retrieval(call, fname) or \
                fname in ("invoke", "ainvoke") and self._retriever_ctor(call) is not None:
            self.add_retrieval(call, fname)
            return
        if fname in ("create", "embed_query", "embed_documents", "embed_content") and \
                ("embeddings" in attr_chain(f) or fname.startswith("embed")):
            self.out.nodes.setdefault(stable_id("emb", self.mod.rel, call.lineno), Node(
                stable_id("emb", self.mod.rel, call.lineno), NodeKind.CODE_STEP, f"embedding:{self.ctx.component}",
                self.loc(call), {"embedding_call": True, "loops": list(self.loops)}))
            return
        if not tainted:
            return
        if fq == "json.loads" or fname == "loads":
            for s in tainted:
                self._mark(s, "parsed_as_json", True)
                if self.trys and self.trys[-1] & {"JSONDecodeError", "ValueError", "*", "Exception"}:
                    self._mark(s, "json_parse_guarded", True)
            return
        # extracting with a regex (re.search/findall...) is parsing; re.sub/re.split only clean or reshape the text
        if fname in ("search", "match", "findall", "fullmatch", "finditer") and (fq.startswith("re.") or attr_chain(f)[:1] == ["re"]):
            for s in tainted:
                self._mark(s, "parsed_with_regex", True)
            return
        if fname in R.VALIDATION_CALLS or fq in ("jsonschema.validate",) or fname == "validate" and "jsonschema" in fq:
            self.add_validation(call, tainted, "schema", src(self.mod, f)[:60])
            return
        hit = self.res._project_function(call)
        cls_hit = self.res.index.model_class(self.mod, getattr(f, "id", "")) if isinstance(f, ast.Name) else None
        if cls_hit is not None and not cls_hit.is_enum:
            self.add_validation(call, tainted, "schema", cls_hit.name)
            return
        if hit is not None and not self.ex.summaries.get(self.ex.qualname_of(*hit), Summary()).reach:
            if any(fname.lower().startswith(p) for p in ("validate", "check", "verify", "ensure", "assert_", "is_valid")):
                self.add_validation(call, tainted, "custom_code", fname)

    def _looks_like_retrieval(self, call: ast.Call, fname: str) -> bool:
        if fname in ("similarity_search", "similarity_search_with_score", "similarity_search_with_relevance_scores",
                     "max_marginal_relevance_search", "get_relevant_documents"):
            return True
        kws = {k.arg for k in call.keywords}
        if kws & set(R.RETRIEVAL_METHODS[fname]):
            return True
        recv = src(self.mod, call.func.value).lower() if isinstance(call.func, ast.Attribute) else ""
        return any(h in recv for h in ("collection", "index", "store", "vector", "retriever", "qdrant", "pinecone",
                                        "chroma", "weaviate", "faiss", "kb", "knowledge"))

    def _retriever_ctor(self, call: ast.Call) -> ast.Call | None:
        """The `store.as_retriever(...)` call behind `retriever.invoke(q)` / `store.as_retriever(...).invoke(q)`."""
        if not isinstance(call.func, ast.Attribute):
            return None
        recv = call.func.value
        v: ast.expr | None = recv if isinstance(recv, ast.Call) else None
        if isinstance(recv, ast.Name):
            v = self.res.local_value(recv.id, getattr(call, "lineno", None))
            if v is None:
                mv = self.res.module_value(recv.id)
                v = mv[1] if mv else None
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr in R.RETRIEVER_CTOR_METHODS:
            return v
        return None

    def add_retrieval(self, call: ast.Call, fname: str) -> None:
        rid = stable_id("retr", self.mod.rel, call.lineno, call.col_offset)
        top_k = None
        for k in R.RETRIEVAL_METHODS.get(fname, ()):
            e = kw(call, k)
            if e is not None:
                v = self.res.const(e)
                top_k = v if isinstance(v, int) else None
        ctor = self._retriever_ctor(call) if top_k is None else None
        if ctor is not None:
            sk = self.res.const(kw(ctor, "search_kwargs"))
            if isinstance(sk, dict) and isinstance(sk.get("k"), int):
                top_k = sk["k"]
        query = call.args[0] if call.args else kw(call, "query", "query_texts", "input")
        fn_src = src(self.mod, self.ctx.fn).lower() if self.ctx.fn is not None else ""
        loop_targets = set()
        for lp in self.loops:
            node = self.out.nodes.get(lp)
            if node and node.attrs.get("target"):
                loop_targets.add(node.attrs["target"])
        q_src = src(self.mod, query) if query is not None else None
        # loop-invariant only if both the query and the store/retriever stay the same across iterations
        target_names = {n for t in loop_targets for n in re.findall(r"\w+", t)}
        recv = call.func.value if isinstance(call.func, ast.Attribute) else None
        recv_names: set[str] = set()
        if recv is not None:
            recv_names = {n.id for n in ast.walk(recv) if isinstance(n, ast.Name)}
            for name in list(recv_names):
                lv = self.res.local_value(name, call.lineno)
                if lv is not None:
                    recv_names |= {n.id for n in ast.walk(lv) if isinstance(n, ast.Name)}
        q_names = set(re.findall(r"\w+", q_src or ""))
        invariant = bool(self.loops) and q_src is not None and not (q_names & target_names) and not (recv_names & target_names)
        self.out.nodes[rid] = Node(rid, NodeKind.RETRIEVAL, f"retrieval:{self.ctx.component}", self.loc(call), {
            "method": fname, "top_k": top_k, "query": q_src[:120] if q_src else None,
            "rerank": any(h in fn_src for h in R.RERANK_HINTS), "loops": list(self.loops),
            "loop_invariant_query": invariant, "function": self.ctx.qualname,
            "receiver": src(self.mod, recv)[:120] if recv is not None else None, "branch": list(self.branch)})
        if non_production_path(self.mod.rel):
            self.out.nodes[rid].attrs["non_production"] = True
        self.call_step[("retr", id(call))] = rid  # type: ignore[index]
        for lp in self.loops:
            self.out.edges.append((lp, rid, EdgeKind.CONTAINS, {}))

    def add_validation(self, node: ast.AST, steps: set[str], kind: str, detail: str) -> None:
        vid = stable_id("val", self.mod.rel, getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
        self.out.nodes[vid] = Node(vid, NodeKind.VALIDATION, f"validation:{detail}", self.loc(node),
                                   {"kind": kind, "detail": detail})
        for s in steps:
            self.out.edges.append((vid, s, EdgeKind.VALIDATES, {"validation_kind": kind}))

    def control_sink(self, test: ast.expr, node: ast.AST, extra_labels: list[str] | None = None, kind: str = "branch") -> None:
        steps = self.taint_of(test)
        if not steps:
            return
        cid = stable_id("cond", self.mod.rel, getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
        labels = list(dict.fromkeys(labels_in(test) + (extra_labels or [])))
        self.out.nodes[cid] = Node(cid, NodeKind.CONDITIONAL, f"{kind}:{self.ctx.component}", self.loc(node),
                                   {"labels": labels, "test": src(self.mod, test)[:160], "kind": kind})
        # `a == "x" and b == "y"`: each label belongs to the step that taints its own comparison
        per_step: dict[str, list[str]] = {}
        operands = test.values if isinstance(test, ast.BoolOp) else [test]
        for op in operands:
            for s in self.taint_of(op):
                per_step.setdefault(s, []).extend(labels_in(op))
        for s in steps:
            own = list(dict.fromkeys(per_step.get(s, []) + (extra_labels or []))) if isinstance(test, ast.BoolOp) else labels
            self.out.edges.append((s, cid, EdgeKind.CONTROLS, {"labels": own}))

    def record_invocation(self, call: ast.Call, stmt: ast.stmt | None = None) -> None:
        f = call.func
        agent_expr = call.args[0] if call.args and isinstance(f, ast.Attribute) and fq_name(f, self.res, ) and \
            (fq_name(f, self.res) or "").startswith("agents.Runner") else (f.value if isinstance(f, ast.Attribute) else None)
        inp = None
        if isinstance(f, ast.Attribute) and (fq_name(f, self.res) or "").startswith("agents.Runner"):
            inp = call.args[1] if len(call.args) > 1 else kw(call, "input")
        else:
            inp = call.args[0] if call.args else kw(call, "user_prompt", "inputs")
        var = None
        if isinstance(agent_expr, ast.Name):
            var = agent_expr.id
        mt = kw(call, "max_turns")
        mtv = self.res.const(mt) if mt is not None else MISSING
        self.out.invocations.append({
            "var": var, "template": self.res.text(inp) if inp is not None else None, "location": self.loc(call),
            "taint": self.taint_of(inp) if inp is not None else set(), "loops": list(self.loops),
            "max_turns": mtv if isinstance(mtv, int) else None,
        })
        sid = None
        if var:  # agent vars from previous rounds (agents may be defined in another module)
            sid = self.out.agent_vars.get((self.mod.name, var)) or self.ex.agent_steps.get((self.mod.name, var)) or next(
                (v for (_, n), v in self.ex.agent_steps.items() if n == var), None)
        if sid:
            self.call_step[id(call)] = sid
            if stmt is not None and id(stmt) in self.top_level_ids and not self.loops:
                self.out.sequence.append({"steps": [sid], "deps": sorted(self.taint_of(inp) if inp is not None else set()),
                                          "line": call.lineno, "parallel": self.gather_depth > 0})

    def _mark(self, step_id: str, key: str, value: Any) -> None:
        s = self.out.steps.get(step_id)
        if s is not None:
            s.attrs[key] = value
        else:
            # step lives in another function: record as a deferred attribute edge
            self.out.nodes.setdefault(f"attr:{step_id}:{key}", Node(f"attr:{step_id}:{key}", NodeKind.CODE_STEP,
                                                                  "deferred-attr", None, {"target": step_id, "key": key,
                                                                                          "value": value}))


# ----------------------------------------------------------------------------- small utilities
# boilerplate that does not give a helper a task of its own
GENERIC_ASSISTANT = re.compile(r"(?i)\b(you are|eres)\s+(a|an|un|una)\s+(helpful|useful|friendly|smart|[uú]til|amable)?\s*(ai\s+)?(assistant|asistente)\.?")
LLM_CALL_HINT = re.compile(r"\b(create|completion|acompletion|generate_content|invoke|ainvoke|parse|stream|chat|generate)\s*\(")


def is_true_const(test: ast.expr) -> bool:
    return isinstance(test, ast.Constant) and bool(test.value)


def _static_prompt_text(e: ast.expr, res: Resolver, depth: int = 0) -> str:
    """Instruction text an expression contributes, looking inside message lists/dicts (``messages=[{"content": ...}]``)."""
    if depth > 4:
        return ""
    if isinstance(e, (ast.List, ast.Tuple)):
        return "".join(_static_prompt_text(x, res, depth + 1) for x in e.elts)
    if isinstance(e, ast.Dict):
        out = ""
        for k, v in zip(e.keys, e.values):
            if isinstance(k, ast.Constant) and k.value in ("content", "text", "system", "instructions", "prompt"):
                out += _static_prompt_text(v, res, depth + 1)
        return out
    if isinstance(e, ast.Name):
        v = res.local_value(e.id)
        if isinstance(v, (ast.List, ast.Tuple, ast.Dict)):
            return _static_prompt_text(v, res, depth + 1)
    t = res.text(e)
    return t.text if t is not MISSING else ""


_TEMPLATE_CTORS = {"from_messages", "from_template", "ChatPromptTemplate", "PromptTemplate"}
_ROLE_NAMES = {"system", "human", "user", "ai", "assistant", "placeholder", "developer"}


def _param_domain(res: Resolver, name: str) -> list[str] | None:
    """Values a parameter can take according to its annotation: Literal[...], bool, or a project Enum class."""
    if res.fn is None:
        return None
    arg = next((a for a in res.fn.args.posonlyargs + res.fn.args.args + res.fn.args.kwonlyargs if a.arg == name), None)
    ann = arg.annotation if arg is not None else None
    if ann is None:
        return None
    if isinstance(ann, ast.Name) and ann.id == "bool":
        return ["True", "False"]
    if isinstance(ann, ast.Subscript) and _dotted(ann.value) in ("Literal", "typing.Literal", "typing_extensions.Literal"):
        elts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
        vals = [e.value for e in elts if isinstance(e, ast.Constant)]
        return [str(v) for v in vals] if len(vals) == len(elts) else None
    cname = _dotted(ann)
    if not cname:
        return None
    cls = res.mod.classes.get(cname)
    if cls is None:
        head, _, rest = cname.partition(".")
        fq = res.mod.imports.get(head)
        hit = res.index.lookup(fq + ("." + rest if rest else "")) if fq else None
        if hit is None or hit[1] not in hit[0].classes:
            return None
        cls = hit[0].classes[hit[1]]
    if not any((_dotted(b) or "").split(".")[-1] in ("Enum", "StrEnum", "IntEnum", "Flag", "IntFlag") for b in cls.bases):
        return None
    members = [t.id for st in cls.body if isinstance(st, ast.Assign) for t in st.targets if isinstance(t, ast.Name)]
    return members or None


def _chain_template_text(call: ast.Call, res: Resolver) -> str:
    """Instructions held by a LangChain prompt template piped into the model: ``(TMPL | llm).invoke(...)``."""
    f = call.func
    if not isinstance(f, ast.Attribute):
        return ""
    base = f.value
    if isinstance(base, ast.Name):
        base = res.local_value(base.id) or base
    if not isinstance(base, ast.BinOp) or not isinstance(base.op, ast.BitOr):
        return ""
    out: list[str] = []
    for n in ast.walk(base):
        target: ast.expr | None = n if isinstance(n, ast.Call) else None
        if isinstance(n, ast.Name):
            mv = res.module_value(n.id)
            target = res.local_value(n.id) or (mv[1] if mv else None)
        if not isinstance(target, ast.Call):
            continue
        fname = target.func.attr if isinstance(target.func, ast.Attribute) else getattr(target.func, "id", "")
        if fname in _TEMPLATE_CTORS:
            out += [c.value for c in ast.walk(target)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.lower() not in _ROLE_NAMES]
            # instructions held in constants: ("system", prompts.SUMMARY) / ("system", SYSTEM_PROMPT)
            for c in ast.walk(target):
                if isinstance(c, (ast.Name, ast.Attribute)) and isinstance(getattr(c, "ctx", None), ast.Load) and c is not target.func:
                    v = res.const(c)
                    if isinstance(v, str):
                        out.append(v)
    return " ".join(out)


def _while_bound(st: ast.While, res: Resolver) -> dict[str, Any]:
    test = st.test
    if isinstance(test, ast.Compare) and any(isinstance(o, (ast.Lt, ast.LtE)) for o in test.ops):
        v = res.const(test.comparators[-1])
        return {"bounded": True, "max": v if isinstance(v, int) else None}
    if is_true_const(test):
        cap = _counter_cap(st, res)
        if cap is not None:
            return cap
        breaks = [n for n in ast.walk(st) if isinstance(n, ast.Break)]
        if not breaks:
            has_return = any(isinstance(n, ast.Return) for n in ast.walk(st))
            return {"bounded": None if has_return else False, "exit": "return" if has_return else "none"}
        for n in ast.walk(st):
            if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and any(
                    isinstance(o, (ast.Gt, ast.GtE)) for o in n.test.ops) and any(isinstance(b, ast.Break) for b in n.body):
                v = res.const(n.test.comparators[-1])
                return {"bounded": True, "max": v if isinstance(v, int) else None}
        return {"bounded": None, "exit": "model_dependent"}
    return {"bounded": None}


def _counter_cap(st: ast.While, res: Resolver) -> dict[str, Any] | None:
    """`while True:` with `n += 1` and `if n > MAX (or past a deadline): <break | return | raise | tools = []>`.

    Disarming the tools forces the model's final answer on the next call, so the loop is capped even without `break`.
    """
    counters = {n.target.id for n in ast.walk(st) if isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add)
                and isinstance(n.target, ast.Name)}
    for n in ast.walk(st):
        if not isinstance(n, ast.If):
            continue
        tests = n.test.values if isinstance(n.test, ast.BoolOp) and isinstance(n.test.op, ast.Or) else [n.test]
        caps = [c for c in tests if isinstance(c, ast.Compare) and any(isinstance(o, (ast.Gt, ast.GtE)) for o in c.ops)
                and isinstance(c.left, ast.Name) and c.left.id in counters]
        if not caps or not _ends_or_disarms(n.body):
            continue
        v = res.const(caps[0].comparators[-1])
        return {"bounded": True, "max": v if isinstance(v, int) else None, "cap": "counter"}
    return None


def _ends_or_disarms(body: list[ast.stmt]) -> bool:
    for n in (x for s in body for x in ast.walk(s)):
        if isinstance(n, (ast.Break, ast.Return, ast.Raise)):
            return True
        if isinstance(n, ast.Assign) and isinstance(n.value, (ast.List, ast.Tuple, ast.Constant)):
            empty = not getattr(n.value, "elts", None) and getattr(n.value, "value", None) in (None, "none", "")
            names = [getattr(tg, "id", getattr(tg, "attr", "")) for tg in n.targets]
            if empty and any("tool" in nm.lower() for nm in names):
                return True  # tools = [] / tool_choice = "none": the next call must answer
    return False


def _trigger(excs: set[str]) -> str:
    if not excs or "*" in excs or "Exception" in excs:
        return "any"
    if excs & R.FORMAT_EXCEPTIONS and not excs & R.NETWORK_EXCEPTIONS:
        return "format"
    if excs & R.NETWORK_EXCEPTIONS and not excs & R.FORMAT_EXCEPTIONS:
        return "network"
    return "mixed"


def _tool_choice(v: Any) -> str | None:
    if v is MISSING or v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        if v.get("type") == "tool" and isinstance(v.get("name"), str):
            return v["name"]
        fn = v.get("function")
        if isinstance(fn, dict) and isinstance(fn.get("name"), str):
            return fn["name"]
        if isinstance(v.get("type"), str):
            return v["type"]
    return None


def _literal_annotation(e: ast.expr) -> list[str] | None:
    from ai_auditor.parser.python.index import _literal_values

    return _literal_values(e)


def _braces(text: str) -> list[PromptVariable]:
    import re

    return [PromptVariable(name=m, source=VarSource.UNKNOWN, structured=name_hint(m))
            for m in dict.fromkeys(re.findall(r"(?<!\{)\{([A-Za-z_]\w*)\}(?!\})", text))]


def _is_parallel_call(call: ast.Call) -> bool:
    name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
    return name in ("gather", "as_completed", "map", "submit", "wait", "TaskGroup", "create_task")


def _ancestors(root: ast.AST, target: ast.AST) -> list[ast.AST]:
    path: list[ast.AST] = []

    def visit(node: ast.AST, stack: list[ast.AST]) -> bool:
        if node is target:
            path.extend(stack)
            return True
        return any(visit(c, stack + [node]) for c in ast.iter_child_nodes(node))

    visit(root, [])
    return path


def _has_trim(body: ast.AST, name: str) -> bool:
    text = ast.unparse(body)
    return any(p in text for p in (f"{name}[-", f"del {name}[", f"{name}.pop(", "trim_messages", "summarize_history",
                                    "compact"))
