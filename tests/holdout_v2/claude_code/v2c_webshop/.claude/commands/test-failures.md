---
description: Run a test target and explain why it fails
argument-hint: <test file or pattern>
allowed-tools: Bash(npm test:*), Read, Grep
---
Run `npm test -- $ARGUMENTS`. For every failing test, read the test and the code under test, and explain in plain language why it fails and what the smallest fix would be. Distinguish real regressions from flaky or environment-related failures.
