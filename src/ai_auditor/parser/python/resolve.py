"""Static resolution of Python expressions: literal values and prompt templates.

Resolution is best-effort and *honest*: whatever cannot be resolved becomes a
named variable (``{expr}``) with a classified origin, never a guess.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ai_auditor.ir.model import PromptVariable, VarSource
from ai_auditor.parser.python.index import Module, ProjectIndex
from ai_auditor.parser.tokens import count_tokens

MISSING = object()

_FREE_TEXT_NAMES = re.compile(
    r"(message|text|body|content|review|comment|description|query|question|complaint|transcript|conversation|chat|"
    r"note|feedback|narrative|story|document|doc|article|essay|reply|prompt|request|email|letter|post|summary|"
    r"mensaje|texto|cuerpo|consulta|pregunta|reclamo|queja|comentario|descripcion|resena|nota|historia|documento)",
    re.I,
)
_STRUCTURED_NAMES = re.compile(
    r"(json|payload|record|row|dict|fields|headers|csv|xml|html|log_line|metadata|schema|config|amount|price|total|"
    r"date|timestamp|_id\b|^id$|count|score|status|code|qty|quantity|currency|country|sku|zip|phone|iban|"
    r"importe|monto|fecha|precio|cantidad|estado|codigo|registro|fila)",
    re.I,
)
_STRONG_STRUCTURED = {"date", "time", "timestamp", "amount", "price", "total", "qty", "quantity", "sku", "zip", "phone", "iban",
                      "currency", "country", "id", "code", "json", "csv", "xml", "yaml", "payload", "record", "row", "dict",
                      "fields", "headers", "iso", "fecha", "importe", "monto", "precio", "cantidad", "codigo", "url"}
_GENERIC_CONTAINERS = {"text", "str", "string", "raw", "value", "content", "data", "input", "texto", "valor"}
_FREE_WORDS = {"message", "body", "review", "comment", "description", "query", "question", "complaint", "transcript",
               "conversation", "chat", "note", "notes", "feedback", "narrative", "story", "document", "doc", "article",
               "essay", "reply", "prompt", "request", "email", "letter", "post", "summary", "mensaje", "cuerpo",
               "consulta", "pregunta", "reclamo", "queja", "comentario", "descripcion", "nota", "historia", "documento"}
_SERIALIZATIONS = {"json", "csv", "tsv", "xml", "yaml", "yml", "edi", "ndjson", "jsonl"}
_ENVELOPES = {"body", "document", "doc", "request", "post", "message", "email", "cuerpo", "documento", "mensaje"}
_USER_INPUT_CALLS = {"input", "get_json"}
_FILE_READ_ATTRS = {"read", "read_text", "readlines"}


@dataclass
class Template:
    text: str = ""
    variables: list[PromptVariable] = field(default_factory=list)
    cache_control: bool = False
    exprs: list[ast.expr] = field(default_factory=list)  # expressions behind each variable (for taint)

    def __add__(self, other: Template) -> Template:
        return Template(self.text + other.text, self.variables + other.variables,
                        self.cache_control or other.cache_control, self.exprs + other.exprs)


_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$")


def src(mod: Module, node: ast.AST) -> str:
    """Source text of a node. Same result as ast.get_source_segment, but line splitting is done once per module."""
    lines = mod.__dict__.get("_lines")
    if lines is None:
        lines = [ln.encode() for ln in _LINE.findall(mod.source)]
        mod.__dict__["_lines"] = lines
    try:
        l0, l1 = node.lineno - 1, node.end_lineno - 1  # type: ignore[attr-defined]
        c0, c1 = node.col_offset, node.end_col_offset  # type: ignore[attr-defined]
    except AttributeError:
        return ast.unparse(node).strip()
    if l1 is None or c1 is None or l1 >= len(lines):
        return ast.unparse(node).strip()
    if l0 == l1:
        seg = lines[l0][c0:c1]
    else:
        seg = lines[l0][c0:] + b"".join(lines[l0 + 1:l1]) + lines[l1][:c1]
    return (seg.decode("utf-8", errors="replace") or ast.unparse(node)).strip()


def name_hint(text: str) -> bool | None:
    """Structured (True) / free text (False) / unknown (None) from an identifier or expression."""
    tail = re.split(r"[.\[\]'\"()]+", text.strip())
    tail = [t for t in tail if t]
    key = tail[-1] if tail else text
    if _STRUCTURED_NAMES.search(key) and not _FREE_TEXT_NAMES.search(key):
        return True
    # compound names: a specific type token wins over a generic container word ("date_text", "json_str", "raw_csv")
    tokens = {t.lower() for t in re.findall(r"[A-Za-z][a-z]*|[A-Z]+(?![a-z])", key.replace("_", " "))}
    if tokens & _SERIALIZATIONS and not tokens & (_FREE_WORDS - _ENVELOPES):
        return True  # "xml_body", "json_request": the serialization names the content, the envelope word does not
    if tokens & _STRONG_STRUCTURED and not (tokens - _GENERIC_CONTAINERS - _STRONG_STRUCTURED) & _FREE_WORDS:
        return True
    if _FREE_TEXT_NAMES.search(key):
        return False
    return None


class Resolver:
    """Resolves expressions inside one function scope (or module scope when ``fn`` is None).

    ``bindings`` maps parameter names to (caller_resolver, caller_expr) when a wrapper
    function is materialized at a call site.
    """

    def __init__(
        self,
        index: ProjectIndex,
        mod: Module,
        fn: ast.FunctionDef | ast.AsyncFunctionDef | None,
        assigns: dict[str, list[tuple[int, ast.expr]]],
        classify: Callable[[ast.expr, Resolver], PromptVariable] | None = None,
        bindings: dict[str, tuple[Resolver, ast.expr]] | None = None,
        cls_name: str | None = None,
    ) -> None:
        self.index = index
        self.mod = mod
        self.fn = fn
        self.assigns = assigns
        self.classify_hook = classify
        self.bindings = bindings or {}
        self.cls_name = cls_name
        self.params: list[str] = []
        self.defaults: dict[str, ast.expr] = {}
        if fn is not None:
            args = fn.args
            positional = [a.arg for a in args.posonlyargs + args.args]
            self.params = positional + [a.arg for a in args.kwonlyargs]
            for a, d in zip(positional[len(positional) - len(args.defaults):], args.defaults):
                self.defaults[a] = d
            for a, d in zip(args.kwonlyargs, args.kw_defaults):
                if d is not None:
                    self.defaults[a.arg] = d

    # -- name lookup ------------------------------------------------------------
    def local_value(self, name: str, before_line: int | None = None) -> ast.expr | None:
        vals = self.assigns.get(name)
        if not vals:
            return None
        if before_line is not None:
            prior = [v for ln, v in vals if ln <= before_line]
            if prior:
                return prior[-1]
        return vals[-1][1]

    def module_value(self, name: str, mod: Module | None = None, depth: int = 0) -> tuple[Module, ast.expr] | None:
        mod = mod or self.mod
        if name in mod.constants:
            return mod, mod.constants[name]
        fq = mod.imports.get(name)
        if fq and depth < 4:
            hit = self.index.lookup(fq)
            if hit:
                other, sym = hit
                if "." not in sym:
                    return self.module_value(sym, other, depth + 1)
        return None

    def module_attr(self, node: ast.expr) -> tuple[Module, ast.expr] | None:
        """`prompts.RULES` / `pkg.prompts.RULES` where the base is an imported project module."""
        if not isinstance(node, ast.Attribute):
            return None
        base = _dotted(node.value)
        if base is None or base == "self":
            return None
        head, _, rest = base.partition(".")
        fq = self.mod.imports.get(head)
        if fq is None:
            return None
        other = self.index.modules.get(fq + ("." + rest if rest else ""))
        if other is None or other is self.mod or node.attr not in other.constants:
            return None
        return other, other.constants[node.attr]

    def attr_source(self, node: ast.Attribute) -> tuple[Module, ast.expr] | None:
        """Where a static attribute value is declared: `prompts.X` (module), `SETTINGS.x` (instance default) or
        `self.x` (class attribute / constant assigned in a method of the enclosing class)."""
        if isinstance(node.value, ast.Name) and node.value.id == "self" and self.cls_name:
            v = self.mod.instance_attrs.get(f"{self.cls_name}.{node.attr}")
            return (self.mod, v) if v is not None and self._literalish(v) else None
        return self.module_attr(node) or self.instance_default(node)

    @staticmethod
    def _literalish(v: ast.expr) -> bool:
        """A value that does not depend on constructor arguments (no names other than module-level ones)."""
        return isinstance(v, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call, ast.Attribute, ast.Name)) and not any(
            isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id[:1].islower() and n.id not in ("str", "textwrap", "dedent")
            for n in ast.walk(v))

    def instance_default(self, node: ast.Attribute) -> tuple[Module, ast.expr] | None:
        """`MODELS.big` where `MODELS = Models()` is a module-level instance of a project class and `big` keeps the
        default declared in the class (dataclass/pydantic field, class attribute or constant `self.big = ...`)."""
        if not isinstance(node.value, ast.Name) or node.value.id in self.params or node.value.id in self.bindings:
            return None
        hit = self.module_value(node.value.id)
        if hit is None or not isinstance(hit[1], ast.Call):
            return None
        owner, call = hit
        if call.args or any(k.arg in (node.attr, None) for k in call.keywords):
            return None  # positional or matching keyword arguments may override the default
        cname = _dotted(call.func)
        if not cname:
            return None
        cls_mod = owner if cname in owner.classes else None
        if cls_mod is None:
            head, _, rest = cname.partition(".")
            fq = owner.imports.get(head)
            found = self.index.lookup(fq + ("." + rest if rest else "")) if fq else None
            if found is None:
                return None
            cls_mod, cname = found
        v = cls_mod.instance_attrs.get(f"{cname}.{node.attr}")
        return (cls_mod, v) if v is not None else None

    def foreign(self, mod: Module) -> Resolver:
        return Resolver(self.index, mod, None, {}, self.classify_hook)

    # -- literal values -----------------------------------------------------------
    def const(self, node: ast.expr | None, depth: int = 0) -> Any:
        if node is None or depth > 8:
            return MISSING
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in self.bindings:
                caller, expr = self.bindings[node.id]
                return caller.const(expr, depth + 1)
            if node.id in self.params:
                d = self.defaults.get(node.id)
                return self.const(d, depth + 1) if d is not None and not self.bindings else MISSING
            lv = self.local_value(node.id, getattr(node, "lineno", None))
            if lv is not None:
                return self.const(lv, depth + 1)
            mv = self.module_value(node.id)
            if mv:
                return self.foreign(mv[0]).const(mv[1], depth + 1) if mv[0] is not self.mod else self.const(mv[1], depth + 1)
            return MISSING
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            vals = [self.const(e, depth + 1) for e in node.elts]
            return MISSING if any(v is MISSING for v in vals) else vals
        if isinstance(node, ast.Dict):
            out = {}
            for k, v in zip(node.keys, node.values):
                kv, vv = self.const(k, depth + 1) if k is not None else MISSING, self.const(v, depth + 1)
                if kv is MISSING:
                    return MISSING
                out[kv] = vv  # values may be MISSING; callers check
            return out
        if isinstance(node, ast.Subscript):
            base = self.const(node.value, depth + 1)
            key = self.const(node.slice, depth + 1)
            if isinstance(base, dict) and key is not MISSING:
                return base.get(key, MISSING)
            return MISSING
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self" and self.cls_name:
                v = self.mod.instance_attrs.get(f"{self.cls_name}.{node.attr}")
                return self.const(v, depth + 1) if v is not None else MISSING
            # settings.MODEL / config.MODEL where `settings` is a project class/module constant
            if isinstance(node.value, ast.Name):
                v = self.mod.instance_attrs.get(f"{node.value.id}.{node.attr}")
                if v is not None:
                    return self.const(v, depth + 1)
            ma = self.module_attr(node)
            if ma is not None:
                return self.foreign(ma[0]).const(ma[1], depth + 1)
            default = self.instance_default(node)
            if default is not None:
                return self.foreign(default[0]).const(default[1], depth + 1)
            return MISSING
        if isinstance(node, ast.Call):
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            # dataclasses.field(default="x") / pydantic Field("x") / Field(default="x")
            if fname in ("field", "Field"):
                kw = next((k.value for k in node.keywords if k.arg == "default"), None)
                if kw is None and fname == "Field" and node.args:
                    kw = node.args[0]
                return self.const(kw, depth + 1) if kw is not None else MISSING
            if fname == "join" and isinstance(node.func, ast.Attribute) and len(node.args) == 1:
                return self._const_join(node, depth)
            # os.getenv("X", "default") / os.environ.get("X", "default"): configured at runtime
            if fname in ("getenv", "get") and len(node.args) >= 2:
                if isinstance(node.func, ast.Attribute) and src(self.mod, node.func.value) in ("os", "os.environ", "environ"):
                    return self.const(node.args[1], depth + 1)
            if fname in ("getenv",) and len(node.args) == 1:
                return MISSING
        if isinstance(node, ast.JoinedStr):  # f"openai:{MODELS.big}" with constant parts only
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                elif isinstance(v, ast.FormattedValue) and v.format_spec is None and v.conversion == -1:
                    c = self.const(v.value, depth + 1)
                    if not isinstance(c, (str, int, float)) or isinstance(c, bool):
                        return MISSING
                    parts.append(str(c))
                else:
                    return MISSING
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self.const(node.left, depth + 1), self.const(node.right, depth + 1)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            v = self.const(node.operand, depth + 1)
            return -v if isinstance(v, (int, float)) else MISSING
        return MISSING

    def is_config_value(self, node: ast.expr) -> bool:
        """True when the value comes from environment/config rather than a literal."""
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                fname = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if fname in ("getenv", "get") and "environ" in src(self.mod, n.func) or fname == "getenv":
                    return True
        return False

    # -- prompt templates -------------------------------------------------------------
    def text(self, node: ast.expr | None, depth: int = 0) -> Template:
        if node is None:
            return Template()
        if depth > 10:
            return self._var(node)
        if isinstance(node, ast.Constant):
            return Template(node.value) if isinstance(node.value, str) else Template(str(node.value))
        if isinstance(node, ast.JoinedStr):
            out = Template()
            for v in node.values:
                if isinstance(v, ast.Constant):
                    out = out + Template(str(v.value))
                elif isinstance(v, ast.FormattedValue):
                    inner = self.text(v.value, depth + 1) if self._statically_textual(v.value) else self._var(v.value)
                    out = out + inner
            return out
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.text(node.left, depth + 1) + self.text(node.right, depth + 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            base = self.text(node.left, depth + 1)
            args = node.right.elts if isinstance(node.right, ast.Tuple) else [node.right]
            for a in args:
                base = base + self._var(a, render=False)
            return base
        if isinstance(node, ast.Name):
            if node.id in self.bindings:
                caller, expr = self.bindings[node.id]
                return caller.text(expr, depth + 1)
            if node.id not in self.params:
                lv = self.local_value(node.id, getattr(node, "lineno", None))
                if lv is not None and self._statically_textual(lv):
                    return self.text(lv, depth + 1)
                mv = self.module_value(node.id)
                if mv is not None:
                    r = self if mv[0] is self.mod else self.foreign(mv[0])
                    if r._statically_textual(mv[1]):
                        return r.text(mv[1], depth + 1)
            return self._var(node)
        if isinstance(node, ast.Attribute):
            ma = self.attr_source(node)
            if ma is not None:
                r = self.foreign(ma[0])
                if r._statically_textual(ma[1]):
                    return r.text(ma[1], depth + 1)
            return self._var(node)
        if isinstance(node, ast.Call):
            return self._text_call(node, depth)
        if isinstance(node, ast.IfExp):
            return self.text(node.body, depth + 1)
        return self._var(node)

    def _statically_textual(self, node: ast.expr, depth: int = 0) -> bool:
        """Whether resolving `node` yields mostly static text (vs. an opaque runtime value)."""
        if depth > 6:
            return False
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            return self._statically_textual(node.left, depth + 1) or self._statically_textual(node.right, depth + 1)
        if isinstance(node, ast.Name):
            if node.id in self.bindings:
                caller, expr = self.bindings[node.id]
                return caller._statically_textual(expr, depth + 1)
            if node.id in self.params:
                return False
            lv = self.local_value(node.id, getattr(node, "lineno", None))
            if lv is not None:
                return self._statically_textual(lv, depth + 1)
            mv = self.module_value(node.id)
            if mv is not None:
                r = self if mv[0] is self.mod else self.foreign(mv[0])
                return r._statically_textual(mv[1], depth + 1)
            return False
        if isinstance(node, ast.Attribute):
            ma = self.attr_source(node)
            return ma is not None and self.foreign(ma[0])._statically_textual(ma[1], depth + 1)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in ("format", "strip", "join", "dedent", "replace", "format_map"):
                return True
            if isinstance(f, ast.Attribute) and f.attr in _FILE_READ_ATTRS:
                return True
            fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if fname in ("dedent", "cleandoc"):
                return True
            hit = self._project_function(node, methods=True)
            if hit is None:
                return False
            ret = _single_return(hit[1])
            if ret is None:
                return False
            callee = Resolver(self.index, hit[0], hit[1], _collect_assigns(hit[1]), self.classify_hook)
            return isinstance(ret, (ast.JoinedStr, ast.Constant)) or callee._statically_textual(ret, depth + 1)
        return False

    def _text_call(self, node: ast.Call, depth: int) -> Template:
        f = node.func
        fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if isinstance(f, ast.Attribute) and fname in ("format", "format_map"):
            base = self.text(f.value, depth + 1)
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            out_text = base.text
            extra = Template(variables=list(base.variables), exprs=list(base.exprs), cache_control=base.cache_control)
            for key, expr in kw.items():
                sub = self.text(expr, depth + 1) if self._statically_textual(expr) else self._var(expr)
                if sub.variables or sub.exprs:
                    extra = extra + Template(variables=sub.variables, exprs=sub.exprs)
                    out_text = out_text.replace("{" + key + "}", "{" + (sub.variables[0].name if sub.variables else key) + "}")
                else:
                    out_text = out_text.replace("{" + key + "}", sub.text)
            for a in node.args:
                extra = extra + self._var(a, render=False)
            return Template(out_text, extra.variables, extra.cache_control, extra.exprs)
        if isinstance(f, ast.Attribute) and fname in ("strip", "lstrip", "rstrip", "replace"):
            return self.text(f.value, depth + 1)
        if fname in ("dedent", "cleandoc") and node.args:
            return self.text(node.args[0], depth + 1)
        if isinstance(f, ast.Attribute) and fname == "join" and node.args:
            sep = self.const(f.value)
            arg = node.args[0]
            if isinstance(arg, (ast.List, ast.Tuple)) and isinstance(sep, str):
                out = Template()
                for i, e in enumerate(arg.elts):
                    if i:
                        out = out + Template(sep)
                    out = out + self.text(e, depth + 1)
                return out
            folded = self._const_join(node, depth)
            if isinstance(folded, str):
                return Template(folded)
            return self._var(node)
        if isinstance(f, ast.Attribute) and fname in _FILE_READ_ATTRS:
            return self._file_read(node)
        proj = self._project_function(node, methods=True)
        if proj is not None:
            mod, fn = proj
            ret = _single_return(fn)
            if ret is not None:
                bindings = {}
                params = [a.arg for a in fn.args.posonlyargs + fn.args.args]
                is_method = isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls")
                if is_method:
                    params = params[1:]  # self.build_prompt(rows): `rows` binds the first parameter after self
                for p, a in zip(params, node.args):
                    bindings[p] = (self, a)
                for k in node.keywords:
                    if k.arg:
                        bindings[k.arg] = (self, k.value)
                callee = Resolver(self.index, mod, fn, _collect_assigns(fn), self.classify_hook, bindings,
                                  self.cls_name if is_method else None)
                return callee.text(ret, depth + 1)
        return self._var(node)

    def _const_join(self, node: ast.Call, depth: int) -> Any:
        """'sep'.join(<expr> for <target> in <constant container>) evaluated statically (bounded, side-effect free)."""
        sep = self.const(node.func.value, depth + 1)  # type: ignore[union-attr]
        arg = node.args[0]
        if not isinstance(sep, str):
            return MISSING
        if isinstance(arg, (ast.List, ast.Tuple)):
            vals = [self.const(e, depth + 1) for e in arg.elts]
            return sep.join(vals) if all(isinstance(v, str) for v in vals) else MISSING
        if not isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
            # ", ".join(CATEGORIES) with CATEGORIES a module-level constant; a local list may be filled later (append)
            local = isinstance(arg, ast.Name) and (arg.id in self.params or arg.id in self.bindings or self.local_value(arg.id) is not None)
            if local or not isinstance(arg, (ast.Name, ast.Attribute)):
                return MISSING
            vals = self.const(arg, depth + 1)
            if isinstance(vals, dict):
                vals = list(vals)
            ok = isinstance(vals, list) and len(vals) <= 500 and all(isinstance(v, str) for v in vals)
            return sep.join(vals) if ok else MISSING
        if len(arg.generators) != 1:
            return MISSING
        gen = arg.generators[0]
        if gen.ifs or gen.is_async:
            return MISSING
        it = gen.iter
        method = None
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("items", "keys", "values") and not it.args:
            method, it = it.func.attr, it.func.value
        items = self.const(it, depth + 1)
        if isinstance(items, dict):
            items = list(items.items()) if method == "items" else list(items.values()) if method == "values" else list(items)
        elif method is not None:
            return MISSING
        if not isinstance(items, list) or len(items) > 500:
            return MISSING
        out = []
        for item in items:
            env = _bind(gen.target, item)
            rendered = _render(arg.elt, env) if env is not None else MISSING
            if not isinstance(rendered, str):
                return MISSING
            out.append(rendered)
        return sep.join(out)

    def _file_read(self, node: ast.Call) -> Template:
        """open("x").read() / Path("x").read_text(): resolve the file to measure it when the path is literal."""
        path_val = MISSING
        target = node.func.value  # type: ignore[union-attr]
        if isinstance(target, ast.Call):
            inner = target.func
            iname = inner.attr if isinstance(inner, ast.Attribute) else getattr(inner, "id", "")
            if iname in ("open", "Path") and target.args:
                path_val = self.const(target.args[0])
        var = self._var(node)
        if isinstance(path_val, str):
            for base in (self.mod.path.parent, self.index.root):
                p = (base / path_val)
                if p.is_file():
                    try:
                        content = p.read_text(errors="replace")
                    except OSError:
                        break
                    v = var.variables[0]
                    v.source = VarSource.FILE
                    v.est_tokens = count_tokens(content)
                    v.structured = Path(path_val).suffix in (".json", ".csv", ".yaml", ".yml", ".xml")
                    break
        for v in var.variables:
            if v.source == VarSource.UNKNOWN:
                v.source = VarSource.FILE
        return var

    def _project_function(self, node: ast.Call, methods: bool = False) -> tuple[Module, ast.FunctionDef | ast.AsyncFunctionDef] | None:
        """The project function a call targets. `methods=True` also follows `self.method(...)` (used to read prompt
        text built by a method; the call graph keeps treating method calls as opaque)."""
        f = node.func
        if isinstance(f, ast.Name):
            if f.id in self.mod.functions:
                return self.mod, self.mod.functions[f.id]
            fq = self.mod.imports.get(f.id)
            if fq:
                hit = self.index.lookup(fq)
                if hit and hit[1] in hit[0].functions:
                    return hit[0], hit[0].functions[hit[1]]
        if methods and isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls") and self.cls_name:
            method = self.mod.functions.get(f"{self.cls_name}.{f.attr}")
            return (self.mod, method) if method is not None else None
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            fq = self.mod.imports.get(f.value.id)
            if fq:
                other = self.index.modules.get(fq)
                if other and f.attr in other.functions:
                    return other, other.functions[f.attr]
        return None

    def _var(self, node: ast.expr, render: bool = True) -> Template:
        if self.classify_hook is not None:
            v = self.classify_hook(node, self)
        else:
            v = PromptVariable(name=src(self.mod, node)[:80], expression=src(self.mod, node)[:200])
        return Template("{" + v.name + "}" if render else "", [v], False, [node])


def _dotted(node: ast.expr) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _bind(target: ast.expr, value: Any) -> dict[str, Any] | None:
    if isinstance(target, ast.Name):
        return {target.id: value}
    if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (list, tuple)) and len(value) == len(target.elts):
        env: dict[str, Any] = {}
        for t, v in zip(target.elts, value):
            sub = _bind(t, v)
            if sub is None:
                return None
            env.update(sub)
        return env
    return None


def _render(node: ast.expr, env: dict[str, Any]) -> Any:
    """str() of a tiny expression language: literals, loop names, f-strings, str(x), `+` on strings."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env.get(node.id, MISSING)
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            elif isinstance(v, ast.FormattedValue) and v.format_spec is None and v.conversion == -1:
                inner = _render(v.value, env)
                if inner is MISSING or isinstance(inner, (dict, list, tuple)):
                    return MISSING
                out.append(str(inner))
            else:
                return MISSING
        return "".join(out)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and len(node.args) == 1:
        inner = _render(node.args[0], env)
        return MISSING if inner is MISSING else str(inner)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _render(node.left, env), _render(node.right, env)
        return a + b if isinstance(a, str) and isinstance(b, str) else MISSING
    return MISSING


def _single_return(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    rets = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None]
    return rets[0].value if len(rets) == 1 else None


def _collect_assigns(fn: ast.AST) -> dict[str, list[tuple[int, ast.expr]]]:
    out: dict[str, list[tuple[int, ast.expr]]] = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, []).append((n.lineno, n.value))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value is not None:
            out.setdefault(n.target.id, []).append((n.lineno, n.value))
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            out.setdefault(n.target.id, []).append((n.lineno, n.value))
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if isinstance(item.optional_vars, ast.Name):
                    out.setdefault(item.optional_vars.id, []).append((n.lineno, item.context_expr))
    for v in out.values():
        v.sort(key=lambda x: x[0])
    return out


collect_assigns = _collect_assigns
