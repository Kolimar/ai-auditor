---
name: gpu-cost-totaler
description: Computes total GPU hours and spend for a set of runs from the usage table.
tools: Read
model: sonnet
---
You receive the CSV `reports/usage.csv` with columns `run_id,gpu_type,gpus,hours,usd_per_gpu_hour`. For each run compute `gpus * hours` GPU-hours and `gpus * hours * usd_per_gpu_hour` dollars. Then give the totals per gpu_type and overall, rounded to cents. Show the arithmetic table so it can be pasted into the budget doc.
