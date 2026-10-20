"""Command-line interface.

    ai-auditor analyze PATH [--traces DIR] [--format text|markdown|json|sarif] [--output FILE] [--min-level LEVEL]
    ai-auditor report PATH --review REVIEW.json   # check an agent's review against the files; final report
    ai-auditor ir PATH                 # dump the intermediate representation (JSON)
    ai-auditor graph PATH [--dot]      # workflow graph (Mermaid by default)
    ai-auditor rules                   # list registered rules
    ai-auditor benchmark [--split dev] # precision / recall / calibration on the labelled fixtures
    ai-auditor trace stats|synth PATH  # runtime statistics / clearly-labelled synthetic traces
    ai-auditor distill TRACES --component NAME   # learn deterministic rules from logged LLM decisions
    ai-auditor experiment run SPEC.yaml [--allow-live --budget-usd X]   # counterfactual ACCEPT/REJECT/INCONCLUSIVE
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_auditor import __version__


def _config(args: argparse.Namespace):
    from ai_auditor.config import AuditConfig

    root = Path(args.path)
    cfg = AuditConfig.load(root if root.is_dir() else root.parent, Path(args.config) if getattr(args, "config", None) else None)
    if getattr(args, "pricing", None):
        cfg.pricing_file = args.pricing
    if getattr(args, "min_level", None):
        cfg.min_level = args.min_level
    if getattr(args, "md_instructions", False):
        cfg.markdown_instructions = True
    return cfg


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"report written to {output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def cmd_analyze(args: argparse.Namespace) -> int:
    from ai_auditor.audit import audit, min_level_filter
    from ai_auditor.reporting.render import RENDERERS

    if args.for_agent and args.format == "sarif":
        from ai_auditor.config import UsageError  # noqa: PLC0415

        raise UsageError("--for-agent works with the text, markdown and json formats")
    cfg = _config(args)
    runtime = None
    if args.traces:
        from ai_auditor.tracing.ingest import load_runtime  # noqa: PLC0415  (optional stage)

        from ai_auditor.cost.pricing import PriceTable  # noqa: PLC0415

        runtime = load_runtime(Path(args.traces), PriceTable.load(Path(cfg.pricing_file) if cfg.pricing_file else None))
    only = set(args.rules.split(",")) if args.rules else None
    experiments = None
    if args.experiments:
        from ai_auditor.experiments.runner import load_results  # noqa: PLC0415

        experiments = load_results(Path(args.experiments))
    res = audit(Path(args.path), cfg, use_cache=not args.no_cache, runtime=runtime, only_rules=only, experiments=experiments)
    findings = min_level_filter(res.findings, cfg.min_level)
    out = RENDERERS[args.format](res, findings)
    if args.for_agent:
        from ai_auditor.reporting.agent_brief import build_brief, render_brief_markdown  # noqa: PLC0415

        brief = build_brief(res, findings)
        if args.format == "json":
            import json  # noqa: PLC0415

            data = json.loads(out)
            data["agent_brief"] = brief
            out = json.dumps(data, indent=2, ensure_ascii=False)
        else:
            out += render_brief_markdown(brief)
    _write(out, args.output)
    if args.fail_on:
        from ai_auditor.analyzers.finding import EvidenceLevel

        bar = EvidenceLevel[args.fail_on]
        if any(f.actionable and not f.superseded_by and f.level >= bar for f in findings):
            return 2
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from ai_auditor.audit import audit, min_level_filter
    from ai_auditor.reporting.review import load_review, render_report, report_json, verify_review
    from ai_auditor.reporting.workflow_map import build_map

    review = load_review(Path(args.review))
    cfg = _config(args)
    res = audit(Path(args.path), cfg, use_cache=not args.no_cache)
    findings = min_level_filter(res.findings, cfg.min_level)
    wmap = build_map(res)
    checked = verify_review(res, review, findings, wmap)
    _write((report_json if args.format == "json" else render_report)(res, findings, wmap, checked), args.output)
    bad = sum(1 for f in checked["findings"] if not f["verified"]) + len(checked["errors"])
    if bad:
        print(f"ai-auditor: {bad} item(s) of the review could not be verified: see 'Not verified'", file=sys.stderr)
    return 0


def cmd_ir(args: argparse.Namespace) -> int:
    from ai_auditor.ir.model import dumps
    from ai_auditor.parser.project import extract_project

    ir, _ = extract_project(Path(args.path), _config(args), use_cache=not args.no_cache)
    _write(dumps(ir), args.output)
    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    from ai_auditor.graph.workflow_graph import WorkflowGraph
    from ai_auditor.parser.project import extract_project

    ir, _ = extract_project(Path(args.path), _config(args), use_cache=not args.no_cache)
    g = WorkflowGraph(ir)
    _write(g.to_dot() if args.dot else g.to_mermaid(), args.output)
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    from ai_auditor.analyzers.engine import load_rules

    for rid, cls in load_rules().items():
        needs = ",".join(sorted(cls.needs))
        print(f"{rid}  {cls.title:<45} {cls.category:<16} needs={needs}  ({cls.__module__})")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from ai_auditor.evaluation.golden import render_benchmark, run_benchmark

    if args.split in ("holdout_v3", "all") and not args.confirm_holdout:
        print("holdout_v3 is measured once, at the end of the iteration (tests/holdout_v3/PREREGISTRATION.md); "
              "pass --confirm-holdout", file=sys.stderr)
        return 1
    results, agg = run_benchmark(Path(args.repo), args.split)
    if args.json:
        import json

        _write(json.dumps({"aggregate": agg, "fixtures": [r.__dict__ for r in results]}, indent=2, default=str), args.output)
    else:
        _write(render_benchmark(results, agg, args.split, verbose=not args.quiet), args.output)
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    if args.action == "stats":
        from ai_auditor.tracing.ingest import load_runtime

        rt = load_runtime(Path(args.path))
        lines = [f"executions {rt.n_executions} · spans {rt.n_spans} · sources {rt.sources} · unattributed {rt.unattributed_spans}",
                 f"total cost ${rt.total_cost_usd:.6f} (+ {rt.cost_unknown_calls} calls with UNKNOWN cost)"] + rt.notes + [""]
        for name, c in sorted(rt.components.items(), key=lambda kv: -kv[1].cost_usd):
            cpe = f"${c.cost_per_execution:.6f}" if c.cost_per_execution is not None else "UNKNOWN"
            lines.append(f"{name}: calls {c.calls} ({c.calls_per_execution:.2f}/exec where present) · cost/exec {cpe} · "
                         f"retries {c.retries} · errors {c.errors} · cache-read share {c.cache_read_share} · duplicates {c.duplicate_calls}")
        _write("\n".join(lines) + "\n", args.output)
        return 0
    # synth: generate clearly-labelled synthetic traces for a project (demo/testing)
    from ai_auditor.audit import audit
    from ai_auditor.tracing.synth import write

    res = audit(Path(args.path), use_cache=False)
    out = Path(args.output or "synthetic-traces.jsonl")
    n = write(res.ctx, out, executions=args.executions, seed=args.seed)
    print(f"wrote {n} SYNTHETIC spans to {out}", file=sys.stderr)
    return 0


def cmd_distill(args: argparse.Namespace) -> int:
    import json

    from ai_auditor.optimization.distill import distill, render
    from ai_auditor.tracing.ingest import read_spans

    spans = read_spans(Path(args.path))
    r = distill(spans, args.component, target_fidelity=args.target_fidelity, min_coverage=args.min_coverage,
                max_depth=args.max_depth)
    if args.json:
        d = {k: v for k, v in r.__dict__.items() if k != "tree"}
        d["candidates"] = {n: {"coverage": str(c.coverage), "fidelity": str(c.fidelity), "decision": c.decision,
                               "reasons": c.reasons} for n, c in r.candidates.items()}
        _write(json.dumps(d, indent=2, default=str) + "\n", args.output)
    else:
        _write(render(r) + "\n", args.output)
    if args.emit_python:
        if r.python_code is None:
            print("no code emitted: the tree candidate did not reach the fidelity/coverage bar", file=sys.stderr)
            return 1
        header = (f"# Distilled from {r.n_examples} logged decisions of '{r.component}' ({'SYNTHETIC traces' if r.synthetic else 'real traces'}).\n"
                  f"# Returns None when unsure: keep the LLM call as fallback for those inputs.\n"
                  f"# Tree candidate: coverage {r.candidates['tree'].coverage}; fidelity {r.candidates['tree'].fidelity}.\n\n")
        Path(args.emit_python).write_text(header + r.python_code, encoding="utf-8")
        print(f"python written to {args.emit_python}", file=sys.stderr)
    return 0


def cmd_experiment(args: argparse.Namespace) -> int:
    from ai_auditor.config import AuditConfig
    from ai_auditor.experiments.runner import ExperimentSpec, render, run_experiment, save

    spec = ExperimentSpec.load(Path(args.spec))
    cfg = AuditConfig.load(Path(args.spec).parent, Path(args.config) if args.config else None)
    live = None
    if args.allow_live:
        if not args.budget_usd:
            print("--allow-live requires --budget-usd", file=sys.stderr)
            return 1
        from ai_auditor.experiments.live import LiveRunner  # noqa: PLC0415

        live = LiveRunner(args.budget_usd)
    try:
        result = run_experiment(spec, cfg, live)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _write(render(result), args.output)
    if args.save:
        print(f"result saved to {save(result, Path(args.save))}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai-auditor", description="Find what in an AI system does not need an LLM.")
    p.add_argument("--version", action="version", version=f"ai-auditor {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path")
        sp.add_argument("--config")
        sp.add_argument("--output", "-o")
        sp.add_argument("--no-cache", action="store_true")
        sp.add_argument("--md-instructions", action="store_true",
                        help="read every .md file (except README, CHANGELOG...) as agent instructions: "
                             "a folder of playbooks or prompts exported from any tool")

    a = sub.add_parser("analyze", help="audit a project")
    common(a)
    a.add_argument("--traces", help="directory or file with runtime traces (JSONL / OTLP-JSON)")
    a.add_argument("--pricing", help="pricing YAML overriding the built-in table")
    a.add_argument("--experiments", help="directory with saved experiment results (experiment run --save DIR)")
    a.add_argument("--format", "-f", choices=["text", "markdown", "json", "sarif"], default="text")
    a.add_argument("--min-level", choices=["HYPOTHESIS", "LIKELY", "HIGH_CONFIDENCE", "PROVEN"])
    a.add_argument("--rules", help="comma-separated rule ids to run")
    a.add_argument("--fail-on", choices=["HYPOTHESIS", "LIKELY", "HIGH_CONFIDENCE", "PROVEN"],
                   help="exit 2 if a recommendation at or above this level exists (CI)")
    a.add_argument("--for-agent", action="store_true",
                   help="append a brief for the AI agent running the auditor: the steps the static analysis could "
                        "not settle and a rubric to review them with its own judgement")
    a.set_defaults(func=cmd_analyze)

    rp = sub.add_parser("report", help="check an agent's review (--for-agent answer, JSON) and render the final report")
    common(rp)
    rp.add_argument("--review", required=True, help="the agent's review as JSON (format in the --for-agent brief)")
    rp.add_argument("--format", "-f", choices=["markdown", "json"], default="markdown")
    rp.add_argument("--min-level", choices=["HYPOTHESIS", "LIKELY", "HIGH_CONFIDENCE", "PROVEN"])
    rp.set_defaults(func=cmd_report)

    i = sub.add_parser("ir", help="dump the intermediate representation")
    common(i)
    i.set_defaults(func=cmd_ir)

    g = sub.add_parser("graph", help="print the workflow graph")
    common(g)
    g.add_argument("--dot", action="store_true")
    g.set_defaults(func=cmd_graph)

    b = sub.add_parser("benchmark", help="precision/recall/calibration on the labelled fixtures")
    b.add_argument("--repo", default=".")
    b.add_argument("--split", choices=["dev", "holdout", "tuning", "holdout_v2", "holdout_v3", "all"], default="dev",
                   help="tuning = dev + holdout v1 + holdout v2 (all already inspected); holdout_v3 = unseen, measured once")
    b.add_argument("--confirm-holdout", action="store_true")
    b.add_argument("--json", action="store_true")
    b.add_argument("--quiet", action="store_true")
    b.add_argument("--output", "-o")
    b.set_defaults(func=cmd_benchmark)

    t = sub.add_parser("trace", help="runtime traces: stats | synth")
    t.add_argument("action", choices=["stats", "synth"])
    t.add_argument("path", help="traces file/dir (stats) or project (synth)")
    t.add_argument("--output", "-o")
    t.add_argument("--executions", type=int, default=50)
    t.add_argument("--seed", type=int, default=0)
    t.set_defaults(func=cmd_trace)

    d = sub.add_parser("distill", help="learn deterministic rules from logged LLM decisions (needs input/output values)")
    d.add_argument("path", help="traces file/dir")
    d.add_argument("--component", required=True)
    d.add_argument("--target-fidelity", type=float, default=0.95)
    d.add_argument("--min-coverage", type=float, default=0.5)
    d.add_argument("--max-depth", type=int, default=4)
    d.add_argument("--emit-python", help="write the distilled function to this file (only when the bar is met)")
    d.add_argument("--json", action="store_true")
    d.add_argument("--output", "-o")
    d.set_defaults(func=cmd_distill)

    e = sub.add_parser("experiment", help="run a counterfactual experiment (offline replay by default)")
    e.add_argument("action", choices=["run"])
    e.add_argument("spec", help="experiment YAML")
    e.add_argument("--config")
    e.add_argument("--save", help="directory to store the result for `analyze --experiments`")
    e.add_argument("--allow-live", action="store_true", help="allow candidate/baseline kind 'llm' (calls a model API)")
    e.add_argument("--budget-usd", type=float, help="hard spending cap for live calls")
    e.add_argument("--output", "-o")
    e.set_defaults(func=cmd_experiment)

    r = sub.add_parser("rules", help="list rules")
    r.set_defaults(func=cmd_rules)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = getattr(args, "path", None)
    if path is not None and not Path(path).exists():
        print(f"ai-auditor: error: path does not exist: {path}", file=sys.stderr)
        return 2
    from ai_auditor.config import UsageError

    try:
        return args.func(args)
    except UsageError as exc:  # invalid configuration / experiment spec / dataset; real bugs keep their traceback
        print(f"ai-auditor: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
