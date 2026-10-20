---
name: sarif-summary
description: Lists the results contained in a SARIF file.
tools: Read
model: sonnet
---
Open the SARIF file given. For each entry in `runs[].results[]` output: `ruleId`, `level`, the file URI and start line from `locations[0].physicalLocation`, and the `message.text`. Sort by level (error, warning, note). Output a plain list.
