"""Project-wide symbol index for Python sources (imports, constants, functions, classes).

Built once per analysis so cross-module references (prompts defined in a
``prompts.py``, a generic ``ask()`` helper in ``llm.py``) resolve without
re-parsing files.
"""

from __future__ import annotations

import ast
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from ai_auditor.parser.python.notebook import notebook_source
from ai_auditor.parser.python.notebook import parse as parse_notebook


@dataclass
class ModelClass:
    name: str
    fields: list[str]
    labels: list[str] | None  # Literal / Enum values of a single categorical field, if any
    is_enum: bool = False


@dataclass
class Module:
    name: str  # dotted, relative to project root
    rel: str
    path: Path
    tree: ast.Module
    source: str
    imports: dict[str, str] = field(default_factory=dict)  # local alias -> fully qualified name
    constants: dict[str, ast.expr] = field(default_factory=dict)
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)  # "f" or "Class.m"
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    models: dict[str, ModelClass] = field(default_factory=dict)
    instance_attrs: dict[str, ast.expr] = field(default_factory=dict)  # "Class.attr" -> value assigned in methods


@dataclass
class ProjectIndex:
    root: Path
    modules: dict[str, Module] = field(default_factory=dict)  # dotted name -> module
    by_rel: dict[str, Module] = field(default_factory=dict)

    def lookup(self, fq: str) -> tuple[Module, str] | None:
        """Resolve 'pkg.mod.SYMBOL' to (module, 'SYMBOL') if the module is part of the project."""
        parts = fq.split(".")
        for i in range(len(parts) - 1, 0, -1):
            mod = self.modules.get(".".join(parts[:i]))
            if mod is not None:
                return mod, ".".join(parts[i:])
        return None

    def model_class(self, mod: Module, name: str) -> ModelClass | None:
        if name in mod.models:
            return mod.models[name]
        fq = mod.imports.get(name)
        if fq:
            hit = self.lookup(fq)
            if hit and hit[1] in hit[0].models:
                return hit[0].models[hit[1]]
        return None


def _module_name(rel: str) -> str:
    if rel.endswith(".ipynb"):  # not importable: a name no import statement can produce
        return rel[: -len(".ipynb")].replace("/", ".").replace("-", "_") + "__ipynb"
    p = rel[:-3] if rel.endswith(".py") else rel
    p = p[: -len("/__init__")] if p.endswith("/__init__") else p
    return p.replace("/", ".")


def _literal_values(node: ast.expr | None) -> list[str] | None:
    """Values of Literal["a", "b"] (also Optional[Literal[...]])."""
    if node is None:
        return None
    if isinstance(node, ast.Subscript):
        base = node.value
        base_name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        sl = node.slice
        if base_name == "Literal":
            elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
            vals = [e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, (str, int, bool))]
            return [str(v) for v in vals] or None
        if base_name in ("Optional", "Annotated"):
            inner = sl.elts[0] if isinstance(sl, ast.Tuple) else sl
            return _literal_values(inner)
    return None


def _collect_models(mod: Module) -> None:
    for cls in mod.classes.values():
        bases = {b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "") for b in cls.bases}
        if bases & {"Enum", "StrEnum", "IntEnum"}:
            vals = []
            for st in cls.body:
                if isinstance(st, ast.Assign) and isinstance(st.value, ast.Constant):
                    vals.append(str(st.value.value))
            mod.models[cls.name] = ModelClass(cls.name, [], vals or None, is_enum=True)
        elif bases & {"BaseModel", "TypedDict"} or any(
            isinstance(d, ast.Name) and d.id == "dataclass" for d in cls.decorator_list
        ):
            fields_: list[str] = []
            labels: list[str] | None = None
            n_cat = n_bool = 0
            for st in cls.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    fields_.append(st.target.id)
                    vals = _literal_values(st.annotation)
                    if vals:
                        n_cat += 1
                        labels = vals
                    elif isinstance(st.annotation, ast.Name) and st.annotation.id == "bool":
                        n_bool += 1
            if n_cat == 0 and n_bool == 1:
                labels, n_cat = ["true", "false"], 1  # a lone boolean verdict is a two-valued closed output
            mod.models[cls.name] = ModelClass(cls.name, fields_, labels if n_cat == 1 else None)
    # Enum-typed fields referencing enums defined in this module
    for mc in list(mod.models.values()):
        if mc.labels is None and not mc.is_enum:
            cls = mod.classes[mc.name]
            for st in cls.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.annotation, ast.Name):
                    ref = mod.models.get(st.annotation.id)
                    if ref and ref.is_enum and ref.labels and len(mc.fields) <= 3:
                        mc.labels = ref.labels


def build_index(root: Path, files: list[tuple[Path, str]]) -> tuple[ProjectIndex, list[tuple[str, str]]]:
    """Parse all Python files once. Returns the index and (rel, error) for files that failed to parse."""
    index = ProjectIndex(root=root)
    errors: list[tuple[str, str]] = []
    for path, rel in files:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)  # invalid escapes etc. in audited code are not our output
                if path.suffix == ".ipynb":
                    source, nb_warnings = notebook_source(path)
                    errors += [(rel, w) for w in nb_warnings]
                    tree = parse_notebook(source, rel)
                else:
                    source = path.read_text(errors="replace")
                    tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            errors.append((rel, f"SyntaxError: {exc.msg} (line {exc.lineno})"))
            continue
        except (ValueError, OSError) as exc:
            errors.append((rel, str(exc)))
            continue
        mod = Module(_module_name(rel), rel, path, tree, source)
        pkg = mod.name.rsplit(".", 1)[0] if "." in mod.name else ""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mod.imports[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parent = pkg.split(".") if pkg else []
                    parent = parent[: len(parent) - (node.level - 1)] if node.level > 1 else parent
                    base = ".".join([p for p in parent if p] + ([base] if base else []))
                for a in node.names:
                    mod.imports[a.asname or a.name] = f"{base}.{a.name}" if base else a.name
        for st in tree.body:
            if isinstance(st, ast.Assign):
                for t in st.targets:
                    if isinstance(t, ast.Name):
                        mod.constants[t.id] = st.value
            elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                mod.constants[st.target.id] = st.value
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mod.functions[st.name] = st
            elif isinstance(st, ast.ClassDef):
                mod.classes[st.name] = st
                for sub in st.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mod.functions[f"{st.name}.{sub.name}"] = sub
                        for n in ast.walk(sub):
                            if isinstance(n, ast.Assign):
                                for t in n.targets:
                                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                                        mod.instance_attrs[f"{st.name}.{t.attr}"] = n.value
                    elif isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            if isinstance(t, ast.Name):
                                mod.instance_attrs[f"{st.name}.{t.id}"] = sub.value
                    elif isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name) and sub.value is not None:
                        mod.instance_attrs.setdefault(f"{st.name}.{sub.target.id}", sub.value)  # dataclass/pydantic field default
        _collect_models(mod)
        index.modules[mod.name] = mod
        index.by_rel[rel] = mod
        # Also register the bare file stem so sibling imports ("from prompts import X") resolve
        stem = mod.name.rsplit(".", 1)[-1]
        if not rel.endswith(".ipynb"):
            index.modules.setdefault(stem, mod)
    return index, errors
