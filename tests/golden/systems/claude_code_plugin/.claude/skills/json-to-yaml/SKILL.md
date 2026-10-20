---
name: json-to-yaml
description: Convert a JSON file or snippet into YAML. Use when the user asks to turn JSON config into YAML.
---

# JSON to YAML

When the user gives a JSON file or snippet and wants YAML:

1. Read the JSON input.
2. Rewrite it as YAML: objects become mappings, arrays become sequences with `-`, two-space indentation.
3. Keep key order, keep strings quoted only when YAML requires it, and keep numbers and booleans as they are.
4. Write the result to the same path with a `.yaml` extension, or print it if the user supplied a snippet.

Do not change any values or add comments.
