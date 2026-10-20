# Public API platform

Monorepo for the public REST API (v1, v2), the gateway, and the SDK generators.

- `spec/openapi.yaml` is the source of truth; handlers are generated from it.
- Services: `services/gateway` (Go), `services/billing` (Go), `sdk/` (TypeScript, Python, Java generated).
- Before proposing any change to a public endpoint, check whether it is a breaking change under `docs/compat-policy.md`.
- Run `make lint-spec` and `make contract-test` before every PR.
- Production secrets never appear in the repo; use the names in `config/env.example`.
