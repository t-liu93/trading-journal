# Current roadmap

> **English** · [中文](roadmap.zh.md)

## Baseline and scheduling

As of 2026-11-02, this is the current scheduling entry point. The existing P/F plans are historical references, not active checklists. This baseline comes from source, migrations and workflow inspection, not a fresh execution of all tests or owner acceptance.

Already implemented: account/instrument/strategy configuration, Position and Trade workflows, strategy metadata, append-only plans, per-currency dashboard and account filtering, light/dark switching, generated API types, single-container Docker deployment, migrate-before-app Compose, database sessions and an automatically persisted token-signing secret.

Current verification infrastructure: backend Ruff/strict mypy/pytest, migrated isolated test databases, codegen freshness, frontend type-check/build and conditional image build. Frontend automated behavior tests and release-quality/runtime gates remain gaps. SQLite is supported; PostgreSQL equivalence has not been demonstrated.

**Current scope:** DOC-01 documentation organization is implemented and awaits owner acceptance. No application implementation, delegation, deployment, release or Git publication is started by this roadmap. FIX-01 is the recommended next design to confirm.

## Work queue

Priority is an ordering recommendation, not authorization. P1 = data correctness; P2 = workflow/quality; P3 = requirement clarification or optional expansion. Queue state is maintained here; a linked task card owns its detailed contract and evidence.

| ID | Priority | State | Scope / next action |
|---|---|---|---|
| DOC-01 | P2 | implemented | Documentation organization complete; targeted checks passed; independent review not requested; owner acceptance pending |
| [FIX-01](tasks/FIX-01.md) | P1 | proposed | Maintain Position opening dates from active fills; confirm lifecycle/empty-set policy before implementation |
| UI-01 | P2 | proposed | Display each Trade's notes beside its row; synthetic multi-leg examples and layout acceptance |
| UI-02 | P2 | proposed | Improve First Trade labels/help placement; desktop/narrow-width acceptance |
| UI-03 | P2 | needs-design | Suggest capital/risk/reward from strategy inputs; define formulas, units and manual override |
| UI-04 | P2 | needs-design | Prefill multi-leg entries, especially Iron Condor; define templates without changing recorded intent |
| UI-05 | P3 | needs-clarification | Clarify instrument types/display complaints against the existing compact option codes |
| QA-01 | P2 | proposed | Meaningful tests for frontend date/ROI, cash-flow preview, grouping and failure recovery; choose minimal tooling |
| REL-01 | P2 | proposed | Gate tag publication on exact-source quality checks and runtime image validation; separate design required |

Original reports and the 2026-06-02 incident remain in [triage](../triage/improvements.md). Later UI/QA/release work needs a bounded card before implementation; do not treat this queue as an approved batch.

## Deferred product directions

External instrument lookup, quotes/unrealized P&L, FX conversion, broker/CSV import, OAuth/MFA/audit expansion, Position archiving, Account unarchive, labels/Greeks, i18n and mobile adaptation remain unscheduled directions. Define user need, data sources and acceptance before planning them. Dark mode and codegen CI are already implemented and are not deferred items.

## State and acceptance

Queue states: `proposed`, `needs-design`, `needs-clarification`, `ready`, `in-progress`, `in-review`, `implemented`, `accepted`, `blocked`. `ready` means the contract is agreed; execution still follows the user's requested scope. Record a blocker and the decision needed when blocked.

For every implementation, separately record implementation, automated checks, independent review, and owner acceptance, with candidate identity and skipped items. An implemented task with passing checks may still await review or owner walkthrough. Do not reconstruct old acceptance claims from historical test counts.

Update the task and this concise queue together; do not also update historical macro-plan status. See [development workflow](../development.md) and [task template](task-template.md). Task IDs are stable; UI-01–UI-05 preserve the five original frontend requests.

## Documentation organization record

DOC-01 is documentation/meta work, not completion of any queued bug or feature. Completed on 2026-11-02: documentation map, concise agent rules, development guide, roadmap, task template, FIX-01 draft, preserved triage, history notices, README entry points and isolated walkthrough. Local links/anchors, bilingual structure/commands, shell syntax, historical-content preservation, whitespace, symlink and ignore boundaries passed. The walkthrough Compose configuration was rendered and checked against isolated mounts, source context, loopback binding, HTTP cookies and migrate-before-app dependency. No container was built or started. Application tests/builds were not run for this documentation/meta change. No independent review or owner walkthrough is claimed; acceptance remains pending.
