---
name: api-design-review
description: Guides a careful design review of a new or changed REST endpoint in server/. Use when someone proposes a new route, changes a response shape, or asks whether an API is "well designed".
---
# API design review

A review of an endpoint is not a checklist exercise; the goal is to find the places where a client will be surprised.

## 1. Understand the contract
Read the route handler, its validation schema and every test that exercises it. Write down in one paragraph what the endpoint promises: inputs, outputs, errors, side effects.

## 2. Compare with the existing surface
Grep `server/routes` for sibling endpoints. Naming, pagination (`cursor` vs `page`), error envelope and status code usage must match what already exists unless there is a reason recorded in the PR.

## 3. Probe the failure modes
- What happens on a retry of a non-idempotent POST? Is there an idempotency key?
- What does a client see when the resource exists but belongs to another user?
- Can the response grow without bound?
- Is a breaking change hidden behind a field rename?

## 4. Judge compatibility
Decide whether the change is backwards compatible for the mobile clients still on v2. If it is not, propose a versioning or deprecation path and say who must be told.

## 5. Write the review
Give a verdict (approve, approve with changes, rework) followed by the reasoning for each non-trivial point. Prefer questions to commands when the intent is unclear.
