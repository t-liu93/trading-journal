# V1 Phase F6 — Deployment & Release Readiness

**Language:** English | [中文](./v1-implementation-plan-f6.zh.md)

> Status: **DRAFT v0.2** (2026-05-30). The V1 closeout phase. Companion to
> [v1-release-plan.md](./v1-release-plan.md) (V1 north star — see §6.5 F6, §8.1
> CI gate, §8.2 Postgres parity, §8.3 walkthrough),
> [frontend-expansion-plan.md §F6](./frontend-expansion-plan.md#f6--single-container-docker-production-wiring)
> (macro), and [mvp-implementation-plan.md §5 Phase 5](./mvp-implementation-plan.md#phase-5--docker-single-container-deployment)
> (original single-container intent). Iterate here before writing any code.
>
> **Scope note.** F6 was originally "Docker single-container wiring" only. This
> plan widens it into the V1 closeout phase covering the three deliverables the
> user grouped together on 2026-05-30: **(A) Docker image build**, **(B) CI/CD**,
> **(C) full-feature walkthrough guide**. They ship as one phase because they are
> the release-readiness bundle — the app already works (F0–F5 done); F6 makes it
> *deployable, continuously verified, and documented*.
>
> **Execution order (revised 2026-05-30): A → C → B** — build the image by hand,
> walk through it manually, then automate that proven build as CI. §4 (Part B) is
> revisited last, not now.

## 1. Purpose & context

F0–F5 and P6–P12 are all shipped on `refactoring/rebuild` (406 backend tests
green; `vue-tsc` + `vite build` clean). The application is feature-complete for
V1. What is missing is everything around the code that turns "runs on my laptop"
into "a deployable, defended artifact":

- **A — Docker image.** A single container where FastAPI serves the Vite-built
  SPA from `/` and the API from `/api/*` (the URL split was designed for this
  from day one — see [`main.py` docstring](../../backend/src/trading_journal/main.py)).
- **B — CI/CD.** GitHub Actions that runs the backend quality gate on every push
  / PR and builds + publishes the image to GHCR on `main`.
- **C — Walkthrough guide.** A single bilingual document that walks a fresh user
  through every V1 feature end-to-end. Doubles as the manual acceptance script
  that [v1-release-plan.md §8.3](./v1-release-plan.md#83-manual-acceptance-walkthrough)
  deferred until F6 (trigger now active).

### Settled decisions (do not re-derive)

Locked with the user on 2026-05-30:

1. **Plan-first.** This document is written and reviewed before any code lands,
   per the project's [phase-plan convention](./v1-release-plan.md#1-purpose-and-maintenance).
2. **Image registry = GHCR.** `ghcr.io/t-liu93/trading-journal`. CI authenticates
   with the built-in `GITHUB_TOKEN` (`packages: write`) — no extra secret.
3. **CI backend scope = standard.** `ruff check` + `mypy --strict` + `pytest` +
   the §8.1 **codegen freshness gate**. Frontend `npm run build` is an **optional
   job** (non-blocking is acceptable for V1; see §4.4). **Postgres parity
   (§8.2) is NOT in this phase** — it stays a pre-deploy checklist item.
4. **Single-container SPA model.** FastAPI mounts the built `dist/` at `/`; the
   API keeps the `/api/*` prefix; `/docs` + `/openapi.json` stay at root. SQLite
   remains the V1 runtime DB (Postgres path stays additive/offline).
5. **Walkthrough = standalone bilingual doc.** `docs/walkthrough.md` +
   `docs/walkthrough.zh.md`, linked from v1-release-plan §8.3 — not inlined into
   the release plan, not folded into the repo README.
6. **Execution order = A → C → B.** Build the image manually → walk through it by
   hand → automate that same build as CI. §4 (Part B) is revisited last.
7. **Static serving = plain catch-all.** One GET route: serve the requested file
   if it exists, else return `index.html` (let the SPA router take over). Plus two
   guards: an unmatched `/api/*` path returns a real **404** (not the SPA shell),
   and a **path-traversal** check keeps reads inside `dist/`. No separate `/assets`
   mount — the catch-all already covers `assets/` and root files (`favicon.svg`,
   `icons.svg`).
8. **uv: build-time only.** Build-time `uv sync --frozen --no-dev
   --no-install-project` installs third-party deps into `/app/.venv`; the
   **runtime image calls `uvicorn` directly and contains no `uv`** (smaller,
   deterministic startup — `uv run` would re-check/sync the env on boot). The
   project package resolves via `PYTHONPATH=/app/src` (matches alembic's
   `prepend_sys_path = src`), not installed into the venv.
9. **Non-root via compose, not the Dockerfile.** No fixed `USER` in the image;
   `docker-compose.yml` sets `user: "${PUID:-1000}:${PGID:-1000}"` so the process
   runs as the host user, and `/data` is a **bind mount** (`./data:/data`) — the
   SQLite file is host-owned and backup-friendly (replaces the v0.1 named volume).
10. **Ops defaults.** compose `healthcheck` (`python urllib` → `/api/health`) +
    `restart: unless-stopped`; images tagged by version (no digest pinning); one
    container serves both SPA and API — **no nginx / reverse proxy** (HTTPS
    termination, if ever needed, lives on the host outside the container).

## 2. Scope

### In scope (this plan)

- **A.** Multi-stage `Dockerfile`, `.dockerignore`, SPA static-mount + client-side
  fallback in `main.py` (config-gated so dev without a build still boots), a
  container entrypoint that runs `alembic upgrade head` before uvicorn, and a
  `docker-compose.yml` for dev/prod parity (host-user + bind-mounted `./data` + `.env`).
- **B.** `.github/workflows/ci.yml` with: `backend-quality` (ruff/mypy/pytest),
  `codegen-freshness` (boot backend → `npm run codegen` → `git diff --exit-code`),
  optional `frontend-build`, and `docker-image` (build always; push to GHCR only
  on `main`).
- **C.** `docs/walkthrough.md` + `.zh.md` covering every primary V1 flow, with a
  "start the app" preamble (dev mode + docker mode) and per-flow steps + expected
  results. v1-release-plan §8.3 expanded to point at it.

### Explicitly NOT in scope (deferred)

- **Postgres-in-CI / parity matrix** (§8.2) — pre-deploy checklist, not F6.
- **HTTPS / TLS termination** — handled by a host reverse proxy outside the container.
- **Multi-instance / horizontal scaling / external session store.**
- **Postgres-in-container** — SQLite remains the V1 runtime.
- **Playwright / Vitest** — frontend e2e/unit still deferred (V1.x).
- **Semantic-version release automation / changelog bots / GitHub Releases** — the
  `docker-image` job tags by branch + SHA; tag-driven semver releases are a V1.x
  nicety (mentioned in §10, not built here).
- **Secret management beyond `.env` / GitHub Actions secrets** (no Vault, etc.).

## 3. Part A — Docker image build

### 3.1 Multi-stage `Dockerfile` (repo root)

Three stages keep the runtime image small (no Node, no build toolchain, no dev
deps). The frontend build does **not** need a running backend — `src/api/schema.d.ts`
is committed, so `vite build` is self-contained.

```dockerfile
# syntax=docker/dockerfile:1

# --- Stage 1: frontend builder -------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
# .npmrc (legacy-peer-deps=true) must be copied before `npm ci`.
COPY frontend/package.json frontend/package-lock.json* frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build            # vue-tsc -b && vite build -> /app/frontend/dist

# --- Stage 2: backend deps (uv) ------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend-deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# Install only runtime deps into /app/.venv (no dev group).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- Stage 3: runtime ----------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    DATABASE_URL=sqlite+aiosqlite:////data/app.db
WORKDIR /app
COPY --from=backend-deps /app/.venv /app/.venv
COPY backend/src/ ./src/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend /app/frontend/dist/ ./static/
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    mkdir -p /data
ENV PYTHONPATH=/app/src
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "trading_journal.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Confirmed (2026-05-30 discussion) — both v0.1 open items closed:**
- `frontend/package-lock.json` **is** committed (90 KB, git-tracked) — the v0.1
  "no lockfile" worry was a mis-check on my part. `npm ci` works as-is; no change.
- **uv:** keep `uv sync --frozen --no-dev --no-install-project` in the deps stage
  and **invoke `uvicorn` directly at runtime (no `uv` in the runtime image)**. The
  project resolves via `PYTHONPATH=/app/src` (consistent with alembic's
  `prepend_sys_path = src`); not installed into the venv, which keeps the
  dependency layer cached independently of source churn.

### 3.2 SPA static mount + client-side fallback (`main.py` + `config.py`)

The rule is just **"serve what exists, else the SPA shell"**: a single GET
catch-all returns the requested file if it's in `dist/`, otherwise `index.html`
(so the client-side router handles deep links like `/positions/42` on refresh).
It is registered **after** the API router, so `/api/*`, `/docs`, `/openapi.json`
are matched first and never reach it. Two guards harden it (decision #7): an
unmatched `/api/*` → real 404; path-traversal → kept inside `dist/`.

```python
# config.py — add one field
static_dir: str | None = None   # set to the built dist/ path in the container

# main.py — at the end of create_app(), before `return app`
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse

static_dir = settings.static_dir
if static_dir and Path(static_dir).is_dir():
    dist = Path(static_dir).resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Anything reaching here is an unmatched GET — i.e. a client-side route —
        # because /api/*, /docs and /openapi.json were registered earlier and win.
        # Guard #2: an unmatched /api/* path is a real 404, not the SPA shell.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        # Guard #3: serve a real file only if it exists AND stays inside dist
        # (block ../../etc/passwd-style traversal). resolve() collapses '..'.
        candidate = (dist / full_path).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return FileResponse(candidate)
        # Otherwise it's a client-side route → hand back the SPA shell.
        return FileResponse(dist / "index.html")
```

No separate `/assets` mount is needed — the catch-all serves `assets/*` and the
root files (`favicon.svg`, `icons.svg`) the same way. `FileResponse` still sets
`Content-Type` / `Last-Modified` / ETag and supports Range, plenty for a SPA's
static payload. Config-gated: when `STATIC_DIR` is unset (local dev with Vite on
:5173) the whole block is skipped and the dev proxy keeps working. The catch-all
is GET-only, so it never shadows API POST/PATCH/DELETE.

### 3.3 Container entrypoint (`backend/docker-entrypoint.sh`)

```sh
#!/bin/sh
set -e
alembic upgrade head      # idempotent; brings /data/app.db to head
exec "$@"                 # hand off to CMD (uvicorn)
```

Runs migrations against the bind-mounted SQLite before serving. `exec` keeps
uvicorn as PID 1 for clean signal handling. Because the process runs as the host
UID (compose `user:`), the host's `./data` directory must already exist and be
owned by that user before `up` — otherwise the migration can't create
`/data/app.db`. (See §3.4 and the §8 recipe.)

### 3.4 `docker-compose.yml` (repo root)

```yaml
services:
  app:
    build: .
    image: ghcr.io/t-liu93/trading-journal:dev
    user: "${PUID:-1000}:${PGID:-1000}"     # run as the host user → app.db is host-owned
    ports: ["8000:8000"]
    environment:
      COOKIE_SECRET: ${COOKIE_SECRET:?set in .env}
      COOKIE_SECURE: ${COOKIE_SECURE:-false}
      DEBUG: ${DEBUG:-false}
      DATABASE_URL: sqlite+aiosqlite:////data/app.db
      STATIC_DIR: /app/static
    volumes:
      - ./data:/data                          # bind mount → back up app.db from the host
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').getcode()==200 else 1)"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s
    restart: unless-stopped
```

- **`user:`** runs the container as the host UID/GID (default 1000 — your user),
  so the SQLite file written into the bind mount is owned by you, not root.
- **`./data:/data` bind mount** puts `app.db` on the host for direct backup.
  **Gotcha:** create `./data` (owned by you) *before* `up` (`mkdir -p data`) — else
  Docker creates it as root and the UID-1000 process can't write, so the migration
  fails. The runtime image still `mkdir -p /data` as a fallback for a plain
  `docker run` without a bind mount.
- **`healthcheck`** hits `/api/health` via `python -c urllib` (the slim image has
  no curl/wget but always has python). **`restart: unless-stopped`** survives host
  reboots.
- `.env` supplies `COOKIE_SECRET` (the one mandatory secret); `COOKIE_SECURE` must
  be `true` once behind HTTPS.

### 3.5 `.dockerignore` + env notes

`.dockerignore` excludes `node_modules`, `.venv`, `**/dev.db`, `.git`, test caches,
`docs/`, `review-notes/`, and the host `data/` dir — keeps build context small and
avoids leaking the dev DB or local data.

`.env.example` gains a short "Docker / production" block documenting `STATIC_DIR`,
`PUID`/`PGID` (host user for the container; default 1000), the `./data` bind mount
+ `/data/app.db` path, and the `COOKIE_SECURE=true`-behind-HTTPS rule.

## 4. Part B — CI/CD (GitHub Actions)

Single workflow `.github/workflows/ci.yml`. Triggers: `push` to `main` and
`refactoring/rebuild`, and `pull_request` targeting `main`. Default
`permissions: contents: read`; the `docker-image` job elevates to
`packages: write`.

### 4.1 `backend-quality` job

- `actions/checkout`.
- `astral-sh/setup-uv` (with cache keyed on `backend/uv.lock`).
- `uv sync --frozen` (working-directory `backend`).
- `uv run ruff check .`
- `uv run mypy --strict src` (mypy config already in `pyproject.toml`).
- `uv run pytest` (406 tests; `asyncio_mode=auto` already configured).

### 4.2 `codegen-freshness` job (§8.1 gate)

Catches "backend schema changed, `schema.d.ts` not regenerated":

1. `uv sync --frozen` + `npm ci` (frontend).
2. `uv run alembic upgrade head` against a throwaway SQLite.
3. Boot `uv run uvicorn trading_journal.main:app &`; wait for `/api/health`.
4. `npm run codegen` (hits `http://127.0.0.1:8000/openapi.json`).
5. `git diff --exit-code frontend/src/api/schema.d.ts` — fail if stale.

### 4.3 `frontend-build` job (optional, non-blocking)

- `actions/setup-node` + `npm ci` + `npm run build` (`vue-tsc -b && vite build`).
- Marked `continue-on-error: false` but kept as a separate job so a frontend-only
  breakage is legible. (Per Decision 3 it's "optional" in the sense that the
  *backend* gate is the V1 must-pass; we still run it to catch type/build breaks.)

### 4.4 `docker-image` job (build always; push on `main`)

- `needs: [backend-quality]`.
- `docker/setup-buildx-action`.
- `docker/login-action` → `ghcr.io` with `${{ github.actor }}` / `${{ secrets.GITHUB_TOKEN }}`.
- `docker/metadata-action` → tags `ghcr.io/t-liu93/trading-journal` with `sha-<short>`
  and `latest` (latest only on `main`).
- `docker/build-push-action` with `push: ${{ github.ref == 'refs/heads/main' }}`,
  GitHub Actions layer cache (`cache-from/to: type=gha`).

On non-`main` (PRs, `refactoring/rebuild`) the image is **built but not pushed** —
proves the Dockerfile stays green without polluting the registry.

## 5. Part C — Full-feature walkthrough guide

### 5.1 Form & location

`docs/walkthrough.md` + `docs/walkthrough.zh.md` (standalone bilingual, per
Decision 5). v1-release-plan §8.3 is expanded to a one-line pointer + the
acceptance checklist links here. Living user-facing doc, not a phase plan, so it
sits in `docs/` not `docs/design/`.

### 5.2 Flow coverage checklist (the acceptance script)

Every primary V1 path, in dependency order:

1. **Register → login → logout** (FastAPI Users cookie session).
2. **Account CRUD** — create / edit / archive (F1).
3. **Instrument** — browse `/instruments`; create stock / option / forex via
   `InstrumentForm`; exercise the **inline create from `InstrumentPicker`**
   (`allowCreate`, incl. the two-step option flow) (F2 + F3 Decision 1).
4. **Strategy config** — set a per-strategy exposure cap at `/settings/strategies`.
5. **Position** — create (with `InstrumentPicker`), edit, detail page across all
   four tabs: **Overview** (manual fields + frontend-derived values), **Meta**
   (wheel funding/loan/interest, pmcc LEAP picker), **Plan** (append a TradePlan
   revision), **Trades** (placeholder → live after step 6) (F3).
6. **Trade entry** — single trade; then the **Custom multi-leg** form for the
   four §4.5.2 events: iron-condor open (4 legs), assignment (2), exercise (2),
   expiration (1); confirm the pattern badges render on the Trades tab (F4).
7. **Dashboard** — per-currency PnL cards, open/closed tables, the monthly
   realized-PnL chart, win-rate gauge (F5).
8. **Delete paths** — position 409-when-attached; trade soft-delete +
   `?include_archived=true`.

### 5.3 Document structure

- **0. Prerequisites & start the app** — two subsections: *Dev mode* (`uv run
  uvicorn … --reload` + `npm run dev`, proxy) and *Docker mode* (`docker compose
  up` + first-run `COOKIE_SECRET`). One screenshot/cast slot per major screen
  (placeholders acceptable in v0.1).
- **1–8.** One section per flow above: numbered steps, the exact field values to
  type, and the **expected result** after each (so it reads as an acceptance
  script as well as a tutorial).
- **Appendix** — the §4.5.2 event→rows cheat-sheet (which legs to enter for each
  multi-leg event), cross-linked to [data-model.md §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping).

## 6. Files

**Created**
- `Dockerfile`, `.dockerignore`, `docker-compose.yml` (repo root)
- `backend/docker-entrypoint.sh`
- `.github/workflows/ci.yml` (Part B, built last)
- `docs/walkthrough.md`, `docs/walkthrough.zh.md`

**Modified**
- `backend/src/trading_journal/main.py` (SPA catch-all + `/api` 404 + traversal guard)
- `backend/src/trading_journal/config.py` (`static_dir` setting)
- `.env.example` (Docker/prod block)
- `docs/design/v1-release-plan.md` + `.zh.md` (§6.5 filename settled; §8.1 → CI
  shipped; §8.3 → walkthrough link; status/changelog)
- `docs/design/frontend-expansion-plan.md` + `.zh.md` (§3 F6 row → done; changelog)
- backend tests: a small `test_spa_fallback.py` asserting (a) `/api/*` still routes,
  (b) unknown GET returns `index.html` when `static_dir` set, (c) mount skipped when unset.

## 7. Phased plan

Execution order **A → C → B** (revised with the user 2026-05-30): build the image
by hand, walk through it manually to confirm it works end-to-end, then automate
that same build as CI. Each sub-step is independently shippable.

- **F6.A — Docker image (now).** `config.static_dir` + `main.py` catch-all fallback
  (+ `/api` 404 + traversal guard) + a small SPA test → multi-stage `Dockerfile`
  + entrypoint + `.dockerignore` + `docker-compose.yml` (host-user + bind-mounted
  `./data` + healthcheck + restart). *Acceptance:* `mkdir -p data` then
  `docker compose up --build` serves the SPA at `/` and the API at `/api/*`;
  deep-link refresh works; `./data/app.db` is created on the host owned by you and
  survives a restart.
- **F6.C — Walkthrough (next).** Manually run every §5.2 flow against the running
  container; write `docs/walkthrough.md` + `.zh.md` recording steps + expected
  results. *Acceptance:* a fresh reader goes register → dashboard without reading
  code; every flow covered; then mark v1-release-plan §8.3 done.
- **F6.B — CI/CD (last).** `.github/workflows/ci.yml` (§4) automates exactly the
  build proven by hand in F6.A. *Acceptance:* a PR runs backend-quality +
  codegen-freshness + frontend-build + docker build (no push); merge to `main`
  pushes `ghcr.io/t-liu93/trading-journal:latest`.

## 8. Manual verification recipe

```bash
# A — build + run locally (do this first)
mkdir -p data                 # host dir for the bind mount, owned by you (UID 1000)
cp .env.example .env          # set a real COOKIE_SECRET
docker compose up --build
# -> http://localhost:8000          (SPA)
# -> http://localhost:8000/docs     (API still there)
# -> http://localhost:8000/positions then refresh -> still the SPA (no 404)
# -> ./data/app.db exists on the host, owned by your user
docker compose down && docker compose up   # data persists via the ./data bind mount

# C — the walkthrough is itself the acceptance run-through (see §5.2)

# B — last: CI mirrors the above; optional local dry run with `act`:
#     act pull_request -j backend-quality
```

## 9. Risks & considered alternatives

- **Static serving.** Chose a plain GET catch-all ("serve the file if it exists,
  else `index.html`") over `StaticFiles(html=True)` (which 404s on deep-link
  refresh). Registered after the API router so it can't shadow `/api/*` or `/docs`.
  Two guards close the gaps: `/api/*` → real 404 (not the shell), and a traversal
  check (`is_relative_to(dist)`) blocks reads outside `dist/`.
- **uv at runtime.** Runtime invokes `uvicorn` directly with **no `uv` in the
  image** — smaller and deterministic (`uv run` would re-check/sync the env on
  boot). uv is used only in the build stage (`uv sync`). The project resolves via
  `PYTHONPATH`, not installed into the venv (keeps the deps-layer cache stable).
- **Non-root + writable data.** Runs as the host UID via compose `user:`; `/data`
  is a host bind mount so `app.db` is yours and backup-friendly. *Gotcha managed:*
  `./data` must exist + be host-owned before `up` (documented in §3.4 / §8).
- **GHCR package visibility.** New GHCR packages default to private; the first push
  (in F6.B) must be followed by setting visibility + linking the package to the
  repo. One-time manual step.
- **CI on `refactoring/rebuild`.** We're not on `main` yet, so CI triggers include
  `refactoring/rebuild` to run the gate pre-merge; `latest` only publishes from
  `main` to avoid a half-baked `latest`. (Detailed in §4, built last.)

## 10. After F6 (V1 ships)

- **Archive the macros.** Per v1-release-plan §1, once F6 lands the backend +
  frontend macro roadmaps are archived and the V1 release plan becomes the record.
- **Pre-deploy checklist** (not phases): §8.2 Postgres parity run; GHCR package
  made appropriately visible; `COOKIE_SECURE=true` + real `COOKIE_SECRET` in the
  deploy env.
- **V1.x candidates** unchanged from v1-release-plan §9: PX external integrations,
  Position `archived_at` + Account unarchive, Vitest/Playwright, chart-lib
  re-eval, broker API, FX conversion, mobile/dark-mode/i18n. Plus deferred-here:
  tag-driven semver releases, Postgres-in-CI.

---

## Changelog

- **v0.2 (2026-05-30)** — Part A (Docker) hardened in a design discussion with the
  user; execution order changed to **A → C → B** (manual build → manual walkthrough
  → automate as CI; §4 revisited last). Settled: static serving = plain catch-all
  "serve the file if it exists, else `index.html`" + an `/api/*`-404 guard (#2) + a
  path-traversal guard (#3), no separate `/assets` mount; runtime invokes `uvicorn`
  directly (no `uv` in the runtime image), project found via `PYTHONPATH`; non-root
  handled by compose `user: ${PUID:-1000}:${PGID:-1000}` + a host bind mount
  `./data` (backup-friendly) instead of a named volume + Dockerfile `USER`;
  `healthcheck` (`python urllib` → `/api/health`) + `restart: unless-stopped` added;
  images tagged by version (no digest pinning); confirmed single-container, no
  reverse proxy. Withdrew the v0.1 "commit a lockfile" item —
  `frontend/package-lock.json` is already committed.
- **v0.1 (2026-05-30)** — Initial F6 closeout plan. Widens F6 from "Docker wiring"
  to the V1 release-readiness bundle (A Docker image / B CI-CD / C walkthrough),
  per the three items grouped by the user on 2026-05-30. Settles: plan-first;
  GHCR registry; standard backend CI scope (ruff + mypy + pytest + codegen gate),
  optional frontend build, Postgres parity deferred; single-container SPA model;
  standalone bilingual walkthrough doc. Recommended execution order A → B → C
  (rationale: CI + walkthrough depend on the Dockerfile).
