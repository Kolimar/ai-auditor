---
description: Deploy the current branch to staging
allowed-tools: Bash
---
Execute the following and stop at the first failure:

```
git fetch origin
npm ci
npm run build
npm run deploy:staging
curl -fsS https://staging.shop.example.com/healthz
```

Then tell me the staging URL.
