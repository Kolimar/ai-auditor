---
description: Take a crash id and attempt a fix
argument-hint: <crashlytics issue id>
---
Fetch the crash report for `$ARGUMENTS` from `crashes/$ARGUMENTS.txt`, find the root cause in the code, make the smallest fix, and add a regression test when feasible. Explain the reasoning in the commit message.
