"""Provider-independent span model.

Field names follow the OpenTelemetry GenAI semantic conventions where one exists (``gen_ai.*``); auditor-specific
fields use the ``auditor.*`` prefix. Token usage is stored as DISJOINT buckets so cost can be computed without
double counting:

    uncached_input + cache_read + cache_write = total input
    output (includes reasoning tokens; ``reasoning`` is a subset kept for analysis)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Usage:
    uncached_input: int | None = None
    cache_read: int = 0
    cache_write: int = 0
    output: int | None = None
    reasoning: int = 0  # subset of output
    semantics: str = "unknown"  # where the numbers came from: otel_total | anthropic_native | openai_native | disjoint
    notes: list[str] = field(default_factory=list)

    @property
    def total_input(self) -> int | None:
        if self.uncached_input is None:
            return None
        return self.uncached_input + self.cache_read + self.cache_write


@dataclass
class Span:
    trace_id: str  # one execution of the workflow
    span_id: str
    parent_id: str | None = None
    workflow: str | None = None  # auditor.workflow
    component: str | None = None  # auditor.component: name of the IR step (function / agent / skill)
    agent: str | None = None  # gen_ai.agent.name
    operation: str | None = None  # gen_ai.operation.name: chat | invoke_agent | execute_tool | embeddings ...
    provider: str | None = None  # gen_ai.provider.name (legacy gen_ai.system)
    model: str | None = None  # gen_ai.response.model or gen_ai.request.model
    usage: Usage = field(default_factory=Usage)
    latency_ms: float | None = None
    start_ms: float | None = None
    tool_calls: int = 0
    retry_count: int = 0  # auditor.retry.attempt (0 = first attempt)
    error: str | None = None  # error.type
    cost_usd: float | None = None  # auditor.cost.usd if the producer computed it (OTel defines no cost attribute)
    quality: float | None = None  # auditor.quality.score in [0, 1], optional
    validation_passed: bool | None = None  # auditor.validation.passed, for validator steps
    batch: bool = False  # auditor.batch: request sent through a batch API
    input_hash: str | None = None  # auditor.input.hash: hash of the variable part of the prompt
    prompt_hash: str | None = None  # auditor.prompt.hash: hash of the full request
    output_hash: str | None = None  # auditor.output.hash
    input_value: Any = None  # auditor.input.value: structured input (opt-in, for distillation)
    output_value: Any = None  # auditor.output.value (opt-in)
    synthetic: bool = False  # auditor.synthetic: generated traces, never presented as observations
    source: str = "unknown"  # importer that produced this span
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def is_llm(self) -> bool:
        return self.operation in (None, "chat", "text_completion", "generate_content", "invoke_agent", "create_agent") and (
            self.model is not None or self.usage.output is not None)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
