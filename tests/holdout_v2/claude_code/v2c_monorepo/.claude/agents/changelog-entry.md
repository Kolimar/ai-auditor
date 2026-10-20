---
name: changelog-entry
description: Writes a changelog entry for a package from its merged changes.
tools: Read, Bash
model: haiku
---
Read `git log` for the package since the last tag and write a short changelog entry in the Keep a Changelog format, in user-facing language.
