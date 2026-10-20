---
name: release-checklist
description: Steps to cut a release of the webshop to production.
allowed-tools: Bash
---
# Release

When asked to release, always perform these steps in order:

1. Run `git fetch origin && git checkout main && git pull`.
2. Run `npm ci`.
3. Run `npm test`.
4. Run `npm run build`.
5. Run `npm version patch`.
6. Run `git push --follow-tags`.
7. Run `npm run deploy:prod`.
8. Run `curl -fsS https://shop.example.com/healthz`.

Report the output of the last step.
