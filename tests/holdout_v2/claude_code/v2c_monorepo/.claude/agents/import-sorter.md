---
name: import-sorter
description: Sorts and groups import statements in the files that were modified.
tools: Read, Edit
model: opus
---
In each modified TypeScript file, order imports as: node builtins, external packages, `@orbit/*` packages, relative imports. Sort alphabetically within each group, separated by one blank line. Do not change anything else.
