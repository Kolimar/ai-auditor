---
name: lr-schedule-advisor
description: Recommends a learning rate schedule and warmup for a config given model size, batch size and dataset size.
---
Given the config, think about the optimizer and the number of steps. Recommend a schedule (cosine, one-cycle, linear decay), a warmup length and peak learning rate with the reasoning, using the loss curves of earlier runs in `runs/` as evidence when available. Mention what to monitor to confirm the choice and when to back off.
