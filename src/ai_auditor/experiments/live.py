"""Live model calls for experiments: opt-in, budget-capped, never used by default.

Only instantiated by ``ai-auditor experiment run --allow-live --budget-usd X``. The budget is checked BEFORE each call
with a conservative estimate (prompt tokens × input price + max_tokens × output price); the run stops when the next
call could exceed it. Actual cost is computed from the usage the provider returns.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ai_auditor.cost.pricing import PriceTable
from ai_auditor.parser.tokens import count_tokens
from ai_auditor.tracing.ingest import usage_from_native


class BudgetExceeded(RuntimeError):
    pass


class LiveRunner:
    def __init__(self, budget_usd: float, prices: PriceTable | None = None) -> None:
        if budget_usd <= 0:
            raise ValueError("a positive --budget-usd is required for live experiments")
        self.budget = budget_usd
        self.prices = prices or PriceTable.load()
        self.spent_usd = 0.0
        self.calls = 0
        self._clients: dict[str, Any] = {}

    def _client(self, provider: str):
        if provider not in self._clients:
            if provider == "anthropic":
                import anthropic  # noqa: PLC0415 - optional dependency, only for live runs

                self._clients[provider] = anthropic.Anthropic()
            elif provider == "openai":
                import openai  # noqa: PLC0415

                self._clients[provider] = openai.OpenAI()
            else:
                raise ValueError(f"live provider {provider!r} not supported (anthropic, openai)")
        return self._clients[provider]

    def run(self, side: dict[str, Any], item: Any) -> tuple[Any, float, float | None, int]:
        model, provider = side["model"], side.get("provider", "anthropic")
        prompt = side["prompt"].format(input=item if isinstance(item, str) else json.dumps(item, ensure_ascii=False))
        max_tokens = int(side.get("max_tokens", 256))
        est_prompt = int(count_tokens(prompt) * 1.3)  # pessimistic: the token count is approximate
        price = self.prices.get(model, est_prompt)  # tiered prices depend on the prompt size
        if price is None or price.input is None or price.output is None:
            raise ValueError(f"no price for {model}: cannot enforce the budget")
        worst = (est_prompt * price.input + max_tokens * price.output) / 1e6
        if self.spent_usd + worst > self.budget:
            raise BudgetExceeded(f"next call could exceed the budget (${self.spent_usd:.4f} spent of ${self.budget:.2f})")
        t0 = time.perf_counter()
        try:
            if provider == "anthropic":
                resp = self._client(provider).messages.create(model=model, max_tokens=max_tokens, temperature=side.get("temperature", 0),
                                                              messages=[{"role": "user", "content": prompt}])
                text = "".join(getattr(b, "text", "") for b in resp.content)
                usage = resp.usage.model_dump()
            else:
                resp = self._client(provider).chat.completions.create(model=model, max_completion_tokens=max_tokens,
                                                                       messages=[{"role": "user", "content": prompt}])
                text = resp.choices[0].message.content or ""
                usage = resp.usage.model_dump()
        except BudgetExceeded:
            raise
        except Exception:  # noqa: BLE001 - provider error counts as a reliability failure
            self.spent_usd += worst  # a failed call may still be billed: charge the worst case against the budget
            self.calls += 1
            return "__error__", (time.perf_counter() - t0) * 1000, None, 1
        latency = (time.perf_counter() - t0) * 1000
        u = usage_from_native(provider, usage)
        price = self.prices.get(model, u.total_input) or price
        cost = ((u.uncached_input or 0) * price.input + u.cache_read * (price.cache_read or price.input)
                + u.cache_write * (price.cache_write or price.input) + (u.output or 0) * price.output) / 1e6
        self.spent_usd += cost
        self.calls += 1
        parse = side.get("parse", "text")
        out: Any = text.strip()
        if parse == "json":
            try:
                out = json.loads(out)
            except json.JSONDecodeError:
                out = "__error__"
        return out, latency, cost, 0
