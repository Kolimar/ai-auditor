---
name: changeset-validator
description: Validates changeset files in .changeset/ before a release PR is opened. Use when the user asks to check changesets.
allowed-tools: Read, Glob
---

# Changeset validator

For every `.changeset/*.md` file (except README.md) check the following and list each violation with the file name:

- The frontmatter exists and contains at least one entry.
- Every key is the name of a package that exists in `packages/*/package.json`.
- Every value is exactly one of `major`, `minor`, `patch`.
- The summary after the frontmatter is not empty and is at most 200 characters on the first line.
- No package appears twice in the same file.

Output `OK` if there are no violations, otherwise a bullet list.
