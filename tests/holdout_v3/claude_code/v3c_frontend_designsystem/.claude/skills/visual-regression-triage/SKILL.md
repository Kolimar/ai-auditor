---
name: visual-regression-triage
description: Triage Chromatic visual regression failures on a PR. Use when the visual tests fail and the user wants to know which diffs are intentional and which are real regressions.
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), WebFetch
---

# Visual regression triage

Visual diffs have many causes and the snapshot tool cannot tell them apart. Your job is to decide, per story, whether the change is intended.

## Procedure

1. Get the list of changed stories from the Chromatic build (the user gives the URL or build number). Fetch the build summary and note each story ID with its diff percentage.
2. Look at `git diff origin/main...HEAD --stat` to learn which source files the PR touches. Map each changed story to the component it renders, including indirect dependencies such as shared tokens, icons, and layout primitives.
3. Classify each story:
   - **Expected**: the PR deliberately changes this component or a token it uses, and the diff matches the stated intent in the PR description or changeset.
   - **Collateral**: an indirect change (a token tweak, a shared helper) alters stories nobody intended to touch. Decide whether the new look is acceptable or an unintended side effect.
   - **Flaky**: animation timing, font loading, or date-dependent content. Look for repeated diffs across unrelated builds with `git log` on the story file.
   - **Regression**: the diff shows broken layout, clipped text, missing focus rings, wrong colors in dark mode.
4. For collateral and regression items, read the component code and explain the mechanism that produced the diff. Do not guess; if you cannot determine it, say so.
5. Write a short summary for the PR: which diffs to approve, which to fix, which to rerun. Be explicit about your confidence in each classification.

Think about theme and density variants: a diff that appears only in dark mode is frequently a missing token override, not a design decision.
