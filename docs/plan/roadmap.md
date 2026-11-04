# Current roadmap

> **English** · [中文](roadmap.zh.md)

## Baseline and scheduling

The implementation baseline was established on 2026-11-02; scheduling was updated on 2026-11-04 for M-MCP-01 design delivery. Existing P/F plans are historical references, not active checklists. The implementation baseline comes from source, migrations and workflow inspection, not a fresh execution of all application tests or owner runtime acceptance.

Already implemented: account/instrument/strategy configuration, Position and Trade workflows, strategy metadata, append-only plans, per-currency dashboard and account filtering, light/dark switching, generated API types, single-container Docker deployment, migrate-before-app Compose, database sessions and an automatically persisted token-signing secret.

Current verification infrastructure: backend Ruff/strict mypy/pytest, migrated isolated test databases, codegen freshness, frontend Vitest/Vue Test Utils/jsdom behavior tests and type-check/build, and conditional image builds. REL-01 still tracks release-quality/runtime gates. SQLite is supported; PostgreSQL equivalence has not been demonstrated.

**Delivered baseline:** [M-OPT-01: option selection and trade-entry improvements](milestone-option-entry.md) T1–T6 and T7 phase B are `accepted` after implementation, checks and the five-step owner walkthrough. Original milestone/R1 candidates passed independent review; later UUID-label/timezone follow-ups passed automated/browser checks and owner acceptance without separate independent review. Phase A and DOC-01 remain accepted without repeating their documentation acceptance. The owner subsequently authorized milestone commits, push and [v1.1.0 publication](../release-notes/v1.1.0.md); production deployment remains a separate action.

M-OPT-01 owns shared decisions, complete task cards and acceptance records. It covers expired-option visibility/history/pagination, primary-underlying filtering and contextual creation, FIX-01, UI-01/UI-02 and a bounded QA-01 slice. `ready` records an agreed contract, not authorization to start coding.

**Active milestone (2026-11-04):** [M-MCP-01: agent-driven trade entry](milestone-mcp-entry.md) is `ready` as a design contract. It covers Codex/Hermes queries, dedicated credentials, immutable entry previews, atomic new-Position/Trade entry and safe retries, with an explicitly configured server default entry timezone and local/remote HTTP MCP. Screenshot/model integration is deferred. After the documentation-only delivery, the owner separately authorized application implementation, delegated orchestration, checks and isolated integration verification. T1–T2 technical delivery is complete; T3 is next; no application Git writes or production deployment are authorized.

Each milestone's section 5.2 owns candidate identity and separate implementation, automated-check, independent-review and owner-acceptance records. M-MCP-01 T7 phase A is documentation delivery; it does not establish application or runtime acceptance.

## Work queue

Priority is an ordering recommendation, not authorization. P1 = data correctness; P2 = workflow/quality; P3 = requirement clarification or optional expansion. Queue state is maintained here; a linked task card owns its detailed contract and evidence.

| ID | Priority | State | Scope / next action |
|---|---|---|---|
| [M-MCP-01](milestone-mcp-entry.md) | P2 | in-progress | T7 phase A preserved; T1–T2 implementation/checks/independent review complete; T3 next; owner acceptance pending |
| DOC-01 | P2 | accepted | Documentation handoff accepted on 2026-11-03 with additional manual review omitted; prior targeted checks passed; no independent review or runtime walkthrough claimed |
| [INS-01](milestone-option-entry.md#t3) | P2 | accepted | Milestone slice checks, independent review and owner expiry/pagination walkthrough passed |
| [INS-02](milestone-option-entry.md#t4) | P2 | accepted | Original task/R1 independently reviewed; label follow-up checked; owner steps 3/4 accepted, follow-up not separately reviewed |
| [FIX-01](tasks/FIX-01.md) | P1 | accepted | Original task independently reviewed; timezone follow-up checks/browser and owner step 5 passed, follow-up not separately reviewed |
| [UI-01](milestone-option-entry.md#t5) | P2 | accepted | Milestone slice implementation, checks, independent review and owner step 4 passed |
| [UI-02](milestone-option-entry.md#t6) | P2 | accepted | Milestone slice implementation, checks, independent review and owner steps 3/4 passed |
| UI-03 | P2 | needs-design | Suggest capital/risk/reward from strategy inputs; define formulas, units and manual override |
| UI-04 | P2 | needs-design | Prefill multi-leg entries, especially Iron Condor; define templates without changing recorded intent |
| UI-05 | P3 | needs-clarification | Filtering requests clarified and assigned to INS-01/INS-02; other kind/display complaints remain unclarified |
| [QA-01](milestone-option-entry.md#t1) | P2 | accepted | Only this milestone slice accepted; remaining ROI/grouping/failure-recovery coverage stays deferred |
| REL-01 | P2 | proposed | Gate tag publication on exact-source quality checks and runtime image validation; separate design required |
| [MOPT-DOC](milestone-option-entry.md#t7) | P2 | accepted | Phase A documentation acceptance retained; phase B integration/original-candidate review and five-step owner walkthrough passed |

Original reports and the 2026-06-02 incident remain in [triage](../triage/improvements.md). Work outside a milestone needs a bounded card before implementation; do not treat this queue as an approved implementation batch. M-OPT-01 deferred atomic Position+first-Trade creation; M-MCP-01 now plans that capability only for MCP entry. Migrating the existing website creation flow and an audited closed-record correction path remain deferred.

## Deferred product directions

External instrument lookup, quotes/unrealized P&L, FX conversion, broker/CSV import, OAuth/MFA/audit expansion, Position archiving, Account unarchive, labels/Greeks, i18n and mobile adaptation remain unscheduled directions. Define user need, data sources and acceptance before planning them. Dark mode and codegen CI are already implemented and are not deferred items.

Screenshot extraction and an in-app model connection were discussed on 2026-11-04 and explicitly deferred in favor of MCP first. MCP credential provenance is a bounded part of M-MCP-01, not completion of general audit expansion; direct Bearer setup does not implement OAuth.

## State and acceptance

Queue states: `proposed`, `needs-design`, `needs-clarification`, `ready`, `in-progress`, `in-review`, `implemented`, `accepted`, `blocked`. `ready` means the contract is agreed; execution still follows the user's requested scope. Record a blocker and the decision needed when blocked.

For every implementation, separately record implementation, automated checks, independent review, and owner acceptance, with candidate identity and skipped items. An implemented task with passing checks may still await review or owner walkthrough. Do not reconstruct old acceptance claims from historical test counts.

Update the task and this concise queue together; do not also update historical macro-plan status. See [development workflow](../development.md) and [task template](task-template.md). Task IDs are stable; UI-01–UI-05 preserve the five original frontend requests.

## Documentation organization record

DOC-01 is documentation/meta work, not completion of any queued bug or feature. Completed on 2026-11-02: documentation map, concise agent rules, development guide, roadmap, task template, FIX-01 draft, preserved triage, history notices, README entry points and isolated walkthrough. Local links/anchors, bilingual structure/commands, shell syntax, historical-content preservation, whitespace, symlink and ignore boundaries passed. The walkthrough Compose configuration was rendered and checked against isolated mounts, source context, loopback binding, HTTP cookies and migrate-before-app dependency. No container was built or started; application tests/builds and independent review were not performed. On 2026-11-03 the owner accepted the documentation handoff without further manual document review and requested status closure, commit and push. This accepts documentation with that omission; it does not establish runtime walkthrough or application acceptance.
