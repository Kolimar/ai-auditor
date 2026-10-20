---
description: Draft release notes for a version from merged PRs
argument-hint: <version>
allowed-tools: Bash(gh pr list:*), Read
---
List the PRs merged since the previous tag with `gh pr list --state merged`. For release `$ARGUMENTS`, group the changes into Added, Changed, Fixed and Breaking, rewriting each PR title into a sentence a user would understand. Call out anything that needs a migration step.
