---
description: Triage a bug report and propose a likely root cause
argument-hint: <issue-number>
---

Read issue $ARGUMENTS with `gh issue view`. Reproduce the symptom from the description if possible, search the
codebase for the code paths involved, and form two or three hypotheses about the root cause ranked by likelihood.
For the most likely one, describe the smallest experiment that would confirm it and the shape of the fix.
