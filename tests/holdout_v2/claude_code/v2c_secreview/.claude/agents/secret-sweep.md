---
name: secret-sweep
description: Scans a repository for committed secrets and prepares a summary.
tools: Bash
model: opus
---
Always run these in order and do not skip any: first `gitleaks detect --source . --report-format json --report-path /tmp/gl.json`, then `trufflehog filesystem . --json > /tmp/th.json`, then `wc -l /tmp/gl.json /tmp/th.json`. After the third command, print the three outputs.
