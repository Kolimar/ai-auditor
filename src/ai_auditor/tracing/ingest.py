"""Trace ingestion: auditor JSONL, flattened OTel attributes, and OTLP-JSON exports.

Each importer declares the token semantics it reads and normalizes to disjoint buckets (schema.Usage).
Unknown values stay ``None``; nothing is inferred silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from ai_auditor.tracing.schema import Span, Usage
from ai_auditor.tracing.stats import RuntimeStats, compute_stats

ALIASES: dict[str, tuple[str, ...]] = {
    "provider": ("gen_ai.provider.name", "gen_ai.system", "llm.provider", "ls_provider"),
    "model": ("gen_ai.response.model", "gen_ai.request.model", "llm.model_name", "ls_model_name", "model"),
    "agent": ("gen_ai.agent.name",),
    "operation": ("gen_ai.operation.name",),
    "input_total": ("gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens", "llm.token_count.prompt"),
    "output": ("gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens", "llm.token_count.completion"),
    "cache_read": ("gen_ai.usage.cache_read.input_tokens", "gen_ai.usage.cache_read_input_tokens",
                   "llm.token_count.prompt_details.cache_read"),
    "cache_write": ("gen_ai.usage.cache_write.input_tokens", "gen_ai.usage.cache_creation_input_tokens",
                    "llm.token_count.prompt_details.cache_write"),
    "reasoning": ("gen_ai.usage.reasoning.output_tokens", "llm.token_count.completion_details.reasoning"),
    "error": ("error.type",),
    "component": ("auditor.component",),
    "workflow": ("auditor.workflow",),
    "cost": ("auditor.cost.usd", "llm.cost.total"),
}


def _first(attrs: dict[str, Any], key: str) -> Any:
    for k in ALIASES[key]:
        if k in attrs and attrs[k] is not None:
            return attrs[k]
    return None


def _int(v: Any) -> int | None:
    try:
        return None if v is None else int(v)
    except (TypeError, ValueError):
        return None


def usage_from_otel(attrs: dict[str, Any]) -> Usage:
    """OTel GenAI: input_tokens is the TOTAL input; cache read/write are subsets of it."""
    total = _int(_first(attrs, "input_total"))
    cr = _int(_first(attrs, "cache_read")) or 0
    cw = _int(_first(attrs, "cache_write")) or 0
    u = Usage(output=_int(_first(attrs, "output")), reasoning=_int(_first(attrs, "reasoning")) or 0, semantics="otel_total",
              cache_read=cr, cache_write=cw)
    if attrs.get("auditor.usage.input_excludes_cache"):  # producer declared Anthropic-native numbers
        u.uncached_input, u.semantics = total, "anthropic_native"
    elif total is not None:
        u.uncached_input = total - cr - cw
        if u.uncached_input < 0:  # numbers were clearly not "total including cache"
            u.uncached_input = total
            u.semantics = "ambiguous"
            u.notes.append("input_tokens smaller than cache subtotals: treated as excluding cache")
    return u


def usage_from_native(provider: str | None, usage: dict[str, Any]) -> Usage:
    """Provider-native usage objects as returned by the SDKs."""
    p = (provider or "").lower()
    if {"uncached_input", "cache_read", "cache_write"} & set(usage):  # the auditor's own disjoint shape wins
        return Usage(uncached_input=_int(usage.get("uncached_input")), cache_read=_int(usage.get("cache_read")) or 0,
                     cache_write=_int(usage.get("cache_write")) or 0, output=_int(usage.get("output")),
                     reasoning=_int(usage.get("reasoning")) or 0, semantics="disjoint")
    if "anthropic" in p or "cache_creation_input_tokens" in usage or "cache_read_input_tokens" in usage:
        return Usage(uncached_input=_int(usage.get("input_tokens")), cache_read=_int(usage.get("cache_read_input_tokens")) or 0,
                     cache_write=_int(usage.get("cache_creation_input_tokens")) or 0, output=_int(usage.get("output_tokens")),
                     semantics="anthropic_native")
    if "prompt_tokens" in usage or "input_tokens_details" in usage or "prompt_tokens_details" in usage or "openai" in p:
        total = _int(usage.get("prompt_tokens", usage.get("input_tokens")))
        details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        cr = _int(details.get("cached_tokens")) or 0
        cw = _int(details.get("cache_write_tokens")) or 0
        out_details = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
        return Usage(uncached_input=None if total is None else max(0, total - cr - cw), cache_read=cr, cache_write=cw,
                     output=_int(usage.get("completion_tokens", usage.get("output_tokens"))),
                     reasoning=_int(out_details.get("reasoning_tokens")) or 0, semantics="openai_native")
    if "promptTokenCount" in usage or "prompt_token_count" in usage:  # Gemini usage_metadata: prompt includes cached
        total = _int(usage.get("promptTokenCount", usage.get("prompt_token_count")))
        cr = _int(usage.get("cachedContentTokenCount", usage.get("cached_content_token_count"))) or 0
        out = _int(usage.get("candidatesTokenCount", usage.get("candidates_token_count")))
        th = _int(usage.get("thoughtsTokenCount", usage.get("thoughts_token_count"))) or 0
        return Usage(uncached_input=None if total is None else total - cr, cache_read=cr, output=None if out is None else out + th,
                     reasoning=th, semantics="google_native")
    if "input_tokens" in usage and not ({"uncached_input", "cache_read", "cache_write"} & set(usage)):
        # generic {input_tokens, output_tokens} with no cache fields: Anthropic and OpenAI semantics coincide when no
        # cache is reported; priced as uncached (an upper bound if the provider cached silently), and said so.
        return Usage(uncached_input=_int(usage.get("input_tokens")), output=_int(usage.get("output_tokens")),
                     semantics="no_cache_info", notes=["no cache fields reported: all input priced as uncached (upper bound)"])
    return Usage(uncached_input=_int(usage.get("uncached_input")), cache_read=_int(usage.get("cache_read")) or 0,
                 cache_write=_int(usage.get("cache_write")) or 0, output=_int(usage.get("output")),
                 reasoning=_int(usage.get("reasoning")) or 0, semantics="disjoint")


def span_from_record(rec: dict[str, Any], source: str) -> Span:
    """One JSONL record: either our own shape ({trace_id, component, usage: {...}}) or flattened OTel attributes."""
    attrs = dict(rec.get("attributes") or {})
    attrs.update({k: v for k, v in rec.items() if "." in k})
    provider = rec.get("provider") or _first(attrs, "provider")
    if isinstance(rec.get("usage"), dict):
        usage = usage_from_native(provider, rec["usage"])
    else:
        usage = usage_from_otel(attrs)
    return Span(
        trace_id=str(rec.get("trace_id") or rec.get("traceId") or attrs.get("auditor.execution.id") or "unknown"),
        span_id=str(rec.get("span_id") or rec.get("spanId") or id(rec)),
        parent_id=rec.get("parent_id") or rec.get("parentSpanId") or None,
        workflow=rec.get("workflow") or _first(attrs, "workflow"),
        component=rec.get("component") or _first(attrs, "component"),
        agent=rec.get("agent") or _first(attrs, "agent"),
        operation=rec.get("operation") or _first(attrs, "operation"),
        provider=provider,
        model=rec.get("model") or _first(attrs, "model"),
        usage=usage,
        latency_ms=_latency(rec),
        start_ms=_start(rec),
        tool_calls=int(rec.get("tool_calls") or attrs.get("auditor.tool_calls") or 0),
        retry_count=int(rec.get("retry_count") or attrs.get("auditor.retry.attempt") or 0),
        error=rec.get("error") or _first(attrs, "error"),
        cost_usd=_float(rec.get("cost_usd", _first(attrs, "cost"))),
        quality=_float(rec.get("quality", attrs.get("auditor.quality.score"))),
        validation_passed=rec.get("validation_passed", attrs.get("auditor.validation.passed")),
        batch=bool(rec.get("batch") or attrs.get("auditor.batch")),
        input_hash=rec.get("input_hash") or attrs.get("auditor.input.hash"),
        prompt_hash=rec.get("prompt_hash") or attrs.get("auditor.prompt.hash"),
        output_hash=rec.get("output_hash") or attrs.get("auditor.output.hash"),
        input_value=rec.get("input_value", attrs.get("auditor.input.value")),
        output_value=rec.get("output_value", attrs.get("auditor.output.value")),
        synthetic=bool(rec.get("synthetic") or attrs.get("auditor.synthetic")),
        source=source,
        attrs=attrs,
    )


def _float(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _latency(rec: dict[str, Any]) -> float | None:
    if rec.get("latency_ms") is not None:
        return float(rec["latency_ms"])
    s, e = rec.get("startTimeUnixNano"), rec.get("endTimeUnixNano")
    if s and e:
        return (int(e) - int(s)) / 1e6
    return None


def _start(rec: dict[str, Any]) -> float | None:
    if rec.get("start_ms") is not None:
        return float(rec["start_ms"])
    if rec.get("startTimeUnixNano"):
        return int(rec["startTimeUnixNano"]) / 1e6
    return None


def _otlp_value(v: dict[str, Any]) -> Any:
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return int(v[k]) if k == "intValue" else v[k]
    if "arrayValue" in v:
        return [_otlp_value(x) for x in v["arrayValue"].get("values", [])]
    return None


def iter_otlp(doc: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """OTLP-JSON export (resourceSpans/scopeSpans/spans) -> flat records."""
    for rs in doc.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for sp in ss.get("spans", []):
                rec = {k: sp.get(k) for k in ("traceId", "spanId", "parentSpanId", "startTimeUnixNano", "endTimeUnixNano")}
                rec["attributes"] = {a["key"]: _otlp_value(a.get("value", {})) for a in sp.get("attributes", [])}
                rec["name"] = sp.get("name")
                yield rec


def read_spans(path: Path) -> list[Span]:
    files: Iterable[Path] = sorted(path.rglob("*")) if path.is_dir() else [path]
    spans: list[Span] = []
    for f in files:
        if f.suffix not in (".jsonl", ".json") or not f.is_file():
            continue
        text = f.read_text()
        if f.suffix == ".json":
            doc = json.loads(text)
            spans += [span_from_record(r, "otlp_json") for r in iter_otlp(doc)]
            continue
        for line in text.splitlines():
            if line.strip():
                rec = json.loads(line)
                spans.append(span_from_record(rec, "jsonl"))
    return spans


def load_runtime(path: Path, prices=None) -> RuntimeStats:
    return compute_stats(read_spans(path), prices)
