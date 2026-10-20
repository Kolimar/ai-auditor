# Meridian Commerce Platform

Monorepo for the Meridian order-management platform. Read this file fully before touching code. Everything below applies to every task.

## Stack
- Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Celery, Redis, PostgreSQL 16
- Frontend: React 18 + TypeScript in `web/`
- CI: GitHub Actions, required checks: lint, types, unit, integration

## Global conventions

1. Use type hints everywhere; `mypy --strict` must pass on `services/`.
2. Never import from another service's `internal` package; go through its `api` module.
3. Database changes always ship with an Alembic migration and a rollback test.
4. Money is `Decimal` with explicit currency; never `float`.
5. Log with structlog, never `print`. Include `request_id` in every log line.
6. Public endpoints require an explicit `scopes=[...]` declaration.
7. Feature flags live in `config/flags.yaml`; remove the flag within two releases of GA.
8. Tests use pytest; fixtures live next to the module under `tests/`.
9. Commit messages follow Conventional Commits; scope is the module name.

## Module notes

### auth
- Location: `services/auth/`; owner team: auth-core.
- Entry points: `services/auth/api.py` (HTTP), `services/auth/tasks.py` (Celery).
- Invariants: every write path in `auth` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/auth/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `auth` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `AuthError` subclasses defined in `services/auth/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/auth.json`; alert rules in `ops/alerts/auth.yaml`; every new endpoint needs a latency SLO entry.

### billing
- Location: `services/billing/`; owner team: billing-core.
- Entry points: `services/billing/api.py` (HTTP), `services/billing/tasks.py` (Celery).
- Invariants: every write path in `billing` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/billing/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `billing` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `BillingError` subclasses defined in `services/billing/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/billing.json`; alert rules in `ops/alerts/billing.yaml`; every new endpoint needs a latency SLO entry.

### catalog
- Location: `services/catalog/`; owner team: catalog-core.
- Entry points: `services/catalog/api.py` (HTTP), `services/catalog/tasks.py` (Celery).
- Invariants: every write path in `catalog` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/catalog/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `catalog` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `CatalogError` subclasses defined in `services/catalog/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/catalog.json`; alert rules in `ops/alerts/catalog.yaml`; every new endpoint needs a latency SLO entry.

### checkout
- Location: `services/checkout/`; owner team: checkout-core.
- Entry points: `services/checkout/api.py` (HTTP), `services/checkout/tasks.py` (Celery).
- Invariants: every write path in `checkout` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/checkout/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `checkout` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `CheckoutError` subclasses defined in `services/checkout/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/checkout.json`; alert rules in `ops/alerts/checkout.yaml`; every new endpoint needs a latency SLO entry.

### inventory
- Location: `services/inventory/`; owner team: inventory-core.
- Entry points: `services/inventory/api.py` (HTTP), `services/inventory/tasks.py` (Celery).
- Invariants: every write path in `inventory` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/inventory/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `inventory` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `InventoryError` subclasses defined in `services/inventory/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/inventory.json`; alert rules in `ops/alerts/inventory.yaml`; every new endpoint needs a latency SLO entry.

### notifications
- Location: `services/notifications/`; owner team: notifications-core.
- Entry points: `services/notifications/api.py` (HTTP), `services/notifications/tasks.py` (Celery).
- Invariants: every write path in `notifications` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/notifications/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `notifications` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `NotificationsError` subclasses defined in `services/notifications/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/notifications.json`; alert rules in `ops/alerts/notifications.yaml`; every new endpoint needs a latency SLO entry.

### search
- Location: `services/search/`; owner team: search-core.
- Entry points: `services/search/api.py` (HTTP), `services/search/tasks.py` (Celery).
- Invariants: every write path in `search` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/search/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `search` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `SearchError` subclasses defined in `services/search/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/search.json`; alert rules in `ops/alerts/search.yaml`; every new endpoint needs a latency SLO entry.

### shipping
- Location: `services/shipping/`; owner team: shipping-core.
- Entry points: `services/shipping/api.py` (HTTP), `services/shipping/tasks.py` (Celery).
- Invariants: every write path in `shipping` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/shipping/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `shipping` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `ShippingError` subclasses defined in `services/shipping/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/shipping.json`; alert rules in `ops/alerts/shipping.yaml`; every new endpoint needs a latency SLO entry.

### tax
- Location: `services/tax/`; owner team: tax-core.
- Entry points: `services/tax/api.py` (HTTP), `services/tax/tasks.py` (Celery).
- Invariants: every write path in `tax` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/tax/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `tax` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `TaxError` subclasses defined in `services/tax/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/tax.json`; alert rules in `ops/alerts/tax.yaml`; every new endpoint needs a latency SLO entry.

### users
- Location: `services/users/`; owner team: users-core.
- Entry points: `services/users/api.py` (HTTP), `services/users/tasks.py` (Celery).
- Invariants: every write path in `users` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/users/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `users` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `UsersError` subclasses defined in `services/users/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/users.json`; alert rules in `ops/alerts/users.yaml`; every new endpoint needs a latency SLO entry.

### reports
- Location: `services/reports/`; owner team: reports-core.
- Entry points: `services/reports/api.py` (HTTP), `services/reports/tasks.py` (Celery).
- Invariants: every write path in `reports` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/reports/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `reports` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `ReportsError` subclasses defined in `services/reports/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/reports.json`; alert rules in `ops/alerts/reports.yaml`; every new endpoint needs a latency SLO entry.

### webhooks
- Location: `services/webhooks/`; owner team: webhooks-core.
- Entry points: `services/webhooks/api.py` (HTTP), `services/webhooks/tasks.py` (Celery).
- Invariants: every write path in `webhooks` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/webhooks/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `webhooks` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `WebhooksError` subclasses defined in `services/webhooks/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/webhooks.json`; alert rules in `ops/alerts/webhooks.yaml`; every new endpoint needs a latency SLO entry.

### audit
- Location: `services/audit/`; owner team: audit-core.
- Entry points: `services/audit/api.py` (HTTP), `services/audit/tasks.py` (Celery).
- Invariants: every write path in `audit` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/audit/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `audit` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `AuditError` subclasses defined in `services/audit/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/audit.json`; alert rules in `ops/alerts/audit.yaml`; every new endpoint needs a latency SLO entry.

### scheduler
- Location: `services/scheduler/`; owner team: scheduler-core.
- Entry points: `services/scheduler/api.py` (HTTP), `services/scheduler/tasks.py` (Celery).
- Invariants: every write path in `scheduler` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/scheduler/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `scheduler` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `SchedulerError` subclasses defined in `services/scheduler/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/scheduler.json`; alert rules in `ops/alerts/scheduler.yaml`; every new endpoint needs a latency SLO entry.

### exports
- Location: `services/exports/`; owner team: exports-core.
- Entry points: `services/exports/api.py` (HTTP), `services/exports/tasks.py` (Celery).
- Invariants: every write path in `exports` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/exports/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `exports` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `ExportsError` subclasses defined in `services/exports/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/exports.json`; alert rules in `ops/alerts/exports.yaml`; every new endpoint needs a latency SLO entry.

### imports
- Location: `services/imports/`; owner team: imports-core.
- Entry points: `services/imports/api.py` (HTTP), `services/imports/tasks.py` (Celery).
- Invariants: every write path in `imports` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/imports/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `imports` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `ImportsError` subclasses defined in `services/imports/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/imports.json`; alert rules in `ops/alerts/imports.yaml`; every new endpoint needs a latency SLO entry.

### pricing
- Location: `services/pricing/`; owner team: pricing-core.
- Entry points: `services/pricing/api.py` (HTTP), `services/pricing/tasks.py` (Celery).
- Invariants: every write path in `pricing` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/pricing/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `pricing` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `PricingError` subclasses defined in `services/pricing/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/pricing.json`; alert rules in `ops/alerts/pricing.yaml`; every new endpoint needs a latency SLO entry.

### promotions
- Location: `services/promotions/`; owner team: promotions-core.
- Entry points: `services/promotions/api.py` (HTTP), `services/promotions/tasks.py` (Celery).
- Invariants: every write path in `promotions` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/promotions/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `promotions` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `PromotionsError` subclasses defined in `services/promotions/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/promotions.json`; alert rules in `ops/alerts/promotions.yaml`; every new endpoint needs a latency SLO entry.

### returns
- Location: `services/returns/`; owner team: returns-core.
- Entry points: `services/returns/api.py` (HTTP), `services/returns/tasks.py` (Celery).
- Invariants: every write path in `returns` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/returns/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `returns` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `ReturnsError` subclasses defined in `services/returns/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/returns.json`; alert rules in `ops/alerts/returns.yaml`; every new endpoint needs a latency SLO entry.

### ledger
- Location: `services/ledger/`; owner team: ledger-core.
- Entry points: `services/ledger/api.py` (HTTP), `services/ledger/tasks.py` (Celery).
- Invariants: every write path in `ledger` emits a domain event through `services/events/publish.py`; handlers must be idempotent and keyed by `event_id`.
- Testing: `pytest services/ledger/tests -q`; slow tests are marked `@pytest.mark.slow` and excluded from the pre-commit run.
- Gotchas: `ledger` shares the `orders` table with other modules read-only; never update rows owned by another module directly, publish a command instead.
- Error handling: raise `LedgerError` subclasses defined in `services/ledger/errors.py`; the API layer maps them to problem+json responses.
- Observability: dashboards are in `ops/dashboards/ledger.json`; alert rules in `ops/alerts/ledger.yaml`; every new endpoint needs a latency SLO entry.

## Release process

1. Step 1: see `docs/release/step_1.md` and follow it exactly, including the checklist at the bottom.
2. Step 2: see `docs/release/step_2.md` and follow it exactly, including the checklist at the bottom.
3. Step 3: see `docs/release/step_3.md` and follow it exactly, including the checklist at the bottom.
4. Step 4: see `docs/release/step_4.md` and follow it exactly, including the checklist at the bottom.
5. Step 5: see `docs/release/step_5.md` and follow it exactly, including the checklist at the bottom.
6. Step 6: see `docs/release/step_6.md` and follow it exactly, including the checklist at the bottom.
7. Step 7: see `docs/release/step_7.md` and follow it exactly, including the checklist at the bottom.
8. Step 8: see `docs/release/step_8.md` and follow it exactly, including the checklist at the bottom.
9. Step 9: see `docs/release/step_9.md` and follow it exactly, including the checklist at the bottom.
10. Step 10: see `docs/release/step_10.md` and follow it exactly, including the checklist at the bottom.
11. Step 11: see `docs/release/step_11.md` and follow it exactly, including the checklist at the bottom.
12. Step 12: see `docs/release/step_12.md` and follow it exactly, including the checklist at the bottom.

## Style details

- Rule S1: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S2: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S3: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S4: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S5: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S6: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S7: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S8: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S9: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S10: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S11: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S12: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S13: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S14: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S15: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S16: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S17: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S18: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S19: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S20: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S21: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S22: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S23: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S24: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
- Rule S25: prefer small functions (under 40 lines), early returns, and explicit names over comments; keep docstrings for public APIs only; never silence a linter without a linked ticket.
