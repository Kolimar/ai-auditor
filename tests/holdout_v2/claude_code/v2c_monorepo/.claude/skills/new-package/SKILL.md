---
name: new-package
description: Scaffold a new package in the monorepo.
allowed-tools: Bash
---
For package name N:
1. `mkdir -p packages/N/src packages/N/__tests__`
2. `cp tools/templates/package.json packages/N/package.json`
3. `sed -i "s/__NAME__/N/g" packages/N/package.json`
4. `cp tools/templates/tsconfig.json packages/N/tsconfig.json`
5. `echo "export {};" > packages/N/src/index.ts`
6. `pnpm install`
7. `pnpm --filter @orbit/N tsc --noEmit`
