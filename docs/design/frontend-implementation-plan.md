# Frontend MVP Implementation Plan — v0 Draft

**Language:** English | [中文](./frontend-implementation-plan.zh.md)

> Status: **DRAFT v0.1** (2026-05-18). The execution plan for the first end-to-end slice of the frontend, on `refactoring/rebuild`. Companion document to [data-model.md](./data-model.md) and [mvp-implementation-plan.md](./mvp-implementation-plan.md) (backend). Iterate here before writing code.

## 1. Purpose and approach

The backend tracer bullet (Phases 0–4) shipped JSON endpoints for `/health`, `/auth/*`, `/users/me`, and full `Account` CRUD. This plan is the **frontend tracer bullet** — building the *narrowest* slice of UI that proves the full stack works end-to-end through a real browser: cookie session, router auth guard, fetch with credentials, and a working component library.

**Approach: same tracer-bullet philosophy.** Don't try to build every screen up front. Prove the wire is conductive first — *register → login → see a protected page → logout* — then expand horizontally to CRUD screens in later phases.

Why: the riskiest pieces of integrating Vue 3 + Vite + FastAPI cookie sessions aren't writing forms (forms are repetitive). They're the wiring: Vite dev-proxy preserving cookies, Pinia auth state surviving page reload, router guards firing in the right order, Naive UI providers mounted at the right level, single-origin discipline holding from dev through prod. A tracer bullet exposes that integration risk fast.

## 2. Scope

### In scope (this plan, Phase F0)

- `frontend/` directory: Vite project scaffold + dependencies + tooling
- Vue 3 + TypeScript + Pinia + Vue Router 4
- Naive UI as the component library (with auto-imported types)
- Vite dev-proxy forwarding API paths to the backend (no CORS on the backend)
- HTTP client wrapper (`fetch` + `credentials: 'include'` + error normalization)
- Pinia `auth` store with `login` / `register` / `logout` / `fetchMe` / `init`
- Three pages: `Login`, `Register`, `Dashboard` (auth-protected stub)
- Router auth guard (redirect unauthenticated → `/login`, authenticated-on-`/login` → `/`)
- `frontend/README.md` documenting dev workflow + SSH tunnel
- Backend regression — Phase 2–4 pytest suite continues to pass; no backend code change required

### Explicitly NOT in scope (deferred)

- **Account CRUD UI** — Phase F1
- **Position / Trade / TradePlan / StrategyConfig UI** — Phase F2+
- **Strategy-specific views** (wheel cycle, IC P&L diagram, PMCC roll history) — later
- **Charts and reports** — later (ECharts / Plotly when we get there)
- **Frontend unit tests (Vitest)** — defer until there's logic worth testing; F0 logic is thin enough to verify manually
- **E2E tests (Playwright)** — defer
- **Tailwind CSS** — Naive UI's design tokens cover what we need; revisit if/when we want heavily custom layouts
- **`openapi-typescript` codegen** — defer to F1 (hand-write the few types F0 needs)
- **i18n** — single-language English UI for MVP
- **PWA / service worker** — out of scope
- **Dark mode toggle** — keep it for later; Naive UI's `darkTheme` is one prop away when needed
- **Single-container Docker prod build** — Phase 5 of the backend plan; F0 stays dev-only

## 3. Tech stack summary

| Layer | Choice |
|---|---|
| Framework | **Vue 3** (Composition API, `<script setup>`) |
| Build tool / dev server | **Vite 5+** |
| Language | **TypeScript 5+** |
| Routing | **Vue Router 4** |
| State management | **Pinia** |
| Component library | **Naive UI** |
| HTTP client | Native `fetch` (thin wrapper, no axios) |
| Type checker | `vue-tsc` |
| Linter / formatter | **ESLint** (`@vue/eslint-config-typescript`) + **Prettier** (defer if friction; not required for F0) |
| Auto-imports | `unplugin-vue-components` with `naive-ui` resolver |

## 4. Directory structure

```
trading-journal/
├── backend/                            # (unchanged from Phase 4)
├── frontend/
│   ├── package.json
│   ├── package-lock.json               # committed
│   ├── tsconfig.json
│   ├── tsconfig.node.json              # for vite.config.ts
│   ├── vite.config.ts                  # Vue plugin, auto-imports, dev-proxy
│   ├── index.html                      # HTML entry, mounts #app
│   ├── env.d.ts                        # ambient types (Vue SFC, auto-imports)
│   ├── README.md                       # dev workflow, SSH tunnel notes
│   └── src/
│       ├── main.ts                     # bootstrap: app + pinia + router + naive theme
│       ├── App.vue                     # root: NConfigProvider + provider stack + <router-view>
│       ├── api/
│       │   ├── http.ts                 # fetch wrapper, throws on non-2xx, parses JSON
│       │   └── types.ts                # hand-written TS interfaces (User, FastAPIUsersError)
│       ├── stores/
│       │   └── auth.ts                 # Pinia: user, isAuthenticated, login, logout, fetchMe, init
│       ├── router/
│       │   └── index.ts                # routes + beforeEach guard
│       └── views/
│           ├── LoginView.vue
│           ├── RegisterView.vue
│           └── DashboardView.vue
└── docs/
    └── design/
        └── frontend-implementation-plan.md  (this file)
```

## 5. Phased plan

Each sub-phase has **Goal**, **Tasks**, **Manual verification**, **Acceptance**. Run sub-phases sequentially.

### F0.1 — Scaffold + Naive UI hello world

**Goal.** Vite project boots, browser at `localhost:5173` renders a Naive UI button. Establishes that the toolchain works.

**Tasks.**
1. `mkdir frontend && cd frontend && npm create vite@latest . -- --template vue-ts`
2. Add deps:
   - runtime: `vue-router`, `pinia`, `naive-ui`, `vfonts`
   - dev: `unplugin-vue-components` (for auto-importing Naive UI components + types)
3. Configure `vite.config.ts`:
   - `@vitejs/plugin-vue`
   - `unplugin-vue-components` with `NaiveUiResolver`
   - `server.host = '127.0.0.1'` (do NOT bind 0.0.0.0 — we use SSH tunnel like the backend)
   - `server.port = 5173`
4. Write `src/App.vue` with a minimal `<n-config-provider :theme="null">` wrapping an `<n-button>Hello</n-button>` plus a `<router-view />` placeholder
5. Write `src/main.ts`: create app, mount

**Manual verification.**
```bash
cd frontend
npm install
npm run dev
# Open (via SSH tunnel) http://localhost:5173
# Expected: Naive button renders, no console errors, no missing types in editor
```

**Acceptance.** Browser shows the button. `npm run build` succeeds (this catches type errors early).

---

### F0.2 — Auth plumbing: http client + Pinia store + Vite proxy

**Goal.** Console-driven evidence that the browser can reach the backend through the Vite proxy and that auth state survives in Pinia.

**Tasks.**
1. **Vite proxy** in `vite.config.ts`. The backend mounts every route under the
   `/api` prefix (see backend `main.py`), so a single rule suffices and the
   SPA's own routes (`/accounts`, `/login`, …) never collide with API paths:
   ```ts
   server: {
     port: 5173,
     host: 'localhost',
     strictPort: true,
     proxy: {
       '/api': 'http://127.0.0.1:8000',
     }
   }
   ```
2. **`src/api/types.ts`** — hand-written interfaces (≈30 lines for F0):
   ```ts
   export interface User {
     id: string
     email: string
     is_active: boolean
     is_verified: boolean
     is_superuser: boolean
     last_login_at: string | null
     created_at: string
   }
   ```
3. **`src/api/http.ts`** — thin wrapper:
   - `request(method, path, options)` always sends `credentials: 'include'`
   - On non-2xx: parse JSON, throw a typed `ApiError` carrying status + body
   - On 2xx with JSON body: return parsed JSON
   - On 204: return `null`
   - Helpers: `getJson`, `postJson`, `postForm` (the last one for `/auth/login`'s `application/x-www-form-urlencoded` body)
4. **`src/stores/auth.ts`** (Pinia):
   - state: `user: User | null`, `initialized: boolean`
   - getter: `isAuthenticated: boolean`
   - actions: `register({email, password})`, `login({email, password})`, `logout()`, `fetchMe()`, `init()`
   - `init()` calls `fetchMe()` once and silently swallows 401 (means "not logged in")
   - `login()` calls `/auth/login` then `fetchMe()` to populate `user`

**Manual verification (browser console).**
```js
// On http://localhost:5173 (the Vite dev server), in DevTools console:
fetch('/health', {credentials:'include'}).then(r => r.json()).then(console.log)
// Expected: {status: "ok"}  ← proves Vite proxy is forwarding to FastAPI
```

```js
// After loading the page (App.vue installed Pinia), in console:
const auth = pinia.state.value.auth  // or expose via window for debugging
// Confirm auth.user === null, auth.initialized === true
```

**Acceptance.** `/health` proxies through. Auth store loads without error. Calling `auth.login(...)` from console (with a real account registered earlier via curl) populates `auth.user` and the browser DevTools "Application" tab shows a `trading_journal_session` cookie under `http://localhost:5173`.

---

### F0.3 — Auth pages + router guard

**Goal.** Full UI flow: register → auto-login → dashboard → logout → back to login. Refresh-survives-the-session.

**Tasks.**
1. **`src/router/index.ts`**:
   - Routes: `/login` → `LoginView`, `/register` → `RegisterView`, `/` → `DashboardView` (with `meta: { requiresAuth: true }`)
   - `beforeEach` guard:
     - If `to.meta.requiresAuth && !auth.isAuthenticated` → redirect to `/login`
     - If `to.path in ['/login', '/register'] && auth.isAuthenticated` → redirect to `/`
2. **`src/main.ts`** must do `await authStore.init()` **before** `router.isReady()`, otherwise the first navigation runs before `/users/me` resolves and the user sees a `/login → /` flicker after a page refresh
3. **`src/App.vue`** finalized provider stack:
   ```vue
   <n-config-provider :theme="null">
     <n-message-provider>
       <n-dialog-provider>
         <router-view />
       </n-dialog-provider>
     </n-message-provider>
   </n-config-provider>
   ```
   (Providers required for `useMessage()` and `useDialog()` composables to find their context.)
4. **`LoginView.vue`** — `n-form` with `email` + `password` fields; submit calls `auth.login()`; on success `router.push('/')`; on error use `useMessage().error(err.message)`
5. **`RegisterView.vue`** — `n-form` with `email` + `password`; on success call `auth.login()` immediately (same credentials) then `router.push('/')`; surface validation errors (400 → "password too short", etc.)
6. **`DashboardView.vue`** — minimal:
   - `n-page-header` with the user's email from `auth.user`
   - "Accounts (coming in Phase F1)" placeholder card
   - "Logout" button → `auth.logout()` → `router.push('/login')`

**Manual verification.** Full click-through, see §8 below.

**Acceptance.** Full flow works in the browser. Refresh on `/` does not bounce to `/login` and back. Refresh on `/login` after logout stays on `/login`.

---

### F0.4 — Full e2e smoke + backend regression

**Goal.** Confirm nothing on the backend broke and the integration is solid end-to-end.

**Tasks.**
1. Run backend regression: `cd backend && uv run pytest -q && uv run ruff check . && uv run mypy src` — must stay green (Phase 2–4: 46 tests pass; no backend code should have changed)
2. Frontend type-check: `cd frontend && npm run build` (this runs `vue-tsc --noEmit` then `vite build` — both must pass)
3. Walk through §8 manual recipe
4. Update `project_tech_stack` memory: change "single-container Docker SSR" → "single-container Docker SPA (FastAPI serves Vite-built `dist/`)"

**Acceptance.** All checks green, full manual flow works, memory updated.

## 6. Remote SSH development

You already use SSH local-forward for the backend port. Frontend needs the same treatment.

```bash
# On your operating laptop:
ssh -fNL 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 user@server
```

Then on the laptop, both `http://localhost:8000` (backend) and `http://localhost:5173` (Vite dev) work.

### Running Vite during development

Same pattern as `uvicorn`: long-running, survives SSH disconnect:

```bash
# Pane 1 on the server:
tmux new -s backend
cd backend
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
# Ctrl-b d

# Pane 2:
tmux new -s frontend
cd frontend
npm run dev    # listens on 127.0.0.1:5173 by default (per vite.config.ts)
# Ctrl-b d
```

### HMR through the tunnel

Vite's Hot Module Replacement uses a WebSocket from browser → Vite dev server. This works through the SSH local-forward without special configuration (WS upgrade headers pass through). If HMR ever fails, fall back to `npm run dev -- --hmr.clientPort 5173` to force the client URL.

### Why we bind 127.0.0.1

Same reason as the backend: keeps the port off the LAN and out of any public-facing routing. The SSH tunnel is the only way in. **Never** `npm run dev -- --host 0.0.0.0` unless you understand the network exposure.

## 7. Testing architecture

**F0 has no automated frontend tests.** Justification:

- The logic surface is tiny: ~5 store actions, ~3 views with minimal logic, 1 router guard
- Manual click-through covers it faster than any test could
- Setting up Vitest, Vue Test Utils, jsdom, and component mocking is a 1-day rabbit hole that doesn't pay back at F0 scale

**What stays automated:**

- **Backend pytest** (Phase 2–4: 46 tests) — **must remain green throughout F0** as the regression guard. Run before and after every sub-phase.
- **`vue-tsc` via `npm run build`** — TypeScript catches the bulk of frontend regressions at compile time

**When to add tests** (post-F0):

- **Vitest + Vue Test Utils** for the auth store and HTTP wrapper once they grow beyond F0 scope
- **Playwright** for full end-to-end browser tests once there are ≥3 user journeys worth automating (register, CRUD an account, view dashboard with positions, etc.) — likely Phase F2 or F3
- Worth deferring until then because the e2e setup (browser containers, DB seeding via test-only API, etc.) is meaningful work

## 8. Manual verification reference

Full click-through that exercises Phase F0 end-to-end. Run after F0.3 (against the bare `npm run dev` + uvicorn).

> Prerequisite: backend running on `127.0.0.1:8000`, SQLite migrated to head, SSH tunnel up for both 8000 and 5173.

1. Browser → `http://localhost:5173/` → expected: instantly redirects to `/login` (because no cookie yet)
2. On `/login`, click "Register" link → on `/register`
3. Fill `alice@example.com` / `correct horse battery` → submit → expected: redirected to `/` showing "Welcome, alice@example.com"
4. DevTools → Application → Cookies → `localhost:5173` → expected: `trading_journal_session=...`, HttpOnly, SameSite=Lax
5. **Refresh the page** (F5) → expected: still on `/`, still logged in (no flicker to `/login`)
6. Click "Logout" → expected: cookie gone, on `/login`
7. Try to visit `/` directly → expected: redirected back to `/login`
8. Log in again with the same credentials → expected: back on `/`
9. On the server, check `access_tokens` table:
   ```bash
   sqlite3 backend/dev.db "SELECT count(*) FROM access_tokens"
   # Expected: 1 (after step 8)
   ```
10. Edge cases:
    - Try registering same email a second time → expected: error toast "user already exists"
    - Try logging in with wrong password → expected: error toast "bad credentials"
    - Try registering with `pw` (5 chars) → expected: error toast about password length

## 9. After this tracer bullet

Once F0 ships, the next iterations (each its own short plan section, possibly its own doc):

1. **F1 — Account CRUD UI.** Accounts list (`n-data-table`), create form (modal or dedicated page), edit, soft-delete with archived filter toggle. Adds `openapi-typescript` for codegen so we stop hand-writing types. Estimate: one focused session.
2. **F2 — Instrument + Position skeleton.** Requires backend Phase 5+ (Instrument and Position CRUD endpoints, currently not built). Strategy-aware Position creation flow.
3. **F3 — Trade entry.** The atomic-trade entry form, with `order_group_id` UX for multi-leg fills (open IC, assignment pair, etc.).
4. **F4 — Read-only dashboards & charts.** Open positions table, closed-position PnL history, per-currency portfolio summary (per [data-model.md §6](./data-model.md#currency-placement)).
5. **F5 (or Phase 5 backend) — Production build wiring.** Add `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` to backend `main.py`, update Dockerfile to multi-stage build that bakes `frontend/dist` into the runtime image. The single-container deployment locks in here.

---

## Changelog

- **v0.1 (2026-05-18)** — Initial plan. Phase F0 covers Vite + Vue 3 + Naive UI scaffold, auth pages, and the router/store/proxy plumbing. No backend code changes. F1+ deferred.
