"""Synthetic trace generator for tests and demos.

Every span is marked ``synthetic: true``. The pipeline then refuses to treat these numbers as evidence (levels never
change) and the report labels all runtime figures as synthetic. Generation is deterministic for a given seed.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from ai_auditor.analyzers.engine import AnalysisContext


def generate(ctx: AnalysisContext, executions: int = 50, seed: int = 0, loop_items: int = 5) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []
    steps = [s for s in ctx.ir.llm_steps() if not s.attrs.get("dead_code") and not s.attrs.get("non_production")]
    for e in range(executions):
        tid = f"synthetic-{seed}-{e}"
        t = 1_700_000_000_000.0 + e * 60_000
        for step in steps:
            prof = ctx.profile(step)
            mult = ctx.graph.multiplicity(step.id)
            calls = loop_items if mult.in_loop else 1
            model = prof.model.id if prof.model else (step.model.raw or "unknown")
            for i in range(calls):
                variable = rng.randint(50, 600)
                out_tokens = {"closed": rng.randint(1, 5), "structured": rng.randint(30, 200)}.get(prof.output_space, rng.randint(150, 700))
                label = prof.labels[rng.randrange(len(prof.labels))] if prof.labels else None
                inp = f"{step.name}-input-{rng.randint(0, 40 if prof.output_space == 'closed' else 10_000)}"
                out.append({
                    "trace_id": tid, "span_id": f"{tid}-{step.id}-{i}", "component": step.name, "model": model,
                    "usage": {"uncached_input": prof.static_tokens + variable, "cache_read": 0, "cache_write": 0, "output": out_tokens},
                    "latency_ms": 300 + 4 * out_tokens + rng.random() * 200, "start_ms": t, "input_hash": inp,
                    "output_hash": f"{label or rng.random()}", "output_value": label, "synthetic": True,
                })
                t += 1500
    return out


def write(ctx: AnalysisContext, path: Path, **kw) -> int:
    spans = generate(ctx, **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(s) + "\n" for s in spans))
    return len(spans)
