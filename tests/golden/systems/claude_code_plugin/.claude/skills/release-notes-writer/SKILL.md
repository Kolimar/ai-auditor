---
name: release-notes-writer
description: Write customer-facing release notes from merged PRs and commits. Use when preparing a release.
---

# Release notes writer

Read the merged PR titles and descriptions since the last tag. Write release notes for customers, not engineers:

- Lead with the two or three changes users will care about most, explained in terms of what they can now do.
- Group the rest under "Improvements" and "Fixes" with one plain sentence each.
- Translate internal jargon and ticket IDs into user language; omit purely internal refactors.
- Keep the tone confident and specific, with no marketing filler.

If a change's user impact is unclear from the PR, ask the author instead of guessing.
