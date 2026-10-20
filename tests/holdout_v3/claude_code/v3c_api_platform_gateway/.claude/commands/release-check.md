---
description: Run the standard pre-release checks
allowed-tools: Bash
---

Execute these in sequence and stop at the first failure:

```
git fetch origin --tags
make lint-spec
make contract-test
make sdk-build
```

Then print which step failed, or "all green".
