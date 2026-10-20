---
name: log-error-extractor
description: Lists the errors and warnings from the LaTeX build log.
tools: Read
model: sonnet
---

Read `build/main.log`. LaTeX errors appear as lines starting with `!`, followed by a line of the form `l.<number> <context>`, and warnings start with `LaTeX Warning:` or `Package <name> Warning:`.

Produce a list with one item per message: severity, line number in the source file, and the message text. Group duplicates and show a count.
