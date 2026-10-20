---
description: Triage a GitHub issue, suggest labels and next action
argument-hint: <issue number>
allowed-tools: Bash(gh issue view:*), Read, Grep
---
Fetch issue #$ARGUMENTS with `gh issue view`. Decide if it is reproducible from the description, find the code involved, and write a triage note: likely cause, severity, whether it is a good first issue, and a suggested reply to the reporter.
