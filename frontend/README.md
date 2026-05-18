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
# Vite listens on 127.0.0.1:5173.
```

If you're developing remotely, forward both ports from your laptop:

```bash
ssh -fNL 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 user@dev-server
```

Then open `http://localhost:5173` in your laptop's browser.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR. Binds `127.0.0.1:5173`. |
| `npm run build` | Type-checks with `vue-tsc` then builds production bundle to `dist/`. |
| `npm run preview` | Serves the production build locally for sanity-checking. |

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
