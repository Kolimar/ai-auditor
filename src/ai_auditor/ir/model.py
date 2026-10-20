"""AI Workflow Intermediate Representation (IR).

The IR is the single contract between extractors (``parser/``) and everything
downstream (graph, rules, cost, reporting). Extractors never talk to rules
directly, and rules never read source files: they only see the IR.

Design notes
------------
* The unit of analysis is the ``LLMStep``: one place in the system that triggers
  model inference. ``kind="call"`` is a single request (an SDK call site);
  ``kind="agent"`` is an iterative loop driven by a model (a Claude Code
  subagent, an ``Agent(...)`` from an agent SDK). Treating both uniformly lets
  rules ask "what does this step decide, with which model, on what input".
* Everything that is not known statically is represented explicitly as unknown
  (``None`` plus a diagnostic), never guessed. Downstream code must handle it.
* Every node carries a ``SourceLocation`` so each finding can point at evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import StrEnum
from typing import Any


IR_SCHEMA_VERSION = "1"


class NodeKind(StrEnum):
    WORKFLOW = "workflow"
    LLM_STEP = "llm_step"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    RETRY = "retry"
    VALIDATION = "validation"
    CONTEXT_SOURCE = "context_source"
    CODE_STEP = "code_step"
    SKILL = "skill"


class EdgeKind(StrEnum):
    CONTAINS = "contains"  # workflow/loop/agent -> child
    DELEGATES = "delegates"  # agent -> subagent / skill
    DATA_FLOW = "data_flow"  # producer output -> consumer input
    CONTROLS = "controls"  # step output -> conditional that branches on it
    USES_TOOL = "uses_tool"
    RETRIEVES = "retrieves"  # retrieval -> step that receives its results
    VALIDATES = "validates"  # validation -> step whose output it checks
    RETRIES = "retries"  # retry policy -> step it re-executes
    INJECTS_CONTEXT = "injects_context"  # context source -> step


class StepKind(StrEnum):
    CALL = "call"
    AGENT = "agent"


class OutputKind(StrEnum):
    FREE_TEXT = "free_text"
    JSON = "json"  # JSON requested, no schema enforced
    SCHEMA = "schema"  # schema / typed object enforced (structured outputs, output_type)
    ENUM = "enum"  # closed label set
    BOOLEAN = "boolean"
    NUMBER = "number"
    TOOL_CALL = "tool_call"
    UNKNOWN = "unknown"


class Enforcement(StrEnum):
    CONSTRAINED = "constrained_decoding"  # provider/library guarantees the shape
    POST_VALIDATION = "post_validation"  # parsed/validated after generation
    PROMPT_ONLY = "prompt_only"  # only asked for in the prompt
    NONE = "none"
    UNKNOWN = "unknown"


class VarSource(StrEnum):
    CONSTANT = "constant"
    USER_INPUT = "user_input"
    LLM_OUTPUT = "llm_output"
    FILE = "file"
    RETRIEVAL = "retrieval"
    TOOL_RESULT = "tool_result"
    HISTORY = "history"
    PARAMETER = "parameter"  # function parameter: origin unknown at this scope
    UNKNOWN = "unknown"


@dataclass
class SourceLocation:
    file: str
    line: int | None = None
    end_line: int | None = None

    def __str__(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file


@dataclass
class ModelRef:
    raw: str | None = None  # as written: "gpt-4o", "opus", "${MODEL}", None
    resolved: str | None = None  # canonical id if resolvable
    provider: str | None = None
    tier: str | None = None  # frontier | large | medium | small | unknown (from catalog)
    dynamic: bool = False  # comes from a variable/config we could not resolve
    inherited: bool = False  # e.g. Claude Code subagent with model omitted/"inherit"


@dataclass
class PromptVariable:
    name: str
    source: VarSource = VarSource.UNKNOWN
    origin: str | None = None  # node id that produces it (LLM step, retrieval, file context)
    structured: bool | None = None  # dict/json/number-like value, if known
    est_tokens: int | None = None  # only when the value is statically known (e.g. a file)
    expression: str | None = None  # source text of the interpolated expression
    domain: list[str] | None = None  # finite set of possible values, when the type says so (Enum, Literal, bool)


@dataclass
class PromptPart:
    role: str  # system | developer | user | assistant | instructions | description | tool_description
    text: str  # static text; dynamic insertions rendered as {name}
    variables: list[PromptVariable] = field(default_factory=list)
    location: SourceLocation | None = None
    always_loaded: bool = False  # injected into every session/request regardless of task (e.g. agent descriptions)


@dataclass
class OutputSpec:
    kind: OutputKind = OutputKind.UNKNOWN
    enforcement: Enforcement = Enforcement.UNKNOWN
    labels: list[str] | None = None  # closed label set, if detectable
    schema_name: str | None = None
    schema_fields: list[str] | None = None
    max_tokens: int | None = None


@dataclass
class Node:
    id: str
    kind: NodeKind
    name: str
    location: SourceLocation | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMStep(Node):
    step_kind: StepKind = StepKind.CALL
    framework: str | None = None  # anthropic, openai, langchain, claude_code, crewai, ...
    model: ModelRef = field(default_factory=ModelRef)
    prompt: list[PromptPart] = field(default_factory=list)
    output: OutputSpec = field(default_factory=OutputSpec)
    temperature: float | None = None
    thinking: dict[str, Any] | None = None  # {"budget_tokens": N} / {"effort": "high"} / reasoning_effort
    tool_choice: str | None = None  # "auto" | "any" | "required" | "none" | "<tool name>"
    tool_names: list[str] = field(default_factory=list)
    cache_control: bool = False  # explicit prompt caching configured
    max_iterations: int | None = None  # agents: max_turns / max_iter; None = unknown/unbounded
    description: str | None = None  # routing description (agents/skills), often always-loaded

    def static_text(self, roles: set[str] | None = None) -> str:
        return "\n".join(p.text for p in self.prompt if roles is None or p.role in roles)

    def variables(self) -> list[PromptVariable]:
        return [v for p in self.prompt for v in p.variables]


@dataclass
class Edge:
    src: str
    dst: str
    kind: EdgeKind
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Diagnostic:
    level: str  # info | warning
    code: str  # e.g. UNRESOLVED_MODEL, DYNAMIC_PROMPT, PARSE_ERROR
    message: str
    location: SourceLocation | None = None


@dataclass
class FileRecord:
    path: str
    sha256: str
    extractor: str | None  # None = discovered but no extractor applied


@dataclass
class SystemIR:
    root: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    schema_version: str = IR_SCHEMA_VERSION

    # -- construction -------------------------------------------------------
    def add(self, node: Node) -> Node:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id {node.id}")
        self.nodes[node.id] = node
        return node

    def link(self, src: str, dst: str, kind: EdgeKind, **attrs: Any) -> Edge:
        edge = Edge(src, dst, kind, dict(attrs))
        self.edges.append(edge)
        return edge

    def warn(self, code: str, message: str, location: SourceLocation | None = None) -> None:
        self.diagnostics.append(Diagnostic("warning", code, message, location))

    def merge(self, other: SystemIR) -> None:
        for node in other.nodes.values():
            self.add(node)
        self.edges.extend(other.edges)
        self.files.extend(other.files)
        self.diagnostics.extend(other.diagnostics)

    # -- queries --------------------------------------------------------------
    def llm_steps(self) -> list[LLMStep]:
        return [n for n in self.nodes.values() if isinstance(n, LLMStep)]

    def of_kind(self, kind: NodeKind) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]

    # -- serialization --------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "nodes": [_node_to_dict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
            "files": [asdict(f) for f in self.files],
            "diagnostics": [asdict(d) for d in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemIR:
        ir = cls(root=data["root"], schema_version=data.get("schema_version", IR_SCHEMA_VERSION))
        for nd in data["nodes"]:
            ir.add(_node_from_dict(nd))
        ir.edges = [Edge(e["src"], e["dst"], EdgeKind(e["kind"]), e.get("attrs", {})) for e in data["edges"]]
        ir.files = [FileRecord(**f) for f in data["files"]]
        ir.diagnostics = [
            Diagnostic(d["level"], d["code"], d["message"], _loc(d.get("location"))) for d in data["diagnostics"]
        ]
        return ir


def stable_id(*parts: object) -> str:
    """Deterministic short id: same source -> same id across runs (needed for baselines/diffs)."""
    digest = hashlib.sha1("\x1f".join(str(p) for p in parts).encode()).hexdigest()
    return digest[:12]


def _node_to_dict(node: Node) -> dict[str, Any]:
    data = asdict(node)
    data["__type__"] = type(node).__name__
    return data


def _loc(d: dict[str, Any] | None) -> SourceLocation | None:
    return SourceLocation(**d) if d else None


def _node_from_dict(d: dict[str, Any]) -> Node:
    d = dict(d)
    typ = d.pop("__type__", "Node")
    d["kind"] = NodeKind(d["kind"])
    d["location"] = _loc(d.get("location"))
    if typ != "LLMStep":
        return Node(**{k: d[k] for k in ("id", "kind", "name", "location", "attrs")})
    d["step_kind"] = StepKind(d["step_kind"])
    d["model"] = ModelRef(**d["model"])
    d["prompt"] = [
        PromptPart(
            role=p["role"],
            text=p["text"],
            variables=[PromptVariable(**{**v, "source": VarSource(v["source"])}) for v in p["variables"]],
            location=_loc(p.get("location")),
            always_loaded=p.get("always_loaded", False),
        )
        for p in d["prompt"]
    ]
    out = d["output"]
    d["output"] = OutputSpec(**{**out, "kind": OutputKind(out["kind"]), "enforcement": Enforcement(out["enforcement"])})
    known = {f.name for f in fields(LLMStep)}
    return LLMStep(**{k: v for k, v in d.items() if k in known})


def dumps(ir: SystemIR) -> str:
    return json.dumps(ir.to_dict(), ensure_ascii=False, indent=2, sort_keys=False)
