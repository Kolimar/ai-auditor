---
description: Report the bundle size of the core package
allowed-tools: Bash
---

Run `pnpm --filter core build`, then `pnpm --filter core exec size-limit --json`, then print the result as a table with the columns package, limit and actual size.
