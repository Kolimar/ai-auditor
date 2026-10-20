---
description: Review an interrupt handler for latency and safety
argument-hint: <handler name or file>
---

Review the interrupt service routine given in $ARGUMENTS. Check worst-case execution time against our 20 us budget, use of non-ISR-safe API calls, shared state access without proper atomicity, and whether work should be deferred to a task. Explain trade-offs, not just rule violations.
