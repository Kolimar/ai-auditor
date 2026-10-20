# Gateway service

## /v1/accounts

Routing for `/v1/accounts` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/accounts: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/accounts/{id}

Routing for `/v1/accounts/{id}` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/accounts/{id}: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/charges

Routing for `/v1/charges` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/charges: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/charges/{id}/capture

Routing for `/v1/charges/{id}/capture` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/charges/{id}/capture: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/refunds

Routing for `/v1/refunds` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/refunds: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/customers

Routing for `/v1/customers` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/customers: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/customers/{id}/sources

Routing for `/v1/customers/{id}/sources` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/customers/{id}/sources: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/webhooks

Routing for `/v1/webhooks` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/webhooks: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/events

Routing for `/v1/events` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/events: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/payouts

Routing for `/v1/payouts` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/payouts: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/balance

Routing for `/v1/balance` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/balance: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/disputes

Routing for `/v1/disputes` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/disputes: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/files

Routing for `/v1/files` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/files: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v1/invoices

Routing for `/v1/invoices` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v1/invoices: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v2/accounts

Routing for `/v2/accounts` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v2/accounts: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v2/charges

Routing for `/v2/charges` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v2/charges: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v2/payments

Routing for `/v2/payments` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v2/payments: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.

## /v2/subscriptions

Routing for `/v2/subscriptions` is declared in `routes/routes.yaml`. Rate limit bucket is chosen from the plan table; auth middleware order is mTLS, API key, then OAuth scope check. Timeouts: upstream 4s, idempotency window 24h for mutating methods. Error mapping for /v2/subscriptions: upstream 409 becomes 409 with `idempotency_conflict`, upstream 5xx becomes 502 with retry-after header when the circuit breaker is open.
