---
name: model-card-writer
description: Writes a model card (intended use, data, metrics, limitations) for a trained model. Use when a model is about to be shared or released.
---
1. Read the run config, `eval.json` and the dataset card.
2. Draft the sections Intended Use, Training Data, Evaluation, Limitations and Ethical Considerations.
3. In Limitations be specific: subgroups where metrics are weaker (from `eval_by_group.json`), distribution shifts the data does not cover, and failure modes seen in error analysis.
4. Keep claims tied to numbers in the evaluation files; do not invent results.
