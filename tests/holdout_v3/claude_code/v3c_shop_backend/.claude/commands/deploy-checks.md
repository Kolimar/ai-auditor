---
description: Pre-deploy checks
allowed-tools: Bash
---
Before deploying, run `pytest -q`, then `ruff check .`, then `python manage.py makemigrations --check --dry-run`, and finally `alembic upgrade --sql head` for the reporting DB. Report pass or fail for each.
