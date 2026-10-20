---
name: openapi-linter
description: Lints spec/openapi.yaml against the platform's API style rules.
tools: Read
model: sonnet
---

Check `spec/openapi.yaml` against these rules and list every violation with its JSON pointer:

1. Every path starts with `/v1` or `/v2`.
2. Every operation has an `operationId` in lowerCamelCase.
3. Every operation documents at least one 4xx response referencing `#/components/schemas/Error`.
4. Every list endpoint declares `limit` (integer, max 100) and `cursor` (string) query parameters.
5. Every schema property has a `description`.
6. No operation uses `x-internal: true` unless its path starts with `/v1/internal`.

If there are no violations print `lint clean`.
