---
name: experiment-log
description: Record the state of an analysis run in the lab log.
allowed-tools: Bash
---
Whenever a run finishes:
1. `git add notebooks data/processed`
2. `jupyter nbconvert --to html notebooks/$NB.ipynb --output-dir reports/`
3. `sha256sum data/processed/* > reports/checksums.txt`
4. `git commit -m "run: $NB"`
5. `git tag run-$(date +%Y%m%d-%H%M)`
