---
description: Draft a reply to a customer support ticket
argument-hint: <ticket id>
allowed-tools: Bash(python manage.py show_ticket:*), Read
---
Load ticket $ARGUMENTS with `python manage.py show_ticket`. Read the conversation and the related order. Write a reply that addresses the customer's actual problem, offers the right remedy under `docs/refund-policy.md`, and matches their tone (formal customers get formal replies). If the policy does not cover the case, say so and propose options for the agent to choose.
