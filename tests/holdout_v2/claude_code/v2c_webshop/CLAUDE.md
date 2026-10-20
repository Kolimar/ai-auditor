# Webshop

Next.js 14 storefront with a Node/Express API in `server/` and Postgres via Prisma.

- `npm run dev` starts both apps. Tests: `npm test` (Vitest) and `npm run e2e` (Playwright).
- Follow the conventions in `docs/CONTRIBUTING.md`. Use named exports, no default exports in components.
- Never edit files in `prisma/migrations/` by hand.
