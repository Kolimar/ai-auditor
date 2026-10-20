---
name: release-checklist
description: Walks a maintainer through cutting a release of pytoolkit, from deciding the version number to publishing on PyPI.
allowed-tools: Read, Grep, Bash
---
# Cutting a release

1. Find the last tag and list merged PRs since then.
2. Decide the semantic version bump. Read each PR: anything that changes behavior of an exported function, removes a parameter or changes defaults is breaking, even if the PR title says "fix". When unsure, ask the maintainer.
3. Check that the docs mention every new public symbol and that deprecations announced two releases ago are actually removed.
4. Run `pytest -q` and `mypy src`; if something fails, investigate whether it is a flaky test (the timing tests are known to flake on CI) or a real regression before continuing.
5. Update the changelog and version, open the release PR.
6. After merge, tag and build: `python -m build`, `twine check dist/*`.
7. Ask for confirmation before `twine upload`. Never upload without it.
8. Draft the release announcement and post-release follow-ups (docs redirects, issue milestones).
