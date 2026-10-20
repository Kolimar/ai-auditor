"""Minimal, dependency-free instrumentation that writes auditor JSONL spans.

    from ai_auditor.tracing.sdk import Tracer
    tracer = Tracer("traces/run.jsonl", workflow="support")
    with tracer.execution():                       # one trace_id per workflow execution
        with tracer.step("classify_ticket", input_value=ticket) as span:
            resp = client.messages.create(...)
            span.record(resp, output_value=label)   # reads usage/model from Anthropic/OpenAI/Gemini responses

Prompts and outputs are stored only as hashes unless ``input_value``/``output_value`` are passed explicitly
(opt-in, needed for distillation). Nothing is sent anywhere: spans are appended to a local file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterator


def _hash(value: Any) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _get(obj: Any, *path: str) -> Any:
    for p in path:
        if obj is None:
            return None
        obj = obj.get(p) if isinstance(obj, dict) else getattr(obj, p, None)
    return obj


def _usage_dict(resp: Any) -> dict[str, Any] | None:
    for attr in ("usage", "usage_metadata"):
        u = _get(resp, attr)
        if u is None:
            continue
        if isinstance(u, dict):
            return u
        for m in ("model_dump", "to_dict", "dict"):
            if hasattr(u, m):
                try:
                    return getattr(u, m)()
                except TypeError:
                    continue
        return {k: v for k, v in vars(u).items() if not k.startswith("_")}
    return None


class SpanRecorder:
    def __init__(self, tracer: Tracer, component: str, **fields: Any) -> None:
        self.tracer = tracer
        self.rec: dict[str, Any] = {"trace_id": tracer.trace_id, "span_id": uuid.uuid4().hex[:16], "workflow": tracer.workflow,
                                    "component": component, **{k: v for k, v in fields.items() if v is not None}}
        if "input_value" in fields:
            self.rec["input_hash"] = _hash(fields["input_value"])
            if not tracer.store_values:
                self.rec.pop("input_value", None)

    def record(self, response: Any = None, *, output_value: Any = None, prompt: Any = None, **extra: Any) -> None:
        if response is not None:
            self.rec.setdefault("model", _get(response, "model") or _get(response, "model_version"))
            usage = _usage_dict(response)
            if usage is not None:
                self.rec["usage"] = usage
        if prompt is not None:
            self.rec["prompt_hash"] = _hash(prompt)
        if output_value is not None:
            self.rec["output_hash"] = _hash(output_value)
            if self.tracer.store_values:
                self.rec["output_value"] = output_value
        self.rec.update(extra)


class Tracer:
    def __init__(self, path: str | Path, workflow: str | None = None, store_values: bool = False) -> None:
        self.path = Path(path)
        self.workflow = workflow
        self.store_values = store_values
        self._local = threading.local()
        self._lock = threading.Lock()

    @property
    def trace_id(self) -> str:
        tid = getattr(self._local, "trace_id", None)
        if tid is None:
            tid = self._local.trace_id = uuid.uuid4().hex
        return tid

    @contextlib.contextmanager
    def execution(self) -> Iterator[str]:
        self._local.trace_id = uuid.uuid4().hex
        try:
            yield self._local.trace_id
        finally:
            self._local.trace_id = None

    @contextlib.contextmanager
    def step(self, component: str, **fields: Any) -> Iterator[SpanRecorder]:
        span = SpanRecorder(self, component, **fields)
        start = time.time()
        try:
            yield span
        except Exception as exc:
            span.rec["error"] = type(exc).__name__
            raise
        finally:
            span.rec["start_ms"] = start * 1000
            span.rec["latency_ms"] = (time.time() - start) * 1000
            self._write(span.rec)

    def _write(self, rec: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(rec, default=str, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
