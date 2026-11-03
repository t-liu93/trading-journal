# AGENTS.md · Trading Journal

> **English** · [中文](AGENTS.zh.md)

Stable repository rules for coding agents. `CLAUDE.md` links to this file. Explicit user instructions take precedence over repository conventions. Keep commands, progress, and execution evidence in the documents below.

## Read first

- [Documentation map](docs/index.md): current guidance versus historical records.
- [Current roadmap](docs/plan/roadmap.md): the scheduling and progress entry point. Read the relevant task card before implementing; a proposal is not an approved task.
- [Development guide](docs/development.md): architecture, domain contracts, commands, verification, review, and acceptance.
- [Task-card template](docs/plan/task-template.md): scope, dependencies, contracts, checks, and reviewer focus.
- [Walkthrough](docs/walkthrough.md): disposable full-stack environment and user checks.
- [Triage](docs/triage/improvements.md): original symptoms and requirement history; scheduling lives in the roadmap.

P/F plans under `docs/design/` are historical planning records. Their status labels, commands, and test counts do not describe current progress. Use current source, migrations, tests, and configuration to establish implemented behavior, and the agreed task card to establish intended changes. Surface material disagreements before changing a domain contract.

## Project constraints

- Self-hosted, single-user journal; FastAPI + async SQLAlchemy/Alembic + Vue 3/TypeScript. SQLite is the supported default; PostgreSQL portability is unverified. Business routes use `/api/*`; OpenAPI is `/openapi.json`.
- Separate ORM models from API schemas. Reusable business rules and authoritative financial calculations belong in backend `services/`, using `Decimal` and existing database precision. Frontend previews and display-only metrics are allowed. Keep currencies separate without an explicit conversion design.
- Enforce ownership server-side, including Trade ownership through Position; another user's record returns 404. Instruments are shared reference data with natural-key get-or-create semantics.
- Preserve Trade archival, exclusion of archived trades from calculations, closed-position write locks, frozen realized P&L, append-only TradePlan history, and atomic multi-leg writes. The known `opened_at` defect is not an intended invariant. Lifecycle/correction changes require an agreed contract and regression coverage.
- Evolve shipped schemas through new Alembic migrations. Never hand-edit generated `frontend/src/api/schema.d.ts`; regenerate after OpenAPI changes, including descriptions that affect output.

## Work and review

- Single-agent work is the default. Start subagents or automated implementation/review/repair only when explicitly requested. If an orchestration skill is invoked, read its current instructions; do not duplicate its loop, model settings, or authorization rules here. Use actual harness controls and never claim unsupported model switches.
- Complete the requested scope in small, reviewable steps. Preserve unrelated work, resolve routine choices autonomously, and ask only when a missing decision materially changes correctness or scope.
- Ordinary reviews may use a relevant brief to locate scope. Independent blind reviews use a fresh context with the original task/design and full candidate diff; do not supply implementation/fix reports, process chats, or desired verdicts. Rereview may additionally receive the previous review report and repair delta under the agreed workflow. Reviewers inspect source and independently verify relevant checks.
- Findings block completion only for a violated acceptance criterion, a reproducible defect, or a realistic security/data/compatibility risk. Give evidence, trigger, consequence, and a concrete correction. Keep optional improvements outside the repair scope.
- Verify proportionately using the development guide. Review never replaces tests. Report passed, failed, and unrun checks accurately; distinguish implementation, automated verification, independent review, and human acceptance.
- Keep temporary reports in ignored `development-notes/<run-id>/`; retain existing local `review-notes/` as history. Record exact commit boundaries or a reproducible snapshot including relevant untracked files. Never claim review or acceptance that did not occur.

## Data and Git boundaries

- Verify and walk through with disposable databases, configuration, containers, and synthetic data. Never overwrite `.env`, modify real trading records, stop existing deployments, or migrate live databases incidentally. Track and clean up only resources created for the task.
- Local notes stay outside Git and Docker build contexts; never force-add them. Stable plans and concise acceptance status belong in `docs/`; detailed execution evidence stays local.
- Use English Conventional Commits without AI attribution. Commit, push, publish/tag, and history rewriting require explicit action-specific authorization. Implementation or orchestration alone is not Git authorization. When authorized, keep one commit per atomic task and squash only its unpublished fixups; published history requires separate authorization.

## Documentation maintenance

- Reply in the user's language. Shared guidance is English-first with a semantically matching Chinese mirror updated in the same change. Use `.zh.md` for new pairs; preserve the root README's `docs/README_zh.md` mirror. Link language pairs below H1 and prefer same-language links.
- Triage and local notes may remain Chinese. Documentation-only work needs targeted checks, not application tests or image builds unless executable behavior/configuration also changes.
- Keep this file concise and stable. Maintain current task state in the roadmap/task card; omit milestone progress, test totals, machine-specific paths, and fixed model versions.
