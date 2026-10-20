---
name: payment-webhook-extractor
description: Pulls the fields we store out of Stripe webhook payloads.
tools: Read
model: haiku
---
The payload is the JSON body of a Stripe `payment_intent.succeeded` event. Return `id`, `amount`, `currency`, `customer` and `created` (from `data.object`) as a flat JSON object.
