---
description: Turn the Unity host-test output into a Markdown table
allowed-tools: Read
---

Read `build/test.log`. Each test result is a line in the Unity format `file:line:test_name:PASS` or `file:line:test_name:FAIL: message`. Convert the log into a Markdown table with columns test, file, result and message, with failures listed first.
