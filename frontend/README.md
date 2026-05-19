# Trading Journal — Frontend

Vue 3 + Vite + TypeScript + Naive UI single-page app, served by the FastAPI backend
in production (see `docs/design/frontend-implementation-plan.md`).

## Prerequisites

- Node.js **20+** (24+ recommended)
- The backend running on `127.0.0.1:8000` (see `../backend/README.md`)

## Local development

```bash
# Inside frontend/
npm install
npm run dev
# Vite listens on localhost:5173. strictPort: true — it WILL refuse to start
# if 5173 is already taken (intentional; see "Common pitfalls" below).
```

If you're developing remotely, forward both ports from your laptop:

```bash
ssh -fNL 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 user@dev-server
```

Then open `http://localhost:5173` in your laptop's browser.

> Use `localhost`, not `127.0.0.1` — cookies are stored against the literal
> hostname and the app is configured to be reached via `localhost`. Mixing the
> two will make sessions look like they "vanish" between page loads.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR. Binds `localhost:5173`. |
| `npm run build` | Type-checks with `vue-tsc` then builds production bundle to `dist/`. |
| `npm run preview` | Serves the production build locally for sanity-checking. |
| `npm run codegen` | Regenerates `src/api/schema.d.ts` from the backend's `/openapi.json`. **Requires the backend to be running on `127.0.0.1:8000`.** Run after any backend schema change. |

## API types — codegen workflow

API request/response types are auto-generated from the backend's `/openapi.json`
spec via `openapi-typescript`, and written to `src/api/schema.d.ts`.

That file is **committed to git** so that fresh checkouts compile without
needing the backend running first. But once you change the backend schema
(new endpoint, new field, renamed field, enum value added), re-run:

```bash
# Backend must be up on :8000
npm run codegen
git diff src/api/schema.d.ts   # review what changed
npm run build                  # confirm no downstream breakage
```

**Don't hand-edit `schema.d.ts`** — re-run codegen instead. Consume types from it like:

```ts
import type { components } from './schema'
type Account = components['schemas']['AccountRead']
```

The hand-written file `src/api/types.ts` keeps only things that aren't 1:1 with
an OpenAPI schema (the `ApiError` class, payload aliases for our login
marshalling).

## Common pitfalls

### "Vite is already running on this port" → kill the leak

`strictPort: true` makes Vite refuse to start if 5173 is taken. Find and kill
the leaked process:

```bash
# On the dev server:
ss -tlnp | grep :5173      # find the PID
kill <pid>                 # or kill -9 <pid> if it ignores SIGTERM
# alternatively, kill everything Vite:
pkill -f vite
```

### "My session disappears every time I refresh"

99% of the time this is one of the following — verify in order:

1. **You're on `127.0.0.1:5173` in some tabs and `localhost:5173` in others.**
   Cookies are stored per literal hostname, so they don't transfer between the
   two. Use **`localhost`** consistently (it's the URL Vite prints and the one
   our docs use). Close the `127.0.0.1` tab and clear those cookies.
2. **A stale cookie from a previous backend run.** If you reset `dev.db` (e.g.
   `rm -f backend/dev.db && uv run alembic upgrade head`), every existing
   browser cookie now points at a session that no longer exists in the DB,
   so `/users/me` returns 401. Clear cookies for `localhost` in DevTools →
   Application → Cookies, then log in fresh.
3. **An old leaked Vite process on a different port** (see above). Your SSH
   tunnel points at 5173 but the *new* Vite picked 5176 — you're staring at
   stale code from a previous session. Kill the leak; restart Vite.

## How API calls reach the backend

Starting in F0.2, `vite.config.ts` proxies `/auth/*`, `/users/*`, `/accounts/*`, `/health`
to the backend on `127.0.0.1:8000`. The browser sees a single origin (`localhost:5173`),
so the backend can stay CORS-free in both dev and prod (see plan §5).

## Stack

- **Vue 3** (Composition API, `<script setup>`)
- **Vite** (dev server + build)
- **TypeScript** (strict mode via `@vue/tsconfig`)
- **Naive UI** (component library; components auto-imported via `unplugin-vue-components`)
- **vfonts** (Lato + Fira Code fonts that Naive UI is designed around)
- **Pinia** (state management; wired in F0.2)
- **Vue Router** (router; wired in F0.3)
- **openapi-typescript** (build-time only; turns the backend's `/openapi.json` into TS types — see "API types" above)
