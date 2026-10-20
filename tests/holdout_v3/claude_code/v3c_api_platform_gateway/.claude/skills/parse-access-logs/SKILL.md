---
name: parse-access-logs
description: Extracts status code, path and latency from gateway access logs and counts requests per path.
allowed-tools: Read, Bash
---

The gateway writes nginx combined-format lines extended with a trailing `rt=<seconds>` field, for example:

`10.2.3.4 - - [12/Mar/2026:10:11:12 +0000] "GET /v1/charges?limit=10 HTTP/1.1" 200 512 "-" "curl/8" rt=0.034`

For the log file the user names, read each line and extract the status code, the request path (without query string) and the `rt` value. Then report, per path, the number of requests, the number of 5xx responses and the p95 latency. Output a table sorted by request count.
