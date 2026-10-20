---
description: Security-check the diff of a branch
argument-hint: <branch>
allowed-tools: Bash(git diff:*), Read, Grep
---
Look at `git diff main...$ARGUMENTS`. For each changed hunk, consider whether it introduces a vulnerability (injection, authorization bypass, secret exposure, unsafe deserialization, insecure defaults). Report only issues you can justify from the code, with file and line.
