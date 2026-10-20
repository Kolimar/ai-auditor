---
description: Triage a GitHub issue reported by an API consumer
argument-hint: <issue number>
allowed-tools: Read, Grep, mcp__github__get_issue
---

Fetch issue $ARGUMENTS and work out what the reporter is actually experiencing. Check whether it is a bug in our API, a misunderstanding of the docs, a client bug, or a missing feature. Look through the spec and handlers for the relevant behavior. Propose a labeled classification, a suggested reply, and an internal action if there is one.
