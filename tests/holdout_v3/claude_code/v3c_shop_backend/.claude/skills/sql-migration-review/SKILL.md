---
name: sql-migration-review
description: Reviews Django or raw SQL migrations for locking, data loss and rollback problems on large tables. Use when a PR adds or changes a migration.
allowed-tools: Read, Grep, Glob, Bash
---
# Migration review

Look at every migration in the PR and, for each operation, answer:

1. Does it take a long lock on a big table? Check row counts in `docs/table-sizes.md`. Adding a column with a default, creating indexes without `CONCURRENTLY`, and altering column types are the usual culprits.
2. Can it lose data? Dropping or renaming columns while old code still reads them is a common trap during rolling deploys.
3. Is it reversible? If not, is that acceptable and documented?
4. Does it interact with other pending migrations or with Celery tasks that run during deploy?
5. Is the backfill batched and idempotent?

Run `python manage.py sqlmigrate <app> <name>` to see the SQL for anything you are unsure about. Conclude with approve, approve with changes or block, and rewrite risky operations in a safer sequence when you block.
