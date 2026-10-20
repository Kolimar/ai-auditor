"""Architecture rules: redundant agents, needless delegation, distillation, unbounded loops, batch, parallelism."""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import EvidenceLevel, Finding, Risk, Severity
from ai_auditor.ir.model import INSTRUCTION_FRAMEWORKS, EdgeKind, LLMStep, Node, NodeKind, StepKind, VarSource
from ai_auditor.optimization.profile import TASK_LEXICON
from ai_auditor.parser.tokens import count_tokens
from ai_auditor.rules._common import CLASS_A, CLASS_C, Builder, finding, potential, severity_for, skip_step

EXPLORATORY_TOOLS = {"read", "grep", "glob", "websearch", "webfetch", "bash", "ls", "search", "browse"}
BATCH_PROVIDERS = {"anthropic", "openai", "google"}
DELEGATION_TOOLS = {"task", "agent"}


def _shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


_APP_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", ".git")


def _app_root(root: Path, rel: str | None, cache: dict[str, str]) -> str:
    """Nearest directory (inside the audited root) that looks like its own application; '' is the audited root itself."""
    parent = str(Path(rel).parent) if rel else ""
    parent = "" if parent == "." else parent
    if parent in cache:
        return cache[parent]
    cur = Path(parent) if parent else None
    found = ""
    while cur is not None and str(cur) not in ("", "."):
        d = root / cur
        if any((d / m).exists() for m in _APP_MARKERS) or any(d.glob("requirements*.txt")):
            found = str(cur)
            break
        cur = cur.parent if str(cur.parent) not in ("", ".") else None
    cache[parent] = found
    return found


def _instructions(step: LLMStep) -> str:
    return re.sub(r"\{[^{}]*\}", " ", step.static_text())


@register
class RedundantAgent(Rule):
    id = "LLM-006"
    title = "Redundant Agent"
    category = "architecture"

    SIMILARITY = 0.8

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        steps = [s for s in ctx.ir.llm_steps() if not skip_step(s) and not s.attrs.get("non_production")]
        yield from self._near_duplicates(ctx, steps)
        yield from self._resummarize(ctx, steps)

    def _near_duplicates(self, ctx: AnalysisContext, steps: list[LLMStep]) -> Iterable[Finding]:
        texts = {s.id: _instructions(s) for s in steps}
        sh = {sid: _shingles(t) for sid, t in texts.items() if count_tokens(t) >= 40}
        root, roots = Path(ctx.ir.root), {}  # type: ignore[var-annotated]
        for a, b_ in combinations([s for s in steps if s.id in sh], 2):
            if a.location == b_.location:
                continue
            # copies inside separate applications of a monorepo/examples collection never run in the same system
            if a.framework not in INSTRUCTION_FRAMEWORKS and b_.framework not in INSTRUCTION_FRAMEWORKS and \
                    _app_root(root, a.location and a.location.file, roots) != _app_root(root, b_.location and b_.location.file, roots):
                continue
            la, lb = len(sh[a.id]), len(sh[b_.id])
            if min(la, lb) < self.SIMILARITY * max(la, lb):  # Jaccard <= min/max: cannot reach the threshold
                continue
            sim = _jaccard(sh[a.id], sh[b_.id])
            if sim < self.SIMILARITY:
                continue
            tools_a, tools_b = set(a.tool_names), set(b_.tool_names)
            for this, other in ((a, b_), (b_, a)):
                b = Builder()
                b.pro("prompt_text", f"instructions are {sim:.0%} similar (word 3-gram Jaccard) to '{other.name}' ({other.location})", 0.45 + 0.4 * (sim - self.SIMILARITY) / (1 - self.SIMILARITY), this.location)
                if tools_a != tools_b:
                    b.con("ir", f"different tools: {sorted(tools_a ^ tools_b)[:5]}", 0.5)
                cfg_a = (this.model.raw, str(this.thinking), this.temperature)
                cfg_b = (other.model.raw, str(other.thinking), other.temperature)
                if cfg_a != cfg_b:
                    b.con("ir", f"different model/effort settings ({cfg_a} vs {cfg_b}): a deliberate escalation tier", 0.7)
                srcs_a = {v.source for v in this.variables()}
                srcs_b = {v.source for v in other.variables()}
                if srcs_a != srcs_b:
                    b.con("ir", "the two steps receive different kinds of input", 0.25)
                same_def = this.name == other.name and this.framework in INSTRUCTION_FRAMEWORKS
                f = finding(
                    self, ctx, this, b, CLASS_C, severity=Severity.LOW,
                    reasoning="Two steps with near-identical instructions usually do the same job; keeping both duplicates maintenance and, if both run, cost.",
                    current=(f"Two diverging copies of '{this.name}' are installed ({this.location} and {other.location})." if same_def
                             else f"'{this.name}' and '{other.name}' share most of their instructions."),
                    change=("Keep one version and remove the other: both descriptions are loaded into every session and which one "
                            "runs depends on resolution order." if same_def
                            else "Merge them into one parameterized step (or one agent) and route the differing part as input."),
                    alternative="If they intentionally differ (persona, tools, audience), make that difference explicit and drop the shared boilerplate into a common cached prefix.",
                    risk=Risk.MEDIUM, risks=["The small textual difference may be exactly what matters; diff the prompts before merging."],
                    validation="Run both on the same inputs and compare outputs; if equivalent within a margin, keep one.",
                    requires_runtime=False,
                )
                if f:
                    f.related = [other.id]
                    yield f

    def _resummarize(self, ctx: AnalysisContext, steps: list[LLMStep]) -> Iterable[Finding]:
        def summarizes(s: LLMStep) -> bool:
            # a Claude Code agent's description states its job ("Summarizes one paper into a note")
            return ctx.profile(s).primary == "summarize" or (
                s.framework in INSTRUCTION_FRAMEWORKS and bool(TASK_LEXICON["summarize"].search(s.description or "")))

        for step in steps:
            if not summarizes(step):
                continue
            ups = [u for u in ctx.graph.producers(step.id) if isinstance(u, LLMStep) and summarizes(u)]
            if not ups:
                continue
            up = ups[0]
            m_up, m_this = ctx.graph.multiplicity(up.id), ctx.graph.multiplicity(step.id)
            if m_up.in_loop and not m_this.in_loop:
                continue  # map-reduce over chunks: legitimate hierarchical summarization
            # parameters fed by the upstream summary at a call site (`second(first(x))`) are that summary, not other inputs
            fed = {m.group(1) for e in ctx.ir.edges if e.src == up.id and e.dst == step.id
                   for m in [re.search(r"\((\w+)\)$", str(e.attrs.get("via", "")))] if m}
            other_inputs = [v for v in step.variables() if v.source not in (VarSource.LLM_OUTPUT, VarSource.CONSTANT)
                            and not {re.split(r"\W", v.name)[0], re.split(r"\W", v.expression or "")[0]} & fed]
            b = Builder()
            b.pro("graph", f"summarizes the output of '{up.name}', which is itself a summary", 0.45, step.location)
            if other_inputs:
                b.con("ir", f"also receives other inputs {[v.name for v in other_inputs[:3]]}", 0.5)
            if ctx.profile(step).output_space != ctx.profile(up).output_space:
                b.con("profile", "output format differs from the upstream summary", 0.2)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning="Summarizing a summary loses information twice and pays two calls; one call with the final length/format target is usually enough.",
                current=f"'{up.name}' summarizes, then '{step.name}' summarizes that summary.",
                change=f"Ask '{up.name}' directly for the final length and format, and drop '{step.name}'.",
                risk=Risk.MEDIUM, risks=["The two stages may serve different audiences; check where each output goes."],
                validation="Compare the single-call summary with the two-stage one on a sample (human or rubric review, not a single LLM judge).",
                requires_runtime=True,
            )
            if f:
                f.related = [up.id]
                f.impact.static_potential = potential(ctx, step, 1.0, None)
                yield f


@register
class UnnecessaryDelegation(Rule):
    id = "LLM-012"
    title = "Unnecessary Multi-Agent Delegation"
    category = "architecture"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.step_kind != StepKind.AGENT:
                continue
            if step.framework in INSTRUCTION_FRAMEWORKS and (step.attrs.get("cc_type") in ("skill", "command") or int(step.attrs.get("body_tokens") or 0) > 400):
                # skills and substantial agents do their own work; a command is a prompt the user types into the main
                # session, which runs anyway: invoking an agent from it adds no hop
                continue
            delegates = [d for d in ctx.graph.delegates_of(step.id) if isinstance(d, LLMStep)]
            if len(delegates) != 1:
                continue
            target = delegates[0]
            own_tools = {t.lower() for t in step.tool_names if t and t != "?"} - DELEGATION_TOOLS - {target.name.lower()}
            if own_tools:
                continue
            b = Builder()
            b.pro("graph", f"only job is delegating to a single agent '{target.name}'; no tools of its own", 0.45, step.location)
            if step.framework in INSTRUCTION_FRAMEWORKS:
                body = int(step.attrs.get("body_tokens") or 0)
                if body < 150:
                    b.pro("prompt_text", f"short body (~{body} tokens) beyond the delegation", 0.15)
                else:
                    b.con("prompt_text", f"~{body} tokens of own instructions: may add context or synthesis", 0.3)
            # The delegate's own model, exploratory tools or restricted permissions justify the delegate, not this hop:
            # invoking the delegate directly keeps all of them (docs/RULES.md, LLM-012 "No es").
            ti, si = ctx.profile(target).model, ctx.profile(step).model
            kept = []
            if ti and si and ti.id != si.id:
                kept.append(f"model {ti.id}")
            explor = {t.lower() for t in target.tool_names} & EXPLORATORY_TOOLS
            if explor:
                kept.append(f"exploratory tools {sorted(explor)}")
            if target.attrs.get("tools_inherited") is False and step.attrs.get("tools_inherited") is not False:
                kept.append("its restricted tool set")
            if kept:
                b.pro("ir", f"calling '{target.name}' directly keeps its {', '.join(kept)}", 0.05)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("Each agent hop adds a model turn (and re-sends context). Delegation pays off with parallelism, context "
                           "isolation, different tools/permissions or a different model; none is visible here."),
                current=f"'{step.name}' forwards the task to '{target.name}'.",
                change=f"Invoke '{target.name}' directly (or merge its instructions into '{step.name}').",
                risk=Risk.LOW, risks=["The orchestrator may add framing the delegate relies on."],
                validation="Run the task set with and without the intermediate agent; compare success rate and total tokens per task.",
                requires_runtime=True,
            )
            if f:
                f.related = [target.id]
                f.impact.static_potential = potential(ctx, step, 1.0, None, "one agent hop removed")
                yield f


@register
class DistillationCandidate(Rule):
    id = "LLM-019"
    title = "Candidate for Distillation"
    category = "model_selection"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            p = ctx.profile(step)
            if p.few_shot < 3 or p.output_space != "closed" or p.primary not in ("classify", "extract", "decide"):
                continue
            mult = ctx.graph.multiplicity(step.id)
            volume = mult.in_loop or bool(step.attrs.get("entrypoints"))
            b = Builder()
            b.pro("prompt_text", f"{p.few_shot} few-shot examples define a stable input→label mapping over {len(p.labels)} labels", 0.35, step.location)
            if volume:
                b.pro("graph", "runs at volume (loop or request handler)", 0.15)
            else:
                b.con("graph", "call volume unknown statically", 0.2)
            if p.judgment:
                b.con("prompt_text", f"judgment cues {p.judgment[:3]}", 0.3)
            if p.risk_domains:
                b.con("prompt_text", f"risk domain {sorted(p.risk_domains)}", 0.3)
            f = finding(
                self, ctx, step, b, CLASS_C, cap=EvidenceLevel.HYPOTHESIS, severity=Severity.LOW,
                reasoning=("Narrow, high-volume classification is the setting where a small fine-tuned model or rules learned from "
                           "logged outputs match the LLM. Whether the mapping is stable can only be shown from traces."),
                current=f"LLM classification into {p.labels[:6]} guided by {p.few_shot} examples.",
                change="Log inputs/outputs; once enough traces exist, run `ai-auditor distill` to mine rules or train a small classifier, with LLM fallback on abstention.",
                risk=Risk.MEDIUM, risks=["Distribution shift: the distilled model must abstain on unfamiliar inputs."],
                validation="Fidelity to LLM labels on a held-out trace split (with CI) and coverage at a fixed abstention threshold.",
                requires_runtime=True,
            )
            if f:
                yield f


def _loop_component(n: Node) -> str:
    return n.name.split(":", 1)[-1]


@register
class UnboundedLoop(Rule):
    id = "LLM-021"
    title = "Unbounded Agent Loop"
    category = "reliability"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        g = ctx.graph
        for lp in ctx.ir.of_kind(NodeKind.LOOP):
            if lp.attrs.get("bounded") is True or lp.attrs.get("human_turn"):
                continue  # a chat REPL is bounded by the person typing; inner agent loops are reported on their own
            inner = [n for n in g.successors(lp.id, EdgeKind.CONTAINS) if isinstance(n, LLMStep) and not skip_step(n)]
            if not inner:
                continue
            b = Builder()
            if lp.attrs.get("bounded") is False:
                b.pro("code", "loop has no condition, break or return that can end it", 0.75, lp.location)
            elif lp.attrs.get("exit") in ("model_dependent", "return"):
                b.pro("code", "`while True` that ends only when the model's output says so; no iteration cap", 0.65, lp.location)
            else:
                b.pro("code", "while-loop with no recognizable iteration bound", 0.4, lp.location)
            if lp.attrs.get("agentic"):
                b.pro("code", "agentic loop (tools/history): each iteration re-sends a growing context", 0.15)
            f = finding(
                self, ctx, inner[0], b, CLASS_A, component=_loop_component(lp), location=lp.location,
                severity=Severity.HIGH if lp.attrs.get("bounded") is False else severity_for(ctx, inner[0], Severity.MEDIUM),
                reasoning="Without an iteration cap a model that never emits the stop condition loops until timeout or budget exhaustion, and agent loops re-send the whole history each turn.",
                current=f"Loop around {[s.name for s in inner]} with no maximum number of iterations.",
                change="Add a max-iterations cap (and a token/cost budget) with an explicit failure path when it is reached.",
                risk=Risk.LOW, risks=["Pick the cap from the observed iteration distribution so legitimate long runs are not cut."],
                validation="From traces: distribution of iterations per execution; set the cap above its p99 and alert when hit.",
                requires_runtime=False,
            )
            if f:
                f.related = [s.id for s in inner]
                yield f
        for rt in ctx.ir.of_kind(NodeKind.RETRY):
            if not rt.attrs.get("unbounded"):
                continue
            targets = [n for n in g.successors(rt.id, EdgeKind.RETRIES) if isinstance(n, LLMStep) and not skip_step(n)]
            if not targets:
                continue
            parsed = any(t.attrs.get("parsed_as_json") or t.attrs.get("parsed_with_regex") for t in targets)
            if rt.attrs.get("trigger") == "format" or (rt.attrs.get("trigger") in ("mixed", "any") and parsed):
                continue  # LLM-008 reports it, including the missing limit
            b = Builder()
            b.pro("code", f"{rt.attrs.get('mechanism')} retry on {rt.attrs.get('exceptions') or 'any exception'} without an attempt limit", 0.7, rt.location)
            f = finding(
                self, ctx, targets[0], b, CLASS_A, component=_loop_component(rt), location=rt.location, severity=Severity.HIGH,
                reasoning="An unlimited retry turns a persistent failure (bad request, outage, quota) into unbounded spend and a hung execution.",
                current=f"Retries of {[t.name for t in targets]} never give up.",
                change="Cap attempts (e.g. 3) with exponential backoff and jitter; retry only transient errors.",
                risk=Risk.LOW, validation="Inject a persistent failure in a test and assert the call gives up after N attempts.",
                requires_runtime=False,
            )
            if f:
                f.related = [t.id for t in targets]
                yield f
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.step_kind != StepKind.AGENT or step.framework in INSTRUCTION_FRAMEWORKS:
                continue
            prov = (step.attrs.get("provenance") or {}).get("max_iterations")
            if prov == "absent" and step.max_iterations is None:
                b = Builder()
                b.pro("code", f"{step.framework} agent without a turn/iteration limit, and the SDK sets no default", 0.6, step.location)
                f = finding(
                    self, ctx, step, b, CLASS_A, severity=severity_for(ctx, step, Severity.MEDIUM),
                    reasoning="An agent without a turn limit can loop on tool calls until timeout.",
                    current="Agent run without max turns/iterations.", change="Set the SDK's max turns/iterations parameter.",
                    risk=Risk.LOW, validation="Check the iteration distribution in traces before choosing the cap.",
                    requires_runtime=False,
                )
                if f:
                    yield f


@register
class BatchOpportunity(Rule):
    id = "LLM-024"
    title = "Batch API Opportunity"
    category = "cost"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        g = ctx.graph
        for lp in ctx.ir.of_kind(NodeKind.LOOP):
            if not lp.attrs.get("batch_data"):
                continue
            inner = [n for n in g.successors(lp.id, EdgeKind.CONTAINS)
                     if isinstance(n, LLMStep) and not skip_step(n) and n.step_kind == StepKind.CALL]
            if not inner:
                continue
            entries = {e for s in inner for e in s.attrs.get("entrypoints", [])}
            if "web" in entries:
                continue
            if any(s.attrs.get("history_accumulates") for s in inner):
                continue  # iterations depend on each other
            b = Builder()
            b.pro("code", f"loop over a dataset (`{lp.attrs.get('iter')}`) with synchronous calls to {[s.name for s in inner][:4]}", 0.5, lp.location)
            if "script" in entries:
                b.pro("code", "runs as a script (`if __name__ == '__main__'`), not a request handler", 0.3)
            else:
                b.con("context", "latency requirements unknown statically", 0.15)
            providers = {ctx.profile(s).model.provider for s in inner if ctx.profile(s).model}
            if providers and not providers <= BATCH_PROVIDERS:
                b.con("ir", f"batch support through {sorted(providers)} depends on the underlying provider", 0.2)
            if not providers:
                b.con("ir", "provider unknown", 0.15)
            for step in inner:
                info = ctx.profile(step).model
                ratio = ""
                if info and info.price and info.price.batch_input and info.price.input:
                    ratio = f" ({info.id}: batch input {info.price.batch_input} vs {info.price.input} $/MTok per catalog {info.price.retrieved_at})"
                f = finding(
                    self, ctx, step, Builder(list(b.evidence)), CLASS_A, location=step.location,
                    severity=severity_for(ctx, step, Severity.LOW),
                    reasoning=("Offline bulk work does not need synchronous responses. Provider batch APIs run the same model on the "
                               "same prompts at a discount (official price pages)" + ratio + "."),
                    current=f"'{step.name}' is called synchronously once per item of `{lp.attrs.get('iter')}` ({lp.location}).",
                    change="Submit the items through the provider's Batch API and collect results asynchronously (typically within 24 h).",
                    alternative="If results are needed quickly, at least run calls concurrently with a rate limiter.",
                    risk=Risk.LOW, risks=["Batch results are not immediate; unsuitable if a user waits on them."],
                    validation="Run one batch on a sample; outputs match the synchronous path distributionally (same model/params).",
                    requires_runtime=False,
                )
                if f:
                    f.related = [s.id for s in inner if s is not step]
                    f.impact.static_potential = potential(ctx, step, 0.0, None, "same calls at batch price")
                    yield f


@register
class SequentialIndependentCalls(Rule):
    id = "LLM-025"
    title = "Sequential Independent Calls"
    category = "latency"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        g = ctx.graph
        for wf in ctx.ir.of_kind(NodeKind.WORKFLOW):
            seq = sorted(wf.attrs.get("sequence", []), key=lambda it: it["line"])
            if len(seq) < 2 or any(it.get("parallel") for it in seq):
                continue  # already concurrent in part: do not second-guess the author's grouping
            # stage = 1 + max stage of the items it depends on (data dependency or a branch on their output in between)
            stage: list[int] = []
            for j, item in enumerate(seq):
                deps = [i for i in range(j) if self._depends(g, wf, seq[i], item)]
                stage.append(1 + max((stage[i] for i in deps), default=0))
            n_stages = max(stage)
            if n_stages == len(seq):
                continue  # fully sequential chain
            steps_by_stage: dict[int, list[LLMStep]] = {}
            for it, st in zip(seq, stage):
                for sid in it["steps"]:
                    node = ctx.ir.nodes.get(sid)
                    if isinstance(node, LLMStep) and not skip_step(node):
                        steps_by_stage.setdefault(st, []).append(node)
            groups = {k: v for k, v in steps_by_stage.items() if len(v) >= 2}
            if not groups:
                continue
            first = next(iter(groups.values()))[0]
            b = Builder()
            desc = "; ".join(f"stage {k}: {[s.name for s in v]}" for k, v in sorted(groups.items()))
            b.pro("graph", f"{len(seq)} LLM operations awaited one after another in '{wf.name}' fit in {n_stages} dependency stage(s) — {desc}", 0.6, wf.location)
            b.pro("graph", "calls in the same stage share no data and no branch on each other's output", 0.15)
            b.con("code", "shared side effects (state, rate limits) cannot be ruled out statically", 0.1)
            f = finding(
                self, ctx, first, b, CLASS_A, component=wf.name, location=wf.location, severity=Severity.LOW,
                reasoning="Independent calls awaited one after another add their latencies; run concurrently, each stage costs the latency of its slowest call. Cost is unchanged.",
                current=f"{len(seq)} sequential LLM operations, {n_stages} of which are on the critical path.",
                change="Run the calls of each stage concurrently (asyncio.gather / thread pool) and join before the next stage.",
                risk=Risk.LOW, risks=["Concurrency raises peak request rate; respect provider rate limits."],
                validation="Compare end-to-end latency (p50/p95) before/after; outputs must be identical in distribution.",
                requires_runtime=False,
            )
            if f:
                f.related = [s.id for v in groups.values() for s in v]
                f.impact.static_potential = potential(ctx, first, 0.0, 0, f"latency only: {len(seq)} sequential waits → {n_stages}")
                yield f

    @staticmethod
    def _depends(g, wf: Node, earlier: dict, item: dict) -> bool:
        if set(earlier["steps"]) & set(item.get("deps", [])):
            return True
        for sid in earlier["steps"]:
            for edge in g.controlled_branches(sid):
                cond = g.node(edge.dst)
                if cond.location is None or cond.location.line is None or (wf.location and cond.location.file != wf.location.file):
                    continue
                if earlier["line"] < cond.location.line < item["line"]:
                    return True
        return False
