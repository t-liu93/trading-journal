# M-OPT-01 · Option selection and trade-entry improvements

> **English** · [中文](milestone-option-entry.zh.md)

- Design: the owner confirmed this design and product scope on 2026-11-03; the contract is `ready`.
- Authorization updated on 2026-11-03: documentation/status updates, commit and push. The owner accepted documentation delivery without additional manual document review. Application implementation has not started; implementation, delegation, release/tag publication and deployment are not authorized by this request.
- Scheduling: [current roadmap](roadmap.md). This document owns shared decisions, atomic task cards and acceptance records.
- Execution rules: [development guide](../development.md), [agent rules](../../AGENTS.md). Historical P/F plans and the original conversation are not needed to determine this milestone's contract.

## 1. Goals, baseline and scope

### 1.1 Goal

As records accumulate, expired options and options on other stocks should stop crowding everyday candidate lists. After selecting a Primary Instrument, the user can select related contracts directly. Also maintain opening-date consistency after Trade changes and improve Trade notes and entry-form readability.

Typical result: select AAPL as primary → see AAPL's unexpired options by default → create a missing contract without selecting its underlying again → clearly associate notes with their Trade → see the opening date update after backfill or archival.

### 1.2 Current evidence

Source, tests, configuration and documentation were inspected at baseline commit `eecb842ac020b2e5bdd5c247b727cc18f888b7ae`. This identifies the design baseline, not an implemented candidate. This documentation delivery did not run application tests, builds or a production reproduction.

- Instruments already have option expiry dates and exact `underlying_id` references.
- Instrument listing supports kind, symbol prefix and a result limit, defaulting to 50, without pagination.
- First Trade and subsequent Add Trade flows do not pass Primary Instrument context.
- The PMCC LEAP picker only restricts kind to option; the backend validates the underlying against the Position's primary instrument.
- Position opening dates do not follow subsequent Trade creation/archival; closing dates are derived from active fills.
- Trade notes appear below the grouped table; the frontend has no behavior-test tooling or scripts.

[Historical incident](../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护): the 2026-06-02 INTC Wheel Position required a manual opening-date correction and archived-record cleanup. Realized P&L already excluded archived fills correctly. This milestone fixes application behavior and does not repeat that database intervention.

### 1.3 Tasks and boundaries

| Task | Deliverable |
|---|---|
| [INS-01 / T3](#t3) | Hide expired options by default, historical access and necessary list pagination |
| [INS-02 / T4](#t4) | Primary-instrument filtering and underlying context for contract creation |
| [FIX-01 / T2](#t2) | Opening-date maintenance, close-date ordering and UI refresh |
| [UI-01 / T5](#t5) | Notes immediately beside their corresponding Trade |
| [UI-02 / T6](#t6) | First Trade and shared leg-form layout |
| [QA-01 milestone slice / T1](#t1) | Behavior-test tooling, milestone tests and CI integration |
| [MOPT-DOC / T7](#t7) | Bilingual documentation, scheduling and integration acceptance records |

Excluded: strategy capital/risk/reward derivation; trade templates or automatic action/quantity/price entry; server-atomic Position+first-Trade creation; automatic closing, reopening, closed-Trade corrections or historical backfill; Instrument deletion/archival or external lookup; complete mobile adaptation, comprehensive frontend coverage or release-gate redesign; Git commits, pushes, releases or production deployment.

The owner confirmed the product scope, defaults and this design. Section 2 fixes the technical details needed for implementation. Recheck the worktree before implementing and preserve unrelated changes. Surface and reconfirm material domain-contract or scope changes; the executing agent resolves routine implementation details.

## 2. Decisions and shared contracts

### D01 · Expiry is a query condition

- An option is expired when `expiry < current UTC date`; expiry-day contracts remain visible and are hidden by default the following day.
- The backend decides. This date-level filter is not an exchange's real-time tradability assessment.
- Do not add exchange calendars, intraday cutoff times or user-timezone configuration.
- Do not add archival state, delete contracts or modify related Trades.
- Provide a replaceable backend current-UTC-date function so tests can freeze time.

### D02 · Default hiding and historical access

- Instruments, Primary Instrument, Trade Instrument and PMCC LEAP pickers request unexpired contracts by default.
- Provide a nearby `Show expired options` switch. Enabling it includes expired options while retaining other filters.
- Retain the switch only for the current page/form session, without database or localStorage persistence. Reopening a Trade form restores default hiding.
- Selected contracts, historical Positions/Trades and PMCC metadata still display full labels through ID lookup.
- Historical contracts fetched for display label the current value only; they must not enter the ordinary candidate list.
- Turning the switch off does not clear an explicitly selected historical contract. Selecting it again after clearing requires enabling the switch.

### D03 · Filter before limiting results

Extend `GET /api/instruments`; keep the response as `InstrumentRead[]`.

| Parameter | Type/default | Meaning |
|---|---|---|
| `kind` | Existing optional enum | Retained |
| `q` | Existing optional string | Retain symbol-prefix search |
| `limit` | Integer, default 50, range 1–200 | Retained |
| `offset` | Integer, default 0, minimum 0 | New pagination offset |
| `include_expired` | Boolean, default true | false excludes expired options |
| `option_underlying_id` | Optional UUID | Restrict the underlying of option rows only; other kinds are unaffected |

- Preserve older clients with API default `include_expired=true`; product list entry points explicitly send `false`.
- Combining `kind=option` and `option_underlying_id` returns only that underlying's options. An unmatched underlying yields no option results; malformed UUIDs return 422.
- Apply every filter before ordering and pagination. Keep symbol/creation-time ordering and append ID for deterministic ties.
- Preserve ID lookup and get-or-create contracts. Do not introduce backend prohibitions on historical Instrument/Trade writes.

Minimal pagination: show 50 rows per page, request 51 and use the extra row only to detect another page; advance offsets by 50. Provide previous/next on the management page and load-more in pickers. Reset pagination when search, kind, expiry or underlying changes; deduplicate appended rows by ID. Do not add totals or full downloads. Concurrent contract creation does not imply cross-request snapshot consistency.

### D04 · Associate by underlying ID

- For stock Primary Instruments use their ID; for option Primary Instruments use `option.underlying_id`.
- Apply no option-underlying condition for forex or an unselected primary instrument.
- Preserve stock and forex candidate behavior; the general Trade form must not become option-only.
- PMCC LEAP remains option-only and keeps the backend's existing check that the underlying equals the Position's primary stock ID. Show an explicit Meta-form explanation for incompatible primary instruments rather than relaxing backend validation.
- Show primary-resolution errors and retry. Suspend context-dependent selection instead of silently falling back to all options.
- Compare resolved underlying IDs: retain options for the same underlying. When the underlying changes or the primary is cleared, clear incompatible option selections and notify the user.
- Preserve quantity, price, date, costs and notes; clear incompatible Actions only under existing kind rules. This option filtering does not clear non-option legs.

### D05 · Inline creation inherits context

- With a known underlying, offer a create-option-for-current-underlying action regardless of whether search results are empty.
- Prefill underlying, currency and exchange; lock the underlying in this contextual form.
- Expiry, call/put, strike, quantity, price and Trade action remain user inputs.
- General Instrument management creation keeps manual underlying selection.
- Explicit creation of an expired contract enables expired display in the current picker, explains the change, then selects the returned contract.
- Returned contracts must match the current underlying context; mismatches cannot be automatically selected.
- Preserve get-or-create deduplication and failure recovery.

### D06 · Request races and errors

- Search, kind, underlying, expiry visibility and pagination form the complete request context.
- Invalidate previous requests immediately on condition changes, including pending debounce callbacks. Late responses must not restore old candidates or loading state.
- Remove old candidates when context changes; maintain selected-value labels separately.
- Show request errors and retry, distinguish them from empty results, and preserve loaded pages after load-more failure for retry at the same offset.
- Clear timers on unmount and prevent outstanding requests from writing state afterward.
- Query again whenever a picker opens. Midnight does not need to clear a selection being edited automatically.

### D07 · Opening date is the earliest active fill

- After successful Trade creation or archival on an open Position, use MIN(`executed_at`) among non-archived fills.
- The first active fill can replace the creation date in either direction.
- Preserve the last opening date when all fills are archived; the next fill establishes it again. An empty new Position keeps its supplied date until its first fill.
- Commit Trade changes and date maintenance together. Failed batches leave neither partial Trades nor date changes. Notes-only PATCH does not maintain dates.
- Normalize new fill timestamps to UTC before persistence and ordering, including equivalent instants with different offsets.
- Keep current SQLite storage conventions; interpret naive input as UTC. Do not guess or backfill lost timezone information in old records or broaden this into a repository-wide time refactor.

### D08 · Close ordering and historical boundaries

- On open→closed, recompute the opening date if active fills exist.
- Without an explicit closing time, use the maximum active fill time, or current UTC time for an empty set.
- Allow `closed_at == opened_at`. Return 422 for `closed_at < opened_at`, without partially saving status, dates, other PATCH fields or frozen P&L.
- Apply the same ordering check when explicitly amending an already-closed record's `closed_at`, without recomputing its opening date or frozen P&L.
- Reading or editing other permitted fields must not automatically repair or reject historical invalid dates.
- Preserve archival, closed-Trade write locks, the reopening prohibition, Decimal calculations and append-only plans.
- Do not conceal backend errors by clamping negative holding days in the UI.

### D09 · Notes and form layout

Notes: when a Trade has notes or is being edited, place a companion notes row immediately after its data row, spanning every table column and keyed by Trade ID. Remove duplicate group-bottom notes. Render plain text with preserved newlines and wrapping, never user HTML. Keep `Edit notes` in the corresponding action area and put the editor in the companion row. Enter inserts a newline; Ctrl/Command+Enter saves; provide Save/Cancel buttons. Preserve input on failure, cancel editing on read-only transition and retain archival/closed restrictions.

Forms: use labels above shared leg fields, with help and errors below. Use one column below 600px and two at wider sizes; Instrument and Notes span the full row. Validation locates the specific leg/field without losing inputs or add/remove-leg behavior. Help uses product language without exposing field names, database or server internals. This improves the affected components at narrow widths, not the entire mobile application.

### D10 · Testing and data evolution

- Use Vitest, Vue Test Utils v2 and jsdom for test execution, Vue 3 component interactions and a DOM environment. References: [Vitest](https://vitest.dev/guide/), [Vue Test Utils](https://test-utils.vuejs.org/guide/).
- Use separate test configuration to avoid rewriting generated component declarations. Lock added dependencies to versions compatible with the existing Node 22/Vite 8 project, without upgrading unrelated tooling; preserve `.npmrc`.
- `npm run test` runs once; provide a separate watch script. Do not add Playwright or a numeric coverage threshold.
- No database migration is needed. Regenerate `schema.d.ts` after OpenAPI parameter changes; never hand-edit it.
- Use synthetic data and isolated databases for all verification. Do not inspect or modify production databases.

## 3. Complete task cards

All cards share section 2 and cannot change its contract independently. Paths are relative to the repository root; proposed new application files do not exist before implementation.

Initial application-card evidence: implementation not started; automated checks not run; independent review not requested/performed; owner feature acceptance pending; no implementation candidate. After implementation, record commit boundaries or a reproducible snapshot including relevant untracked files, the local evidence directory and omissions for each card. Design approval is not implementation acceptance.

<a id="t1"></a>

### T1 · QA-01: frontend behavior-test foundation for this milestone

**Goal/evidence:** there is no frontend test script. Enable verification of filtering, context changes and failure recovery.

**Dependencies:** none; feature tests arrive with their cards.

**Files/actions:** modify `frontend/package.json` and `frontend/package-lock.json`; create `frontend/vitest.config.ts`, `frontend/tests/setup.ts` and the later cards' specs; modify `.github/workflows/ci.yml` to run tests once in existing frontend checks. Write test artifacts only to ignored directories; synchronize Git/Docker ignores if a new artifact directory is needed.

**Steps:** configure Vue compilation, jsdom, cleanup and fixed time; centralize necessary browser API shims in setup; assert public interactions and API results; run tests/build after dependency installation in existing CI without changing the release workflow.

**Acceptance:**

- [ ] After `npm ci`, tests/build run and failures exit nonzero and fail the corresponding CI check.
- [ ] Timers, request mocks and system time do not leak between tests.
- [ ] Tests do not write `src/components.d.ts` or consist only of empty/mount assertions.

**Migration/walkthrough:** none; run tests and build separately, checking for unintended generated files.

**Reviewer focus:** exercise real component connections rather than mocking away the tested behavior. Completing this card does not complete the entire historical QA-01 backlog.

<a id="t2"></a>

### T2 · FIX-01: Trade and Position date consistency

**Goal/evidence:** prevent obsolete opening dates after backfill/archival and reversed opening/closing dates, based on the INTC incident and existing write paths.

**Dependencies:** none; frontend interaction tests depend on T1.

**Files/actions:**

- Modify `backend/src/trading_journal/services/positions.py` for aggregation and maintenance.
- Modify `backend/src/trading_journal/services/trades.py` to normalize new fills; place necessary shared UTC functions in new `backend/src/trading_journal/services/datetimes.py`.
- Modify `backend/src/trading_journal/api/trades.py` and `backend/src/trading_journal/api/positions.py` for transactions/validation.
- Modify `backend/tests/test_trades.py` and `backend/tests/test_positions.py`.
- Modify `frontend/src/components/PositionTradesTab.vue` to notify the parent after successful archival; create `frontend/tests/PositionTradesTab.spec.ts`.

**Steps:** add failing regressions first. Flush only after all new fills validate, maintain dates and let the route commit once. Flush archival before aggregation. Construct/validate final close dates before saving status and freezing P&L. Refresh Trades and Position after archival; refresh failure offers retry and must not misreport successful archival as failed.

**Acceptance:**

- [ ] Earlier fills move the opening date earlier; archiving the earliest uses the next fill.
- [ ] Archiving all preserves the date; replacement establishes it again; a first fill later than creation also replaces it.
- [ ] Multi-leg minimum is input-order independent; an invalid later leg rolls back Trades and dates.
- [ ] Different UTC offsets are compared on one timeline.
- [ ] Default/explicit close times, empty sets and same-instant dates satisfy D08; invalid close/amendment rejects atomically.
- [ ] Notes-only PATCH, cross-user 404 and closed locks remain; active-fill P&L and audit history are preserved.
- [ ] Archival updates dates without manual reload; fresh list/detail reads agree.

**Migration/walkthrough:** no schema migration or historical backfill; use section 4's date example.

**Reviewer focus:** flush order, rollback, UTC, historical-close boundaries and refresh events.

<a id="t3"></a>

### T3 · INS-01: expired-option filtering and historical access

**Goal/evidence:** accumulated contracts crowd candidates; current generic queries only return up to 50 by default.

**Dependencies:** T1; this card supplies T4's underlying-query capability.

**Files/actions:**

- Modify `backend/src/trading_journal/api/instruments.py`; create `backend/src/trading_journal/services/instruments.py` for date/query logic.
- Modify `backend/tests/test_instruments.py`.
- Modify `frontend/src/api/instruments.ts`, `frontend/src/composables/useInstruments.ts`, `frontend/src/views/InstrumentsView.vue` and `frontend/src/components/InstrumentPicker.vue`.
- Regenerate `frontend/src/api/schema.d.ts`; create `frontend/tests/InstrumentPicker.spec.ts` and `frontend/tests/InstrumentsView.spec.ts`.

**Steps:** implement D01–D03; add management switches/pagination/appropriate empty states; add picker switches/load-more/ID labels; implement D06; synchronize client and generated types.

**Acceptance:**

- [ ] Freeze today at 2026-11-03: hide 11-02, retain 11-03/11-04 and reveal history with the switch.
- [ ] Expiry filtering preserves stock/forex results and older-client defaults.
- [ ] More than 50 old contracts cannot crowd out active matches; more than 50 matches remain reachable through pagination.
- [ ] Search, kind, expiry, underlying and pagination compose correctly.
- [ ] Expired/off-page current values retain labels; disabling the switch keeps explicitly chosen values.
- [ ] Errors differ from empty results, stale responses cannot overwrite new context and append failures can retry.
- [ ] Queries/switches do not modify contracts or Trades.

**Migration/walkthrough:** none; use section 4's option examples.

**Reviewer focus:** filter before pagination, array-response compatibility, separation of labels/candidates and access to later pages.

<a id="t4"></a>

### T4 · INS-02: primary-instrument context and inline creation

**Goal/evidence:** leg pickers lack primary context and PMCC LEAP validates the underlying only on submission.

**Dependencies:** T1, T3.

**Files/actions:**

- Modify `PositionFormModal.vue`, `TradeEntryModal.vue`, `TradeLegRow.vue`, `PositionTradesTab.vue`, `PmccMetaForm.vue`, `InstrumentPicker.vue` and `InstrumentForm.vue` under `frontend/src/components/`.
- Modify `frontend/src/views/PositionDetailView.vue`; create `frontend/src/utils/instrumentContext.ts` for shared resolution.
- Create `frontend/tests/TradeInstrumentContext.spec.ts`, `frontend/tests/InstrumentForm.spec.ts` and `frontend/tests/PmccMetaForm.spec.ts`.

**Interfaces/data flow:** pass `primaryInstrument` plus resolution state from entry points through `TradeEntryModal` to each leg. Add optional `optionUnderlyingId` to `InstrumentPicker`. New Positions use form primary context; existing Positions use the detail's loaded primary. Connect both Add Trade entry points and the empty Trades state. Add optional `underlyingInstrument`/`lockUnderlying` to `InstrumentForm`; pass the primary to `PmccMetaForm`, retaining `kind=option`.

**Steps:** centralize stock/option/forex resolution; connect every entry point and error state; implement selection cleanup, field retention and stale-request invalidation; implement D05; replace obsolete PMCC text saying pickers do not filter.

**Acceptance:**

- [ ] AAPL primary excludes TSLA options; identical symbols with different IDs are not conflated.
- [ ] Expiry/search/pagination compose; every entry point, added leg and PMCC LEAP is covered.
- [ ] The same underlying preserves selections; changed/cleared context follows D04 and retains other fields.
- [ ] Late requests/resolution errors cannot restore global candidates.
- [ ] Creation prefills the correct underlying/currency/exchange and handles failure, duplicates and historical contracts.
- [ ] Created results cannot bypass context; PMCC backend validation is not relaxed.
- [ ] Stock, forex and atomic multi-leg capabilities remain.

**Migration/walkthrough:** no migration or expanded Trade-write contract; use section 4's context examples.

**Reviewer focus:** all entry-point connections, exact IDs, in-flight old values and creation results.

<a id="t5"></a>

### T5 · UI-01: notes immediately beside Trade rows

**Goal/evidence:** group-bottom notes obscure ownership for multi-leg or repeated-contract records.

**Dependencies:** T1; edit the shared panel sequentially after T2 and preserve its refresh behavior.

**Files/actions:** modify `frontend/src/components/PositionTradesTab.vue`; extend `frontend/tests/PositionTradesTab.spec.ts`.

**Steps:** add D09's notes/editor rows; remove old output; preserve save/cancel/archival/read-only behavior; handle long text, newlines, narrow widths and themes.

**Acceptance:**

- [ ] Single/multi-leg and repeated-contract notes have clear ownership; empty notes create no blank display row.
- [ ] Long text, newlines and HTML-like text render safely.
- [ ] Save, clear, cancel and retry retain ownership/input.
- [ ] Read-only transitions exit editing; archived rows cannot edit.
- [ ] No duplicate notes or broken order grouping/cash-flow display.

**Migration/walkthrough:** none; use repeated contracts with different notes and four-leg examples at desktop/narrow widths and light/dark themes.

**Reviewer focus:** key by Trade ID, not array position or Instrument ID; retain input on failure.

<a id="t6"></a>

### T6 · UI-02: labels, help and validation layout

**Goal/evidence:** leg forms mix inline/stacked layouts and creation help exposes field names.

**Dependencies:** T1, T4; refine the form after connecting context.

**Files/actions:** modify `frontend/src/components/PositionFormModal.vue`, `frontend/src/components/TradeEntryModal.vue` and `frontend/src/components/TradeLegRow.vue`; create `frontend/tests/TradeEntryForm.spec.ts`.

**Steps:** apply D09; place underlying/expiry/error help near its control; locate validation at the leg/field; preserve leg controls, keyboard behavior, previews and failure recovery.

**Acceptance:**

- [ ] Two desktop columns/one narrow column without obscured controls.
- [ ] Labels/help/errors are distinguishable; leg controls, Tab navigation and validation focus work.
- [ ] Errors do not clear other legs/fields.
- [ ] When Position creation succeeds but Trade creation fails, retry still reuses the original Position and existing disabled-state rules.
- [ ] Layout changes do not alter previews or submitted results.

**Migration/walkthrough:** none; enter single/four-leg examples at 1280px and 390px.

**Reviewer focus:** interaction and visual acceptance; a passing build does not establish layout quality.

<a id="t7"></a>

### T7 · MOPT-DOC: documentation and integration acceptance

**Goal:** one complete milestone contract and accurate delivery records.

**Dependencies/status:** phase A is the accepted design/status-document delivery (`MOPT-DOC`). Phase B covers application documentation and integration after T1–T6; it is `ready`, not started. Do not keep the completed documentation phase in progress or mark future application verification complete.

**Files/actions:**

- Create this EN/ZH document pair with language links below H1; modify `docs/plan/roadmap.md` and its Chinese mirror to add the milestone, INS-01/INS-02 and existing-task links.
- Modify `docs/plan/tasks/FIX-01.md` and its mirror, retaining identity/incident/history and directing detailed rules to T2 here instead of maintaining another acceptance checklist.
- Update `docs/triage/improvements.md`, preserving the incident and appending the two requests/links without rewriting historical facts.
- After application implementation, update `docs/development.md`, `docs/walkthrough.md` and their mirrors to describe delivered behavior; do not prematurely claim implementation.
- Do not update historical P/F plan progress.

**Steps/scheduling:** phase A records agreed design and unstarted implementation. INS-01/INS-02 own UI-05's clarified filtering requests; remaining UI-05 issues stay unclarified. QA-01's milestone slice is ready and uncovered work stays deferred. DOC-01 and phase A documentation are accepted with additional manual document review omitted; no runtime acceptance is inferred. Phase B later updates implementation/check/review/acceptance separately for every card.

**Acceptance:**

- [x] Phase A: both languages agree on scope, defaults, errors, dependencies and state; links/anchors resolve.
- [x] Phase A: no competing contracts; a new agent can execute without the original conversation.
- [x] Phase A: detailed local evidence stays ignored and outside Git/images.
- [ ] Phase B: update documentation for delivered application behavior and complete section 4 integration checks, accurately recording omissions and actual owner feature acceptance.

**Migration/walkthrough:** documentation stage has no data operations; application stage uses section 4's isolated environment.

**Reviewer focus:** one contract, bilingual parity and no future behavior presented as current fact; independent review only when authorized.

## 4. Verification, walkthrough and cleanup

### 4.1 Automated checks

From `backend/`:

```bash
uv sync --frozen
uv run ruff check .
uv run mypy --strict src
uv run pytest
```

From `frontend/`:

```bash
npm ci
npm run test
npm run build
```

T1 introduces `npm run test`. After API parameter changes, run existing `npm run codegen` against an isolated backend and inspect type drift/freshness; do not edit generated files manually. Change existing tests only to reflect agreed contract changes, not by removing meaningful regression assertions to obtain passing checks.

Documentation-only delivery checks links/anchors, bilingual parity and `git diff --check`; it does not establish application verification.

### 4.2 Automated scenario matrix

| Area | Required scenarios |
|---|---|
| Expiry | Yesterday/today/tomorrow, UTC boundaries, frozen time |
| Queries | Older defaults, combined conditions, filtering before limit, second page, no matches |
| Association | Different underlyings, same symbol/different IDs, stock/option Primary |
| Races | A→B primary, old debounce, expiry switch, page retry |
| Creation | Context prefill, duplicate, wrong underlying, historical contract |
| Labels | Off-page value, expired value, retaining current value after switch-off |
| Dates | Backfill, earliest/all archival, replacement, leg order, offsets |
| Atomicity | Invalid later leg/close time saves nothing partially |
| Ownership | Other-user 404, closed write locks |
| UI | Archive refresh event, note ownership, input retention, field focus |
| Existing flows | First-fill failure recovery, atomic multi-leg, cash flows, frozen P&L |

### 4.3 Isolated environment

Use the complete commands in sections 1, 2 and 4 of the [current disposable walkthrough](../walkthrough.md): a new temporary directory, separate Compose project/image, candidate source build, loopback port and explicit HTTP Cookie settings. This guide is an operational prerequisite, not a historical-plan or conversation dependency.

Before startup, verify mounts point only to the temporary database, build context identifies the candidate and the port is free. Change occupied ports rather than stopping other services. Do not use root local Compose files, `.env` or real `data/`. Build the actual image and verify migration success, health, login and SPA deep links before the feature walkthrough. Record actual commands, resource identity and cleanup locally.

### 4.4 Synthetic data and owner walkthrough

Automated tests freeze today at 2026-11-03; manual examples use yesterday/today/tomorrow relative to the actual UTC date.

**Options/filtering:**

1. Create two stocks with options on each; one stock has expired, expiry-day and future contracts.
2. Automated fixtures additionally include more than 50 old contracts and more than 50 matching contracts.
3. Management hides expired contracts by default; the switch/pagination reach historical records.
4. Select the first stock on a new Position; only its options appear. Added legs, both Add Trade entry points, empty-state entry and PMCC agree.
5. Change primary and check option cleanup/other-field retention.
6. Inline creation prefills underlying and deduplicates; historical selection/creation and saved labels work.
7. Verify basic stock/forex entry remains available.

**Dates/P&L:**

1. Create an empty Position dated D3; add a D1 buy of 10 shares at 100 and a D2 sell of 10 at 110, both with zero costs and D1<D2<D3.
2. Opening is D1 and total cash flow is 100. Archive D1: opening becomes D2. Re-enter D1: opening returns to D1.
3. Default close date is D2 and frozen P&L is 100.
4. Use another Position for archive-all, replacement and invalid explicit close time; verify batch rollback, differing offsets and closed locks through the API.

**Notes/layout:** two Trades of one contract with different notes; four legs with empty/long/multiline notes; failure/cancel/clear/read-only; forms/panels at 1280px/390px and light/dark themes.

### 4.5 Evidence and cleanup

Store evidence under ignored `development-notes/<run-id>/`, including Chinese `summary.md` and `walkthrough.md`. Record candidate, commands, outcomes, failures, omissions and limits. Clean only this run's projects, processes, images, temporary directories and browser profile. If the owner cannot walk through yet, explicitly leave acceptance pending. Independent review requires a separate request; do not automatically start subagents.

## 5. Sequence, status and remaining queue

### 5.1 Sequence

Single agent: deliver design/entry points → receive a subsequent implementation instruction → T1 → T2 → T3 → T4 → T5 → T6 → T7 integration records. Keep each step independently inspectable. Without action-specific Git authorization, do not commit; once authorized, organize commits by atomic task.

### 5.2 Completion criteria

All six implementation cards satisfy acceptance; backend quality/full tests, frontend tests/build and generated types pass; actual-image and isolated walkthrough checks complete with omissions recorded; bilingual documents/roadmap and a reproducible candidate are synchronized; no real-data mutation, implicit historical backfill or weakened closed locks. Track implementation, automation, independent review and owner acceptance separately. Mark `accepted` only after actual owner confirmation.

| Card | Implementation | Automated verification | Independent review | Owner feature acceptance |
|---|---|---|---|---|
| T1 / QA-01 slice | Not started | Not run | Not requested | Pending |
| T2 / FIX-01 | Not started | Not run | Not requested | Pending |
| T3 / INS-01 | Not started | Not run | Not requested | Pending |
| T4 / INS-02 | Not started | Not run | Not requested | Pending |
| T5 / UI-01 | Not started | Not run | Not requested | Pending |
| T6 / UI-02 | Not started | Not run | Not requested | Pending |
| T7 phase A / MOPT-DOC | Complete | Documentation checks passed | Not requested | Documentation accepted; additional manual review omitted |
| T7 phase B / application integration | Ready, not started | Not run | Not requested | Pending |

Application implementation candidate/local evidence: none yet. The documentation candidate is the M-OPT-01 documentation commit based on `eecb842ac020b2e5bdd5c247b727cc18f888b7ae`, identified by Git history for this file. Commit/push were explicitly authorized for this documentation delivery; that does not authorize later implementation or publication actions.

Documentation delivery record (2026-11-03): the owner confirmed the design, accepted the documentation handoff without further manual review and authorized status updates, commit and push. Bilingual design, README/map entry points and roadmap/FIX-01/triage updates are complete. DOC-01 and T7 phase A are accepted with the stated manual-review omission; phase B and application work remain unstarted. Targeted checks passed: local links/anchors, paired heading structure, decision/task IDs, acceptance-checklist state, identical command blocks and technical inline-code parity (apart from the translated UTC-date placeholder). Changed/new Markdown whitespace, original incident preservation and documentation-only scope were checked. Application source, dependencies, generated types and databases are unchanged. Application tests, image builds, independent review and owner feature walkthrough were not run. Git outcomes are established by the actual repository/remote operation, not by design acceptance.

### 5.3 Remaining work

Retain UI-03 parameter derivation; UI-04 multi-leg templates; remaining UI-05 kind/display requests; QA-01 ROI/grouping/failure-recovery coverage outside this milestone; REL-01 release gates; atomic Position+first-Trade creation; audited closed-record corrections; and import, quotes, FX, archival extensions, Greeks, i18n and complete mobile adaptation.
