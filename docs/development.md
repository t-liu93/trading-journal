# Development guide

> **English** · [中文](development.zh.md)

## Architecture and current contracts

Backend code is under `backend/src/trading_journal/`: `models/` for ORM persistence, `schemas/` for API validation/serialization, `services/` for reusable business logic, `api/` for HTTP orchestration, and `auth/` for authentication. Frontend code under `frontend/src/` separates API clients, composables, stores, views, components, utilities and routing.

FastAPI, async SQLAlchemy 2, Alembic, FastAPI Users, Pydantic Settings and uv support the backend; Vue 3/TypeScript, Vite, Pinia, Vue Router, Naive UI and ECharts support the frontend. SQLite is the default. PostgreSQL portability is a goal without a current verified deployment record. Business routes use `/api/*`, health is `/api/health`, and OpenAPI is `/openapi.json`. Production serves the SPA outside API/docs routes; Vite proxies `/api` to `127.0.0.1:8000`.

Preserve these contracts unless the task explicitly changes them:

- Authoritative financial values use backend `Decimal` and existing SQL `Numeric` precision. Trade cash flow is `sign(action) × price × quantity × multiplier − commission − fees`. Frontend previews, days held, ROI and annualized ROI are display-only. Keep different currencies separate.
- Enforce ownership using the authenticated user, resolving Trade through Position; return 404 for another user's resource. Instruments are shared reference data with natural-key get-or-create.
- Trade DELETE archives; sums exclude archived rows. PATCH accepts notes only; corrections to other fields on open positions require archive + replacement. Closed positions reject Trade writes and cannot be reopened. There is no supported unarchive endpoint.
- Closing freezes realized P&L. Without an explicit close time, use the latest non-archived fill, or now for an empty position. `opened_at` currently does not follow later Trade changes: [FIX-01](plan/tasks/FIX-01.md) is a proposal, not an implemented repair.
- Multi-leg Trade writes are atomic. Position + first Trade currently involves two frontend requests with partial-failure recovery, not one backend transaction.
- TradePlan is append-only, protected by revision uniqueness and retry handling. Any Trade, including archived history, or plan revision prevents Position deletion.
- Add Alembic migrations for shipped schema changes. Tests exercise a migrated template copied into an isolated database for each test.
- The automatically persisted `app_config` secret is for token signing; sessions use opaque database tokens. No operator-provided `COOKIE_SECRET` is needed.

## Commands and environments

Current CI/Docker use Python 3.12 and Node 22. Consult manifests, lockfiles, `Dockerfile` and `.github/workflows/ci.yml` when changing versions.

| Directory | Command | Purpose |
|---|---|---|
| `backend/` | `uv sync --frozen` | Locked development dependencies |
| `backend/` | `uv run ruff check .` | Lint |
| `backend/` | `uv run mypy --strict src` | Type-check |
| `backend/` | `uv run pytest` | Isolated backend tests |
| `backend/` | `uv run alembic upgrade head` | Migrate configured DB; inspect target first |
| `backend/` | `COOKIE_SECURE=false uv run uvicorn trading_journal.main:app --reload` | Local HTTP backend |
| `frontend/` | `npm ci` | Locked dependencies; preserve `.npmrc` |
| `frontend/` | `npm run dev` | Vite at `http://localhost:5173` |
| `frontend/` | `npm run build` | Type-check and production bundle |
| `frontend/` | `npm run codegen` | Generate committed types from running backend |

Use the [walkthrough](walkthrough.md) for disposable Compose verification. Templates live in `example/`; ignored root Compose files are local working copies and may point at real records. Do not overwrite or reuse them for checks. Compose runs `migrate` before `app`, preventing startup on migration failure.

For hot reload, run in `backend/`:

```bash
uv sync --frozen
export TJ_DEV_DIR="$(mktemp -d /tmp/tj-dev-XXXXXX)"
export DATABASE_URL="sqlite+aiosqlite:///$TJ_DEV_DIR/dev.db"
export COOKIE_SECURE=false
uv run alembic upgrade head
uv run uvicorn trading_journal.main:app --reload
```

In another terminal, run `npm ci` and `npm run dev` in `frontend/`. Use `localhost` consistently. Select free ports; Vite/codegen assume backend port 8000. Stop only your own processes, then remove the temporary directory created for this run. Do not reset an existing database to fix a session issue.

## Tasks, verification and acceptance

Read the [roadmap](plan/roadmap.md) and relevant contract using the [task template](plan/task-template.md). Deliver small reviewable user outcomes, including backend/frontend integration when necessary. Resolve material decisions before `ready`; a draft does not authorize implementation. Keep shared decisions, atomic steps and concise acceptance in one document pair per future milestone.

Record four separate dimensions: implementation, automated checks, independent review, and owner acceptance. Update the task record and concise roadmap row together. `implemented` is not `accepted`; explicitly record skipped paths and approved exceptions. Historical P/F plans are not additional status trackers.

| Change | Relevant verification |
|---|---|
| Backend | Ruff, strict mypy, relevant pytest; full suite for shared domain/auth/migrations; meaningful regression tests |
| Financial/lifecycle | Decimal results, ownership, archival, rollback, timestamps, empty sets; synthetic data |
| Frontend | `npm run build` and affected interactions; cover nontrivial logic as [QA-01](plan/roadmap.md) introduces suitable tests |
| OpenAPI | Regenerate `schema.d.ts`, inspect diff, build frontend; descriptions may affect output too |
| Container/startup | Real image build and affected migration/startup/SPA checks on disposable data |
| File moves/deletions | Check imports, links, Docker COPY inputs, packaging and CI references |
| Documentation | Links/anchors, bilingual parity, commands against configuration, whitespace and change scope |

Current CI provides backend lint/types/tests, codegen freshness, frontend build and conditional Docker build. Frontend unit/E2E scripts do not yet exist. Tag publishing is not dependent on full quality checks/runtime smoke tests; [REL-01](plan/roadmap.md) tracks that gap. Never claim unrun tests, an independent review that did not happen, or user acceptance without confirmation.

## Independent review and local handoff

Ordinary work stays single-agent. Start delegated orchestration only on explicit request. An invoked installed skill supplies the bounded workflow, repair limit, role configuration and run-record requirements; do not duplicate conflicting variants from other projects. Review supplements tests.

- Initial reviewer: fresh context, original task/design, full candidate diff/snapshot, exact boundaries and neutral instructions. No implementation/fix reports, process chats, preferred verdicts or defenses. Relevant source/rules and independent checks remain accessible.
- Rereviewer: may additionally receive the previous review report and repair delta; independently assess the cumulative candidate against the original contract. Fixers may read implementation and review reports.
- Block only on acceptance violations, reproducible defects or realistic security/data/compatibility risks. State location, evidence, trigger, consequence and required correction. Optional preferences do not start repair loops.
- Identify the actual candidate using base/head SHAs when committed, or a reproducible saved diff/snapshot including relevant untracked files. Do not create a commit just to obtain a boundary. Subsequent code changes invalidate coverage of the old review where affected.

Keep detailed execution evidence local in ignored `development-notes/<run-id>/`. Deliver Chinese `summary.md` and `walkthrough.md` covering scope, candidate, checks/outcomes, limitations, exact startup/actions/expected observations and cleanup. Retain any additional reports required by an invoked skill. Existing `review-notes/` remains local history. Small documentation-only work may be reported in chat; stable plans retain only concise decisions/status/acceptance.

Use isolated databases, configuration, containers and synthetic accounts. Track resources and clean up only those created for the run. Never stop an existing deployment or change real trading records for verification.

Git authorization is action-specific: implementation or delegation alone does not authorize committing, pushing, publishing/tagging or rewriting history. When authorized, the orchestrator owns shared-worktree Git mutations; no concurrent commits/rebases. Keep one commit per task, squash only that task's unpublished fixups, and preserve other tasks and published history.
