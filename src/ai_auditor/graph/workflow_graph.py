"""Graph view over the IR: indices and structural queries used by rules.

Kept dependency-free on purpose (no networkx): the queries rules need are a
handful of neighbourhood lookups and reachability walks over small graphs.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from ai_auditor.ir.model import Edge, EdgeKind, LLMStep, Node, NodeKind, SystemIR


@dataclass(frozen=True)
class Multiplicity:
    """How often a step can run per execution, as far as static analysis can tell."""

    in_loop: bool
    loop_bounded: bool | None  # None = unknown
    max_retries: int | None  # None = no retry policy found / unknown
    unbounded_retries: bool

    @property
    def per_execution(self) -> str:
        if not self.in_loop and self.max_retries is None:
            return "1"
        if self.in_loop:
            return "N (inside loop; N unknown statically)"
        return f"1..{self.max_retries + 1}" if self.max_retries is not None else "1..?"


class WorkflowGraph:
    def __init__(self, ir: SystemIR) -> None:
        self.ir = ir
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)
        for e in ir.edges:
            self._out[e.src].append(e)
            self._in[e.dst].append(e)

    # -- primitive lookups ----------------------------------------------------
    def node(self, node_id: str) -> Node:
        return self.ir.nodes[node_id]

    def out_edges(self, node_id: str, kind: EdgeKind | None = None) -> list[Edge]:
        return [e for e in self._out.get(node_id, []) if kind is None or e.kind == kind]

    def in_edges(self, node_id: str, kind: EdgeKind | None = None) -> list[Edge]:
        return [e for e in self._in.get(node_id, []) if kind is None or e.kind == kind]

    def successors(self, node_id: str, kind: EdgeKind | None = None) -> list[Node]:
        return [self.ir.nodes[e.dst] for e in self.out_edges(node_id, kind) if e.dst in self.ir.nodes]

    def predecessors(self, node_id: str, kind: EdgeKind | None = None) -> list[Node]:
        return [self.ir.nodes[e.src] for e in self.in_edges(node_id, kind) if e.src in self.ir.nodes]

    # -- semantic queries -------------------------------------------------------
    def llm_steps(self) -> list[LLMStep]:
        return self.ir.llm_steps()

    def consumers(self, step_id: str) -> list[Node]:
        """Nodes that receive this step's output as data."""
        return self.successors(step_id, EdgeKind.DATA_FLOW)

    def producers(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.DATA_FLOW)

    def controlled_branches(self, step_id: str) -> list[Edge]:
        """CONTROLS edges: the step's output decides a branch."""
        return self.out_edges(step_id, EdgeKind.CONTROLS)

    def validators_of(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.VALIDATES)

    def retry_policies_of(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.RETRIES)

    def tools_of(self, step_id: str) -> list[Node]:
        return self.successors(step_id, EdgeKind.USES_TOOL)

    def retrievals_for(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.RETRIEVES)

    def context_sources_for(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.INJECTS_CONTEXT)

    def delegates_of(self, step_id: str) -> list[Node]:
        return self.successors(step_id, EdgeKind.DELEGATES)

    def delegators_of(self, step_id: str) -> list[Node]:
        return self.predecessors(step_id, EdgeKind.DELEGATES)

    def enclosing(self, node_id: str, kind: NodeKind) -> list[Node]:
        """Transitive CONTAINS ancestors of a given kind (e.g. enclosing loops)."""
        found: list[Node] = []
        seen: set[str] = set()
        queue = deque([node_id])
        while queue:
            cur = queue.popleft()
            for parent in self.predecessors(cur, EdgeKind.CONTAINS):
                if parent.id in seen:
                    continue
                seen.add(parent.id)
                if parent.kind == kind:
                    found.append(parent)
                queue.append(parent.id)
        return found

    def multiplicity(self, step_id: str) -> Multiplicity:
        loops = self.enclosing(step_id, NodeKind.LOOP)
        retries = self.retry_policies_of(step_id)
        bounded: bool | None = None
        if loops:
            flags = [lp.attrs.get("bounded") for lp in loops]
            bounded = False if False in flags else (None if None in flags else True)
        max_r: int | None = None
        unbounded = False
        for r in retries:
            n = r.attrs.get("max_attempts")
            if n is None:
                unbounded = unbounded or bool(r.attrs.get("unbounded"))
            else:
                max_r = max(max_r or 0, int(n) - 1)
        return Multiplicity(bool(loops), bounded, max_r, unbounded)

    def downstream(self, node_id: str, kinds: tuple[EdgeKind, ...] = (EdgeKind.DATA_FLOW, EdgeKind.CONTROLS)) -> list[Node]:
        """All nodes transitively reachable through data/control edges."""
        seen: set[str] = set()
        out: list[Node] = []
        queue = deque([node_id])
        while queue:
            cur = queue.popleft()
            for e in self._out.get(cur, []):
                if e.kind in kinds and e.dst not in seen and e.dst in self.ir.nodes:
                    seen.add(e.dst)
                    out.append(self.ir.nodes[e.dst])
                    queue.append(e.dst)
        return out

    # -- export -------------------------------------------------------------------
    def to_mermaid(self) -> str:
        shape = {
            NodeKind.LLM_STEP: ("([", "])"),
            NodeKind.TOOL: ("[/", "/]"),
            NodeKind.RETRIEVAL: ("[(", ")]"),
            NodeKind.CONDITIONAL: ("{", "}"),
            NodeKind.VALIDATION: ("[[", "]]"),
        }
        lines = ["flowchart TD"]
        for n in self.ir.nodes.values():
            left, right = shape.get(n.kind, ("[", "]"))
            label = n.name.replace('"', "'")
            if isinstance(n, LLMStep) and n.model.raw:
                label += f"<br/><i>{n.model.raw}</i>"
            lines.append(f'  n{n.id}{left}"{label}"{right}')
        style = {EdgeKind.DATA_FLOW: "-->", EdgeKind.CONTROLS: "-.->", EdgeKind.CONTAINS: "---"}
        for e in self.ir.edges:
            if e.src in self.ir.nodes and e.dst in self.ir.nodes:
                lines.append(f"  n{e.src} {style.get(e.kind, '-->')}|{e.kind.value}| n{e.dst}")
        return "\n".join(lines)

    def to_dot(self) -> str:
        lines = ["digraph workflow {", "  rankdir=TB;"]
        for n in self.ir.nodes.values():
            shape = "box" if n.kind == NodeKind.LLM_STEP else "ellipse"
            lines.append(f'  "{n.id}" [label="{n.kind.value}: {n.name}", shape={shape}];')
        for e in self.ir.edges:
            lines.append(f'  "{e.src}" -> "{e.dst}" [label="{e.kind.value}"];')
        lines.append("}")
        return "\n".join(lines)
