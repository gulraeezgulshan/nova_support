# SupportNova web

Next.js 16 frontend for SupportNova. See the [project README](../README.md) for setup.

```bash
pnpm dev            # http://localhost:3000 (needs the API on :8000 and Clerk keys in .env.local)
pnpm api:generate   # regenerate the typed API client from openapi.json
pnpm lint && pnpm typecheck
```
