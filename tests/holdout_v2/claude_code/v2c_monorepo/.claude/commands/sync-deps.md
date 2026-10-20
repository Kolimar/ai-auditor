---
description: Refresh lockfile and generated code
allowed-tools: Bash
---
Run `pnpm install --frozen-lockfile=false`, then `pnpm -r run codegen`, then `bazel run //tools:gazelle`, then `git status --short` and show me the result.
