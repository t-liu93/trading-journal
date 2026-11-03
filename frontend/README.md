# Frontend

> **English** · [中文](README.zh.md)

Vue 3 + TypeScript + Vite + Naive UI SPA. Current CI/Docker use Node 22; use the lockfile and preserve `.npmrc`. See the [development guide](../docs/development.md) for the backend's disposable HTTP environment.

## Commands

Run in `frontend/`: `npm ci`, then `npm run dev` for `http://localhost:5173`. Vite uses a strict port and proxies `/api` to `127.0.0.1:8000`. Check an occupied port's owner instead of killing unrelated processes; keep the browser hostname consistent.

`npm run build` runs vue-tsc and Vite. `npm run preview` serves built assets for inspection; API-backed verification uses the backend or [full-stack walkthrough](../docs/walkthrough.md).

## API types and verification

`src/api/schema.d.ts` is committed generated output. With the backend on port 8000, run `npm run codegen`, inspect `git diff -- src/api/schema.d.ts`, then `npm run build`. Regenerate for any OpenAPI change, including descriptions affecting output. Do not hand-edit generated types.

There are no frontend unit/E2E scripts yet; [QA-01](../docs/plan/roadmap.md) tracks meaningful coverage. A clean build does not prove browser behavior. Use synthetic data for task-specific interactions and keep manual/automated evidence separate. If a session is invalid after replacing a disposable database, clear only the test browser's cookies and log in again; do not delete real records.

The [current roadmap](../docs/plan/roadmap.md) and task cards own current scope; P/F design plans are historical.
