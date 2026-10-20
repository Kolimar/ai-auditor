---
description: Review a component for API design and consistency
argument-hint: <ComponentName> [focus area]
---

Review the component named in $ARGUMENTS in `packages/core/src`. Consider whether its props API is consistent with sibling components, whether the defaults are safe, whether the naming matches our glossary, and whether the story coverage is honest about edge cases. If a focus area is given after the name, weigh it more heavily. Point out anything that would be painful to change after release since consumers will depend on it.
