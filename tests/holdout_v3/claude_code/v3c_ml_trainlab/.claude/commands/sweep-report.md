---
description: Summarize a hyperparameter sweep and recommend what to try next
argument-hint: <sweep id>
allowed-tools: Read, Grep, Bash(python -m trainlab.inspect:*)
---
Look at all runs of sweep $ARGUMENTS under `runs/`. Describe which hyperparameters mattered, which interactions you can see, and recommend the next three configurations to try, justifying each.
