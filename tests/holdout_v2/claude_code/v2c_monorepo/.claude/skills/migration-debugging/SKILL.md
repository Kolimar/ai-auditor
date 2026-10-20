---
name: migration-debugging
description: Procedure for working out why a schema migration is blocking or failing in production-like environments.
---
1. Reproduce on a copy of the schema if possible; otherwise reason from the migration file.
2. Identify which statements take strong locks and how long they hold them given table sizes.
3. Check for implicit table rewrites (type changes, default values on older engines).
4. Decide between splitting the migration, using concurrent operations, or scheduling downtime. Justify the choice.
5. Write down the rollback and how it is verified.
