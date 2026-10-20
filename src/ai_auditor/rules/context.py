"""Context, caching and retrieval rules."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Iterable

from ai_auditor.analyzers.engine import AnalysisContext, Rule, register
from ai_auditor.analyzers.finding import Finding, Risk, Severity
from ai_auditor.ir.model import EdgeKind, LLMStep, Node, NodeKind, StepKind, VarSource
from ai_auditor.parser.tokens import count_tokens
from ai_auditor.rules._common import CLASS_A, CLASS_C, Builder, finding, potential, severity_for, skip_step

# Broad-scope objects (whole state/history/profile). Serializing the item being processed (order, ticket...) is normal.
WHOLE_OBJECT = re.compile(r"(?i)(json\.dumps|str|repr|model_dump_json|to_json|vars)\((self\.)?(state|context|ctx|session|history|conversation|memory|everything|profile|(all|full|entire|whole)_\w+)\b")
SUBJECT_TASKS = {"summarize", "reason", "translate", "code"}


@register
class ExcessiveContext(Rule):
    id = "LLM-004"
    title = "Excessive Context Injection"
    category = "context"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        cfg = ctx.config
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.framework == "claude_code":
                continue  # Claude Code bodies load on demand; always-loaded memory/descriptions are handled below
            p = ctx.profile(step)
            narrow = p.output_space in ("closed", "structured") and p.primary not in SUBJECT_TASKS
            b = Builder()
            tokens = None
            for v in step.variables():
                if v.source == VarSource.FILE and (v.est_tokens or 0) > 1000 and narrow:
                    b.pro("input", f"file {v.name} injected (~{v.est_tokens} tokens) into a narrow task", 0.5, step.location)
                    tokens = (tokens or 0) + (v.est_tokens or 0)
                expr = v.expression or v.name
                if WHOLE_OBJECT.search(expr) and narrow:
                    b.pro("input", f"whole broad-scope object serialized into the prompt: {expr[:60]}", 0.35, step.location)
            if p.static_tokens > cfg.excessive_context_tokens and narrow:
                b.pro("prompt", f"~{p.static_tokens} static tokens for a '{p.primary}' task with {p.output_space} output", 0.45)
                tokens = (tokens or 0) + p.static_tokens
            if step.attrs.get("history_accumulates") and not step.attrs.get("history_trimmed"):
                b.pro("code", "conversation history grows every iteration with no trimming/compaction", 0.45, step.location)
                cap = step.attrs.get("history_bound")
                if isinstance(cap, int) and cap <= 20:
                    b.con("code", f"the loop is capped at {cap} iterations, which also bounds the history", 0.35)
            if not b.evidence:
                continue
            if p.primary in SUBJECT_TASKS:
                b.con("profile", f"context is the subject of a '{p.primary}' task", 0.6)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("Every input token is paid on every call, and long, mostly irrelevant context also degrades accuracy "
                           "(lost-in-the-middle, distractors)."),
                current="The prompt carries more context than the task output suggests it needs.",
                change="Send only the fields the task uses (select/serialize a projection), trim or compact history, and keep static reference text in a cached prefix.",
                alternative="If the full context is needed sometimes, route: small context first, full context on failure.",
                risk=Risk.MEDIUM, risks=["Removing context can drop information the model was silently using."],
                validation="Ablation on a labelled sample: quality with full vs reduced context, with a pre-registered margin; compare input tokens.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, tokens)
                yield f
        # Claude Code: always-loaded memory files
        for node in ctx.ir.of_kind(NodeKind.CONTEXT_SOURCE):
            est = node.attrs.get("est_tokens") or 0
            if node.attrs.get("always_loaded") and est > cfg.excessive_context_tokens:
                b = Builder()
                who = "" if node.attrs.get("loaded_by", "claude_code") == "claude_code" else f" of {node.attrs['loaded_by']}"
                aka = f" (same file as {node.attrs['aliases']})" if node.attrs.get("aliases") else ""
                b.pro("context_source", f"{node.name}{aka} is loaded into every session{who} (~{est} tokens, {node.attrs.get('lines')} lines)", 0.55, node.location)
                f = finding(
                    self, ctx, None, b, CLASS_C, component=node.name, location=node.location, severity=Severity.LOW,
                    reasoning="Always-loaded memory is paid (or cache-read) on every session and competes for attention with the task.",
                    current=f"{node.name} with ~{est} tokens.",
                    change="Keep only rules needed in every session; move procedures to skills (loaded on demand) or linked files.",
                    risk=Risk.LOW, validation="Compare session input tokens and task success before/after on a set of typical tasks.",
                    requires_runtime=True,
                )
                if f:
                    yield f
        # one disproportionate description: routing text loaded in every session, whether or not the agent is used
        for step in ctx.ir.llm_steps():
            if step.framework != "claude_code" or step.attrs.get("cc_type") not in ("agent", "skill") or skip_step(step):
                continue
            desc = step.description or ""
            dt = count_tokens(desc)
            limit = cfg.always_loaded_description_tokens
            # Real plugins routinely use 200-700-token descriptions with routing examples or trigger lists (official
            # ones included): only a very long description without examples is reported on its own; the rest is
            # covered by the aggregate check below.
            if dt <= 4 * limit or re.search(r"(?i)<example>|\bexamples?:|\bejemplos?:|^\s*-?\s*(user|usuario):", desc, re.M):
                continue
            b = Builder()
            b.pro("context_source", f"description of ~{dt} tokens is loaded into every session to route requests "
                                    f"(more than 4x the {limit}-token threshold)", 0.45, step.location)
            f = finding(
                self, ctx, step, b, CLASS_C, severity=Severity.LOW,
                reasoning="Agent and skill descriptions are injected into every session so the model can pick them; a long one is paid on every session and blurs routing.",
                current=f"'{step.name}' has a ~{dt}-token description.",
                change="Keep the description to when to use the agent/skill; move topic lists, procedures and long examples into the body (loaded on demand).",
                risk=Risk.LOW, validation="Check routing accuracy (right agent/skill picked) on a fixed task set before/after.",
                requires_runtime=True,
            )
            if f:
                yield f
        desc_tokens = sum(count_tokens(s.description or "") for s in ctx.ir.llm_steps() if s.framework == "claude_code")
        n = sum(1 for s in ctx.ir.llm_steps() if s.framework == "claude_code" and s.description)
        if desc_tokens > 3000:
            b = Builder()
            b.pro("context_source", f"{n} agent/skill/command descriptions are always loaded: ~{desc_tokens} tokens per session", 0.4)
            long_ones = sorted((count_tokens(s.description or ""), s.name) for s in ctx.ir.llm_steps() if s.framework == "claude_code")[-3:]
            b.pro("context_source", f"longest: {[(name, t) for t, name in reversed(long_ones)]}", 0.1)
            f = finding(
                self, ctx, None, b, CLASS_C, component="*system*", severity=Severity.LOW,
                reasoning="Routing descriptions are injected into every session so the model can pick agents/skills; verbose ones cost tokens and blur routing.",
                current=f"~{desc_tokens} tokens of always-loaded descriptions.",
                change="Shorten descriptions to trigger conditions; move examples and details into the body (loaded on demand).",
                risk=Risk.LOW, validation="Check routing accuracy (right agent/skill picked) on a fixed task set before/after.",
                requires_runtime=True,
            )
            if f:
                yield f


def _paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]


@register
class RepeatedContext(Rule):
    id = "LLM-005"
    title = "Repeated Context"
    category = "caching"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        min_tok = ctx.config.repeated_context_min_tokens
        owners: dict[str, set[str]] = defaultdict(set)
        sizes: dict[str, int] = {}
        # Claude Code agents/skills each run in their own context: shared text is not paid twice per request.
        steps = {s.id: s for s in ctx.ir.llm_steps() if not skip_step(s) and s.framework != "claude_code"}
        for s in steps.values():
            for para in _paragraphs(s.static_text({"system", "developer", "instructions", "user"})):
                h = hashlib.sha1(para.encode()).hexdigest()
                owners[h].add(s.id)
                sizes[h] = count_tokens(para)
        groups: dict[frozenset[str], int] = defaultdict(int)
        for h, ids in owners.items():
            if len(ids) >= 2:
                groups[frozenset(ids)] += sizes[h]
        for ids, tokens in sorted(groups.items(), key=lambda kv: -kv[1]):
            if tokens < min_tok:
                continue
            members = [ctx.ir.nodes[i] for i in ids]
            b = Builder()
            b.pro("prompt_text", f"~{tokens} tokens of identical text appear in {len(members)} prompts: {[m.name for m in members][:5]}", 0.6)
            if not all(isinstance(m, LLMStep) and m.cache_control for m in members):
                b.pro("params", "not all of them use explicit prompt caching", 0.15)
            if tokens >= 1000:
                b.pro("prompt_text", "block exceeds 1,000 tokens", 0.1)
            anchor = next((m for m in members if isinstance(m, LLMStep)), members[0])
            f = finding(
                self, ctx, anchor if isinstance(anchor, LLMStep) else None, b, CLASS_A,
                component=anchor.name, location=anchor.location, severity=Severity.LOW,
                reasoning=("The same block is paid in full by each prompt. Placing it as an identical, stable prefix lets provider "
                           "prompt caching bill it at the cache-read rate (0.025–0.1x of input on current official price pages), "
                           "or it can be deduplicated if some prompts do not need it."),
                current=f"Duplicated block (~{tokens} tokens) in {[m.name for m in members]}.",
                change="Extract the block into one shared constant placed first in each prompt (stable prefix) and enable prompt caching; or drop it where unused.",
                risk=Risk.LOW, risks=["Caching only pays off if calls sharing the prefix happen within the cache TTL."],
                validation="Check cache_read tokens in provider usage after the change; output should be unchanged.",
                requires_runtime=False,
            )
            if f:
                f.related = [m.id for m in members]
                f.impact.static_potential = potential(ctx, anchor, 0.0, tokens * (len(members) - 1), "billable at cache-read rate or removed") if isinstance(anchor, LLMStep) else None
                yield f


@register
class MissingCaching(Rule):
    id = "LLM-014"
    title = "Missing Caching Opportunity"
    category = "caching"

    VOLATILE = re.compile(r"(?i)(now\(|today|date|time|timestamp|uuid|request_id|user_id|session|random)")

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        for step in ctx.ir.llm_steps():
            if skip_step(step) or step.framework == "claude_code":
                continue
            p = ctx.profile(step)
            info = p.model
            if info is None or info.cache_mechanism is None:
                continue
            system = [part for part in step.prompt if part.role in ("system", "developer", "instructions")]
            prefix_text = "\n".join(re.sub(r"\{[^{}]*\}", "", part.text) for part in system)
            prefix_tokens = count_tokens(prefix_text) + int(step.attrs.get("tools_tokens") or 0)
            minimum = info.cache_min_tokens
            b = Builder()
            mult = ctx.graph.multiplicity(step.id)
            repeated = mult.in_loop or bool(step.attrs.get("entrypoints")) or step.step_kind == StepKind.AGENT or step.attrs.get("history_accumulates")
            # (a) explicit-caching providers: large static prefix without cache_control
            if info.cache_mechanism == "explicit" and not step.cache_control and minimum and prefix_tokens >= minimum:
                margin = prefix_tokens / minimum
                b.pro("prompt", f"static prefix ~{prefix_tokens} tokens ≥ cacheable minimum {minimum} for {info.id}; no cache_control set", 0.45 if margin >= 1.3 else 0.25, step.location)
                if repeated:
                    b.pro("graph", f"the call repeats ({mult.per_execution}; entrypoints={step.attrs.get('entrypoints')})", 0.35)
                else:
                    b.con("graph", "reuse frequency within the cache TTL is unknown statically", 0.2)
                if margin < 1.3:
                    b.con("prompt", "token estimate is approximate and close to the minimum", 0.2)
            # (b) volatile content placed before the static prefix (cache-busting for every provider)
            volatile = []
            for part in system:
                first_var = part.text.find("{")
                if first_var != -1:
                    static_after = re.sub(r"\{[^{}]*\}", "", part.text[first_var:])
                    head_vars = [v.name for v in part.variables if self.VOLATILE.search(v.name)]
                    if head_vars and count_tokens(static_after) >= (minimum or 1024) * 0.8:
                        volatile += head_vars
            if volatile:
                b.pro("prompt", f"volatile values {volatile[:3]} precede ~{prefix_tokens} static tokens, so the prefix differs on every call", 0.5)
            if not b.evidence:
                continue
            f = finding(
                self, ctx, step, b, CLASS_A, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("Provider prompt caching bills repeated prefixes at a fraction of the input price (official docs), with "
                           "identical outputs. It requires a byte-identical prefix of at least the model's minimum length and, for "
                           "Anthropic, an explicit cache_control marker."),
                current="Large static prefix re-sent at full price." if not volatile else "Dynamic values at the start of the prompt break prefix caching.",
                change=("Mark the end of the static prefix with cache_control (tools → system → stable messages), and move dynamic "
                        "values after it." if info.cache_mechanism == "explicit" else "Move dynamic values after the static prefix so automatic prefix caching can apply."),
                alternative="Shorten the static prefix if parts are not needed.",
                risk=Risk.LOW, risks=["Writes cost 1.25x (5 min TTL) on Anthropic: needs ≥2 uses within the TTL to pay off."],
                validation="Send two identical requests and confirm cache_read_input_tokens > 0 on the second; compare billed tokens.",
                requires_runtime=False,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, prefix_tokens, "tokens billable at cache-read rate after the first call")
                yield f


@register
class RepeatedRetrieval(Rule):
    id = "LLM-015"
    title = "Repeated Retrieval"
    category = "context"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        retrievals = [r for r in ctx.ir.of_kind(NodeKind.RETRIEVAL) if not r.attrs.get("non_production")]
        by_query: dict[tuple, list] = defaultdict(list)
        for r in retrievals:
            if r.attrs.get("query"):
                # same query against a different store/retriever is a different retrieval
                by_query[(r.attrs.get("function"), r.attrs.get("receiver"), r.attrs["query"])].append(r)
        for r in retrievals:
            b = Builder()
            if r.attrs.get("loops") and r.attrs.get("loop_invariant_query"):
                b.pro("code", f"retrieval '{r.attrs.get('query')}' runs inside a loop with a query that does not change between iterations", 0.7, r.location)
            dup = [d for d in by_query.get((r.attrs.get("function"), r.attrs.get("receiver"), r.attrs.get("query")), [])
                   if d is r or not _exclusive(r, d)]
            if len(dup) > 1 and r is dup[0]:
                b.pro("code", f"the same query is retrieved {len(dup)} times in {r.attrs.get('function')}", 0.5, r.location)
            if not b.evidence:
                continue
            f = finding(
                self, ctx, None, b, CLASS_A, component=r.name.split(":", 1)[-1], location=r.location, severity=Severity.LOW,
                reasoning="Identical retrievals return identical results (absent concurrent index writes); repeating them adds embedding/search cost and latency.",
                current=f"Retrieval with query `{r.attrs.get('query')}` repeated.",
                change="Retrieve once before the loop (or memoize per query within the execution) and reuse the result.",
                risk=Risk.LOW, risks=["If the index is updated during the execution, results could legitimately differ."],
                validation="Assert equal result ids before/after on recorded executions.",
                requires_runtime=False,
            )
            if f:
                yield f


def _exclusive(a: Node, b: Node) -> bool:
    """Two retrievals in the body and the else of the same `if` never both run."""
    sides_a = {x.rsplit(":", 1)[0]: x.rsplit(":", 1)[1] for x in a.attrs.get("branch") or []}
    sides_b = {x.rsplit(":", 1)[0]: x.rsplit(":", 1)[1] for x in b.attrs.get("branch") or []}
    return any(sides_b.get(k) not in (None, v) for k, v in sides_a.items())


def _feeds_llm(ctx: AnalysisContext, r: Node) -> bool:
    if any(e.src == r.id and e.kind == EdgeKind.RETRIEVES for e in ctx.ir.edges):
        return True
    fn = r.attrs.get("function")
    return bool(fn) and any(s.attrs.get("qualname") == fn for s in ctx.ir.llm_steps())


@register
class ExcessiveRAG(Rule):
    id = "LLM-016"
    title = "Excessive RAG Context"
    category = "context"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        cfg = ctx.config
        for r in ctx.ir.of_kind(NodeKind.RETRIEVAL):
            if r.attrs.get("non_production"):
                continue
            k = r.attrs.get("top_k")
            if not isinstance(k, int) or k < cfg.rag_top_k_warn:
                continue
            b = Builder()
            b.pro("code", f"top_k={k} chunks retrieved per query", 0.45 if k >= cfg.rag_top_k_high else 0.3, r.location)
            if not r.attrs.get("rerank"):
                b.pro("code", "no reranking or score threshold detected", 0.2)
            else:
                b.con("code", "a reranker is present", 0.4)
            if r.attrs.get("full_documents"):
                b.pro("code", "each retrieved hit is replaced by its whole source file before it reaches the prompt", 0.25)
            if not _feeds_llm(ctx, r):
                b.con("graph", "no LLM prompt is seen consuming these results (library/helper code, or used across functions)", 0.5)
            f = finding(
                self, ctx, None, b, CLASS_C, component=r.name.split(":", 1)[-1], location=r.location, severity=Severity.LOW,
                reasoning=("Answer quality is non-monotonic in k: more chunks add hard negatives and input tokens. The right k is "
                           "task-specific (the thresholds used here are heuristic)."),
                current=f"top_k={k}, rerank={'yes' if r.attrs.get('rerank') else 'no'}.",
                change="Sweep k ∈ {3,5,10,…} on a labelled set and keep the smallest k within the quality margin; add a reranker or a score cut-off.",
                risk=Risk.MEDIUM, risks=["Recall drops for questions whose evidence is spread across many chunks."],
                validation="k-sweep with groundedness/answer metrics and input-token counts, pre-registered margin.",
                requires_runtime=True,
            )
            if f:
                yield f


@register
class ExcessiveTools(Rule):
    id = "LLM-023"
    title = "Excessive Tool Definitions"
    category = "context"

    def check(self, ctx: AnalysisContext) -> Iterable[Finding]:
        cfg = ctx.config
        # only project-level MCP config (root .mcp.json) is known to be active; plugin copies may be disabled
        has_mcp = any(n.attrs.get("mcp_server") and n.location and "/" not in (n.location.file or "/") for n in ctx.ir.of_kind(NodeKind.TOOL))
        for step in ctx.ir.llm_steps():
            if skip_step(step):
                continue
            # Claude Code: an explicit list of built-in tools *restricts* the default set; only MCP tools add schemas
            n = step.attrs.get("tools_count") if step.framework != "claude_code" else sum(1 for t in step.tool_names if t.lower().startswith("mcp__"))
            tok = int(step.attrs.get("tools_tokens") or 0)
            b = Builder()
            if isinstance(n, int) and n >= cfg.tool_count_warn:
                text = step.static_text().lower()
                mentioned = [t for t in step.tool_names if t and t != "?" and t.lower() in text]
                b.pro("ir", f"{n} tool definitions sent with every request (~{tok} tokens of schemas)", 0.45 if n >= 30 else 0.35, step.location)
                if len(mentioned) <= 3:
                    b.pro("prompt_text", f"instructions reference only {len(mentioned)} of them: {mentioned[:5]}", 0.2)
            elif tok >= cfg.tool_tokens_warn:
                b.pro("ir", f"~{tok} tokens of tool schemas per request", 0.4, step.location)
            elif step.framework == "claude_code" and step.attrs.get("tools_inherited") and has_mcp and step.attrs.get("cc_type") == "agent":
                b.pro("ir", "subagent omits `tools`, so it inherits every tool including all configured MCP servers", 0.3, step.location)
            if not b.evidence:
                continue
            f = finding(
                self, ctx, step, b, CLASS_C, severity=severity_for(ctx, step, Severity.LOW),
                reasoning=("Tool definitions are input tokens on every request; per official Anthropic docs, selection accuracy also "
                           "degrades past ~30–50 tools."),
                current="Large tool set attached to a step whose instructions use few tools.",
                change="Attach only the tools this step uses, or defer rarely used tools (tool search / defer_loading where supported).",
                risk=Risk.LOW, risks=["A removed tool may be needed for rare paths; check tool-usage traces."],
                validation="From traces: histogram of tools actually called; A/B task success with the reduced set.",
                requires_runtime=True,
            )
            if f:
                f.impact.static_potential = potential(ctx, step, 0.0, tok or None)
                yield f
