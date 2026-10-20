---
name: owasp-code-review
description: Structured secure code review of a web service along the OWASP Top 10, for when someone asks for a security review of a repository, module or pull request.
---
# Secure code review

This procedure is long on purpose; do not skip steps because the code "looks fine".

## Scope
Ask which components handle untrusted input (HTTP handlers, queue consumers, file importers). If the user does not know, find them by searching for framework route registrations and message-listener decorators.

## Pass 1: Access control and authentication
For each entry point, find where identity is established and where authorization is checked. Look for object-level authorization (does the handler check that the record belongs to the caller?), missing checks on admin routes, JWT validation shortcuts (alg none, missing audience check), session fixation and password reset flows that leak whether an account exists.

## Pass 2: Injection and deserialization
Follow user data to sinks: SQL (string concatenation, ORM raw queries), shell execution, template rendering, XML parsers with external entities, unsafe deserializers, SSRF in URL fetchers. For each sink decide whether encoding or parameterization is actually applied on every path, not only the main one.

## Pass 3: Cryptography and secrets
Check algorithms, modes, key sources, random number generators, TLS settings, and secrets in config or code.

## Pass 4: Business logic
Think like an abuser: race conditions on balance updates, replayable requests, price tampering, mass assignment.

## Output
For each issue give location, description of the attack, severity with reasoning, and a fix. Close with a list of areas you did not cover. If you are unsure whether something is exploitable, say so and describe how to confirm.
