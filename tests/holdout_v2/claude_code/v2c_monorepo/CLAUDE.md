# Orbit monorepo

TypeScript and Go services managed with pnpm workspaces and Bazel. Read this whole file before changing anything.

## General rules
- Every package has its own README; keep it current.
- Do not add dependencies without checking the allowlist in `tools/deps/allowed.json`.
- Tests live next to the code in `__tests__` or `_test.go` files.
- Conventional commits, scope is the package name.
- Never import across package boundaries except through the package's public `index.ts`.

## packages/auth

Language: Go. Owners: team-auth.

The auth package exposes its API in `packages/auth/src/index`. Run its tests with `pnpm --filter @orbit/auth test` or `go test ./packages/auth/...`.

Conventions: errors in auth are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/auth/config/default.json` and overridden by environment variables prefixed `ORBIT_AUTH_`. Logging uses the shared logger with the field `component=auth`. Feature flags for this package are named `auth.*` and defined in `tools/flags/auth.yaml`.

Known gotchas: the auth integration tests need `docker compose up auth-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/auth test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/auth.md`.

Deployment: auth is released independently through the pipeline in `.ci/auth.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/auth/migrations` must be backward compatible for one release.

## packages/billing

Language: TypeScript. Owners: team-billing.

The billing package exposes its API in `packages/billing/src/index`. Run its tests with `pnpm --filter @orbit/billing test` and its typecheck with `pnpm --filter @orbit/billing tsc --noEmit`.

Conventions: errors in billing are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/billing/config/default.json` and overridden by environment variables prefixed `ORBIT_BILLING_`. Logging uses the shared logger with the field `component=billing`. Feature flags for this package are named `billing.*` and defined in `tools/flags/billing.yaml`.

Known gotchas: the billing integration tests need `docker compose up billing-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/billing test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/billing.md`.

Deployment: billing is released independently through the pipeline in `.ci/billing.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/billing/migrations` must be backward compatible for one release.

## packages/catalog

Language: TypeScript. Owners: team-catalog.

The catalog package exposes its API in `packages/catalog/src/index`. Run its tests with `pnpm --filter @orbit/catalog test` and its typecheck with `pnpm --filter @orbit/catalog tsc --noEmit`.

Conventions: errors in catalog are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/catalog/config/default.json` and overridden by environment variables prefixed `ORBIT_CATALOG_`. Logging uses the shared logger with the field `component=catalog`. Feature flags for this package are named `catalog.*` and defined in `tools/flags/catalog.yaml`.

Known gotchas: the catalog integration tests need `docker compose up catalog-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/catalog test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/catalog.md`.

Deployment: catalog is released independently through the pipeline in `.ci/catalog.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/catalog/migrations` must be backward compatible for one release.

## packages/checkout

Language: Go. Owners: team-checkout.

The checkout package exposes its API in `packages/checkout/src/index`. Run its tests with `pnpm --filter @orbit/checkout test` or `go test ./packages/checkout/...`.

Conventions: errors in checkout are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/checkout/config/default.json` and overridden by environment variables prefixed `ORBIT_CHECKOUT_`. Logging uses the shared logger with the field `component=checkout`. Feature flags for this package are named `checkout.*` and defined in `tools/flags/checkout.yaml`.

Known gotchas: the checkout integration tests need `docker compose up checkout-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/checkout test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/checkout.md`.

Deployment: checkout is released independently through the pipeline in `.ci/checkout.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/checkout/migrations` must be backward compatible for one release.

## packages/search

Language: TypeScript. Owners: team-search.

The search package exposes its API in `packages/search/src/index`. Run its tests with `pnpm --filter @orbit/search test` and its typecheck with `pnpm --filter @orbit/search tsc --noEmit`.

Conventions: errors in search are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/search/config/default.json` and overridden by environment variables prefixed `ORBIT_SEARCH_`. Logging uses the shared logger with the field `component=search`. Feature flags for this package are named `search.*` and defined in `tools/flags/search.yaml`.

Known gotchas: the search integration tests need `docker compose up search-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/search test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/search.md`.

Deployment: search is released independently through the pipeline in `.ci/search.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/search/migrations` must be backward compatible for one release.

## packages/notifications

Language: TypeScript. Owners: team-notifications.

The notifications package exposes its API in `packages/notifications/src/index`. Run its tests with `pnpm --filter @orbit/notifications test` and its typecheck with `pnpm --filter @orbit/notifications tsc --noEmit`.

Conventions: errors in notifications are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/notifications/config/default.json` and overridden by environment variables prefixed `ORBIT_NOTIFICATIONS_`. Logging uses the shared logger with the field `component=notifications`. Feature flags for this package are named `notifications.*` and defined in `tools/flags/notifications.yaml`.

Known gotchas: the notifications integration tests need `docker compose up notifications-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/notifications test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/notifications.md`.

Deployment: notifications is released independently through the pipeline in `.ci/notifications.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/notifications/migrations` must be backward compatible for one release.

## packages/inventory

Language: Go. Owners: team-inventory.

The inventory package exposes its API in `packages/inventory/src/index`. Run its tests with `pnpm --filter @orbit/inventory test` or `go test ./packages/inventory/...`.

Conventions: errors in inventory are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/inventory/config/default.json` and overridden by environment variables prefixed `ORBIT_INVENTORY_`. Logging uses the shared logger with the field `component=inventory`. Feature flags for this package are named `inventory.*` and defined in `tools/flags/inventory.yaml`.

Known gotchas: the inventory integration tests need `docker compose up inventory-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/inventory test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/inventory.md`.

Deployment: inventory is released independently through the pipeline in `.ci/inventory.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/inventory/migrations` must be backward compatible for one release.

## packages/shipping

Language: TypeScript. Owners: team-shipping.

The shipping package exposes its API in `packages/shipping/src/index`. Run its tests with `pnpm --filter @orbit/shipping test` and its typecheck with `pnpm --filter @orbit/shipping tsc --noEmit`.

Conventions: errors in shipping are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/shipping/config/default.json` and overridden by environment variables prefixed `ORBIT_SHIPPING_`. Logging uses the shared logger with the field `component=shipping`. Feature flags for this package are named `shipping.*` and defined in `tools/flags/shipping.yaml`.

Known gotchas: the shipping integration tests need `docker compose up shipping-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/shipping test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/shipping.md`.

Deployment: shipping is released independently through the pipeline in `.ci/shipping.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/shipping/migrations` must be backward compatible for one release.

## packages/reporting

Language: TypeScript. Owners: team-reporting.

The reporting package exposes its API in `packages/reporting/src/index`. Run its tests with `pnpm --filter @orbit/reporting test` and its typecheck with `pnpm --filter @orbit/reporting tsc --noEmit`.

Conventions: errors in reporting are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/reporting/config/default.json` and overridden by environment variables prefixed `ORBIT_REPORTING_`. Logging uses the shared logger with the field `component=reporting`. Feature flags for this package are named `reporting.*` and defined in `tools/flags/reporting.yaml`.

Known gotchas: the reporting integration tests need `docker compose up reporting-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/reporting test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/reporting.md`.

Deployment: reporting is released independently through the pipeline in `.ci/reporting.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/reporting/migrations` must be backward compatible for one release.

## packages/admin-ui

Language: Go. Owners: team-admin.

The admin-ui package exposes its API in `packages/admin-ui/src/index`. Run its tests with `pnpm --filter @orbit/admin-ui test` or `go test ./packages/admin-ui/...`.

Conventions: errors in admin-ui are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/admin-ui/config/default.json` and overridden by environment variables prefixed `ORBIT_ADMIN_UI_`. Logging uses the shared logger with the field `component=admin-ui`. Feature flags for this package are named `admin_ui.*` and defined in `tools/flags/admin-ui.yaml`.

Known gotchas: the admin-ui integration tests need `docker compose up admin-ui-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/admin-ui test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/admin-ui.md`.

Deployment: admin-ui is released independently through the pipeline in `.ci/admin-ui.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/admin-ui/migrations` must be backward compatible for one release.

## packages/storefront-ui

Language: TypeScript. Owners: team-storefront.

The storefront-ui package exposes its API in `packages/storefront-ui/src/index`. Run its tests with `pnpm --filter @orbit/storefront-ui test` and its typecheck with `pnpm --filter @orbit/storefront-ui tsc --noEmit`.

Conventions: errors in storefront-ui are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/storefront-ui/config/default.json` and overridden by environment variables prefixed `ORBIT_STOREFRONT_UI_`. Logging uses the shared logger with the field `component=storefront-ui`. Feature flags for this package are named `storefront_ui.*` and defined in `tools/flags/storefront-ui.yaml`.

Known gotchas: the storefront-ui integration tests need `docker compose up storefront-ui-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/storefront-ui test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/storefront-ui.md`.

Deployment: storefront-ui is released independently through the pipeline in `.ci/storefront-ui.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/storefront-ui/migrations` must be backward compatible for one release.

## packages/design-system

Language: TypeScript. Owners: team-design.

The design-system package exposes its API in `packages/design-system/src/index`. Run its tests with `pnpm --filter @orbit/design-system test` and its typecheck with `pnpm --filter @orbit/design-system tsc --noEmit`.

Conventions: errors in design-system are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/design-system/config/default.json` and overridden by environment variables prefixed `ORBIT_DESIGN_SYSTEM_`. Logging uses the shared logger with the field `component=design-system`. Feature flags for this package are named `design_system.*` and defined in `tools/flags/design-system.yaml`.

Known gotchas: the design-system integration tests need `docker compose up design-system-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/design-system test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/design-system.md`.

Deployment: design-system is released independently through the pipeline in `.ci/design-system.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/design-system/migrations` must be backward compatible for one release.

## packages/gateway

Language: Go. Owners: team-gateway.

The gateway package exposes its API in `packages/gateway/src/index`. Run its tests with `pnpm --filter @orbit/gateway test` or `go test ./packages/gateway/...`.

Conventions: errors in gateway are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/gateway/config/default.json` and overridden by environment variables prefixed `ORBIT_GATEWAY_`. Logging uses the shared logger with the field `component=gateway`. Feature flags for this package are named `gateway.*` and defined in `tools/flags/gateway.yaml`.

Known gotchas: the gateway integration tests need `docker compose up gateway-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/gateway test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/gateway.md`.

Deployment: gateway is released independently through the pipeline in `.ci/gateway.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/gateway/migrations` must be backward compatible for one release.

## packages/ledger

Language: TypeScript. Owners: team-ledger.

The ledger package exposes its API in `packages/ledger/src/index`. Run its tests with `pnpm --filter @orbit/ledger test` and its typecheck with `pnpm --filter @orbit/ledger tsc --noEmit`.

Conventions: errors in ledger are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/ledger/config/default.json` and overridden by environment variables prefixed `ORBIT_LEDGER_`. Logging uses the shared logger with the field `component=ledger`. Feature flags for this package are named `ledger.*` and defined in `tools/flags/ledger.yaml`.

Known gotchas: the ledger integration tests need `docker compose up ledger-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/ledger test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/ledger.md`.

Deployment: ledger is released independently through the pipeline in `.ci/ledger.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/ledger/migrations` must be backward compatible for one release.

## packages/identity

Language: TypeScript. Owners: team-identity.

The identity package exposes its API in `packages/identity/src/index`. Run its tests with `pnpm --filter @orbit/identity test` and its typecheck with `pnpm --filter @orbit/identity tsc --noEmit`.

Conventions: errors in identity are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/identity/config/default.json` and overridden by environment variables prefixed `ORBIT_IDENTITY_`. Logging uses the shared logger with the field `component=identity`. Feature flags for this package are named `identity.*` and defined in `tools/flags/identity.yaml`.

Known gotchas: the identity integration tests need `docker compose up identity-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/identity test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/identity.md`.

Deployment: identity is released independently through the pipeline in `.ci/identity.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/identity/migrations` must be backward compatible for one release.

## packages/pricing

Language: Go. Owners: team-pricing.

The pricing package exposes its API in `packages/pricing/src/index`. Run its tests with `pnpm --filter @orbit/pricing test` or `go test ./packages/pricing/...`.

Conventions: errors in pricing are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/pricing/config/default.json` and overridden by environment variables prefixed `ORBIT_PRICING_`. Logging uses the shared logger with the field `component=pricing`. Feature flags for this package are named `pricing.*` and defined in `tools/flags/pricing.yaml`.

Known gotchas: the pricing integration tests need `docker compose up pricing-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/pricing test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/pricing.md`.

Deployment: pricing is released independently through the pipeline in `.ci/pricing.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/pricing/migrations` must be backward compatible for one release.

## packages/promotions

Language: TypeScript. Owners: team-promotions.

The promotions package exposes its API in `packages/promotions/src/index`. Run its tests with `pnpm --filter @orbit/promotions test` and its typecheck with `pnpm --filter @orbit/promotions tsc --noEmit`.

Conventions: errors in promotions are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/promotions/config/default.json` and overridden by environment variables prefixed `ORBIT_PROMOTIONS_`. Logging uses the shared logger with the field `component=promotions`. Feature flags for this package are named `promotions.*` and defined in `tools/flags/promotions.yaml`.

Known gotchas: the promotions integration tests need `docker compose up promotions-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/promotions test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/promotions.md`.

Deployment: promotions is released independently through the pipeline in `.ci/promotions.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/promotions/migrations` must be backward compatible for one release.

## packages/recommendations

Language: TypeScript. Owners: team-recommendations.

The recommendations package exposes its API in `packages/recommendations/src/index`. Run its tests with `pnpm --filter @orbit/recommendations test` and its typecheck with `pnpm --filter @orbit/recommendations tsc --noEmit`.

Conventions: errors in recommendations are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/recommendations/config/default.json` and overridden by environment variables prefixed `ORBIT_RECOMMENDATIONS_`. Logging uses the shared logger with the field `component=recommendations`. Feature flags for this package are named `recommendations.*` and defined in `tools/flags/recommendations.yaml`.

Known gotchas: the recommendations integration tests need `docker compose up recommendations-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/recommendations test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/recommendations.md`.

Deployment: recommendations is released independently through the pipeline in `.ci/recommendations.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/recommendations/migrations` must be backward compatible for one release.

## packages/returns

Language: Go. Owners: team-returns.

The returns package exposes its API in `packages/returns/src/index`. Run its tests with `pnpm --filter @orbit/returns test` or `go test ./packages/returns/...`.

Conventions: errors in returns are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/returns/config/default.json` and overridden by environment variables prefixed `ORBIT_RETURNS_`. Logging uses the shared logger with the field `component=returns`. Feature flags for this package are named `returns.*` and defined in `tools/flags/returns.yaml`.

Known gotchas: the returns integration tests need `docker compose up returns-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/returns test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/returns.md`.

Deployment: returns is released independently through the pipeline in `.ci/returns.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/returns/migrations` must be backward compatible for one release.

## packages/tax

Language: TypeScript. Owners: team-tax.

The tax package exposes its API in `packages/tax/src/index`. Run its tests with `pnpm --filter @orbit/tax test` and its typecheck with `pnpm --filter @orbit/tax tsc --noEmit`.

Conventions: errors in tax are returned as typed results, never thrown across a service boundary. Configuration is read once at startup from `packages/tax/config/default.json` and overridden by environment variables prefixed `ORBIT_TAX_`. Logging uses the shared logger with the field `component=tax`. Feature flags for this package are named `tax.*` and defined in `tools/flags/tax.yaml`.

Known gotchas: the tax integration tests need `docker compose up tax-db` first; snapshots in `__snapshots__` must be regenerated with `pnpm --filter @orbit/tax test -u` after intentional output changes; the on-call runbook is in `docs/runbooks/tax.md`.

Deployment: tax is released independently through the pipeline in `.ci/tax.yml`. Rollbacks are done by redeploying the previous tag; database migrations in `packages/tax/migrations` must be backward compatible for one release.

