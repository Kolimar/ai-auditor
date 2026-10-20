---
name: generate-postman-collection
description: Converts spec/openapi.yaml into a Postman collection v2.1 JSON file.
allowed-tools: Read, Write
---

Read `spec/openapi.yaml` and write `dist/postman_collection.json`.

Mapping:
- each tag becomes a folder, named after the tag;
- each operation becomes a request inside its first tag's folder, named by `summary`;
- `servers[0].url` becomes the collection variable `baseUrl`;
- path parameters `{id}` become `:id` with an empty value;
- the request body example (or an empty object) is the raw JSON body;
- security scheme `bearerAuth` becomes collection-level bearer auth with variable `token`.

Do not add or drop operations.
