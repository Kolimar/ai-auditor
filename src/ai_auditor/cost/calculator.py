"""Cost of one call from disjoint usage buckets and a versioned price table.

Never guesses: a missing price or missing usage makes the cost UNKNOWN (``usd=None``) with a reason.
Prices are USD per million tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_auditor.cost.pricing import PriceTable
from ai_auditor.tracing.schema import Span


@dataclass
class CostResult:
    usd: float | None
    status: str  # computed | provided | unknown
    reason: str = ""


def span_cost(span: Span, prices: PriceTable) -> CostResult:
    if span.cost_usd is not None:
        return CostResult(span.cost_usd, "provided", "cost reported by the trace producer")
    u = span.usage
    if u.uncached_input is None or u.output is None:
        return CostResult(None, "unknown", "usage incomplete in trace")
    price = prices.get(span.model, u.total_input)
    if price is None or price.input is None or price.output is None:
        return CostResult(None, "unknown", f"no price for model '{span.model}' in {prices.origin}")
    p_in = price.batch_input if span.batch and price.batch_input is not None else price.input
    p_out = price.batch_output if span.batch and price.batch_output is not None else price.output
    if u.cache_read and price.cache_read is None:
        return CostResult(None, "unknown", f"cache-read price unknown for '{span.model}'")
    if u.cache_write and price.cache_write is None:
        return CostResult(None, "unknown", f"cache-write price unknown for '{span.model}'")
    usd = (u.uncached_input * p_in + u.cache_read * (price.cache_read or 0) + u.cache_write * (price.cache_write or 0)
           + u.output * p_out) / 1e6
    return CostResult(usd, "computed", f"{price.model} @ {price.retrieved_at}")


def tokens_cost(prices: PriceTable, model: str | None, uncached: float, output: float, cache_read: float = 0,
                cache_write: float = 0, batch: bool = False) -> float | None:
    """Cost of ONE call with this token mix (the price tier depends on a single call's prompt size; never pass sums
    over many calls). None if any needed price is unknown."""
    price = prices.get(model, int(uncached + cache_read + cache_write))
    if price is None or price.input is None or price.output is None:
        return None
    p_in = price.batch_input if batch and price.batch_input is not None else price.input
    p_out = price.batch_output if batch and price.batch_output is not None else price.output
    if (cache_read and price.cache_read is None) or (cache_write and price.cache_write is None):
        return None
    return (uncached * p_in + cache_read * (price.cache_read or 0) + cache_write * (price.cache_write or 0) + output * p_out) / 1e6
