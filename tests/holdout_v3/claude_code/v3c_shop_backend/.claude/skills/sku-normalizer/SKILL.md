---
name: sku-normalizer
description: Normalizes SKU strings to the canonical format.
---
Given a list of SKUs, return each in canonical form: uppercase, spaces and underscores replaced by hyphens, and the numeric part zero padded to six digits (for example `ab_42` becomes `AB-000042`). Output one per line in the same order.
