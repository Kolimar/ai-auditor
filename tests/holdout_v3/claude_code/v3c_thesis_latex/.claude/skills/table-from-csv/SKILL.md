---
name: table-from-csv
description: Converts CSV result files in results/ into LaTeX booktabs tables for the thesis.
allowed-tools: Read, Write
---

For each `results/*.csv` that the user names, write `tables/<basename>.tex` containing a `table` environment with `\centering`, a `tabular` using `booktabs` (`\toprule`, `\midrule`, `\bottomrule`), the header row from the CSV in bold, and numeric columns right-aligned with two decimals. Use the CSV file name as the label (`tab:<basename>`) and leave the caption as `\caption{TODO}`. Escape underscores and percent signs.
