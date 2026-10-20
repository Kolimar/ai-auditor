---
name: dbt-model-review
description: Review a dbt model or a set of models for correctness, grain, performance and test coverage. Use when a PR changes files under warehouse/models.
---
# dbt model review

1. Identify the grain of the model from its `group by` / unique key and check that the YAML tests assert it.
2. Read the joins. A many-to-many join that silently multiplies rows is the most common defect; check the cardinality of each side using the parent models' tests.
3. Check incremental logic: is the filter on a column that is reliably populated? Can late-arriving rows be lost?
4. Look at cost: partition filters present, no `select *` from wide sources, clustering aligned with join keys.
5. Check documentation and naming against neighbouring models.

Write the review as a short list of issues ordered by risk, each with a suggested change. When the model seems fine, state which risks you specifically ruled out.
