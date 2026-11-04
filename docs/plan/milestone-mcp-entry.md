# M-MCP-01 · Agent-driven trade entry

> **English** · [中文](milestone-mcp-entry.zh.md)

- Design: on 2026-11-04 the owner requested this revised design be saved with related guidance, committed and pushed. The contract was delivered as `ready`; application execution started on 2026-11-04 under a separate explicit owner request.
- Authorization: the original delivery covered documentation and its commit/push only. On 2026-11-04 the owner separately authorized T1–T6 and T7 phase B implementation, delegated independent review/repair, automated checks and isolated integration verification. No application commit/push/tag/release, history rewriting or production deployment is authorized.
- Baseline: `0b86da31d4fc0a7893c4b8dc6956408e5ca0c70b` (v1.1.0). Source/configuration inspection establishes the design baseline, not a new application verification run.
- Scheduling: [current roadmap](roadmap.md). This document owns shared decisions, atomic task cards and separate implementation/check/review/owner-acceptance records.
- Execution rules: [development guide](../development.md), [agent rules](../../AGENTS.md) and [task template](task-template.md). A new agent should not need the original conversation or historical P/F plans to execute an authorized card.

## 1. Goal, baseline and scope

### 1.1 Goal

Use natural language in Codex or Hermes to open a Position or add Trades: the agent queries context, asks for missing information, displays a server-generated preview, and commits after the owner confirms in the conversation.

The journal does not call a model in this milestone. External agents interpret language; the backend supplies deterministic queries, validation, calculations and writes.

Typical flow: describe a trade → query accounts/positions/instruments → resolve missing details → prepare a preview draft → confirm in chat → commit the draft → receive record IDs and a journal link.

### 1.2 Current facts

- Account, Instrument, Position and Trade APIs exist; browser authentication uses cookies and database sessions.
- There are no dedicated agent credentials, MCP service or entry drafts.
- Multi-leg Trade writes are atomic; Position + first Trades currently require two frontend requests with partial-failure recovery.
- Instrument get-or-create still largely lives in the API router and needs extraction for reuse.
- Backend Decimal calculations, active-fill date maintenance, archival exclusion and closed-Trade locks already exist.
- Datetimes are stored as UTC and rendered in browser local time. There is no separate server default entry-timezone setting.
- Codex and Nous Research Hermes support HTTP MCP and can share a server with separate credentials. References: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Hermes MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp). Actual installed clients still require integration checks.

### 1.3 Delivery boundaries

| Included | Excluded |
|---|---|
| Query accounts, instruments, positions and trades | Screenshot recognition, model APIs, in-app chat |
| New Position + first Trades | MCP creation of an empty Position |
| Single-/multi-leg additions to open Positions | Close/reopen/archive/correct tools |
| Create missing instruments as part of entry | Account, strategy-meta and TradePlan writes |
| Preview, confirmation, atomic commit and safe retries | UI-03 parameter derivation and UI-04 trade templates |
| Credential management, local and remote connections | OAuth login, broker integration and production deployment |

The first six application cards and the documentation/integration card are defined in section 3. Screenshot/model integration remains deferred; this milestone does not authorize a later model provider or data-sharing choice.

## 2. Shared decisions and public contracts

### D01 · Agents interpret language

MCP accepts structured fields, not prose that the journal sends to a model. Agents interpret requests, query candidates, ask questions and display previews; the server owns validation, calculations, authorization and transactions.

Multiple account/position/contract matches require a user choice, not a similarity-based guess. For options, buy/sell alone must not silently determine BTO/STO/BTC/STC. Missing contract identity or opening/closing intent must be clarified.

### D02 · Tool surface

| Tool | Input/output contract |
|---|---|
| `get_context` | Current UTC time, server default timezone and local time, supported strategies and Trade actions |
| `list_accounts` | Owned accounts; archived accounts excluded by default |
| `search_instruments` | Kind, symbol, currency, exchange and option underlying/expiry/strike/call-put filters; complete contract specifications |
| `list_positions` | Account, primary-instrument, strategy and status filters |
| `get_position` | Owned Position details, primary instrument and cash flow; no unbounded nested Trade list |
| `list_trades` | Owned-position fills; archived fills excluded by default |
| `prepare_entry` | Validate new-Position + first-Trades or existing-Position additions; persist a preview draft |
| `commit_entry` | Commit by draft ID only; no replacement transaction fields |

List tools use `limit`/`offset`, default 50, maximum 200, nonnegative offset, and return `items`/`has_more`. Apply all filters before pagination and include a stable ID in ordering. Historical/archived access uses explicit filters and retains ownership checks. MCP instrument search defaults to including expired contracts for backfills; existing website picker defaults do not change.

### D03 · Structured entry input

`prepare_entry` takes a caller-generated UUID `request_id`, `kind` (`open_position` or `add_trades`), and a nonempty Trade array. New entries provide account, Primary Instrument, strategy and optional financial values/notes; additions provide `position_id`. These alternatives are mutually exclusive.

Each leg supplies an instrument, action, quantity, price, execution time, optional timezone, commission/fees and notes. Instrument references are exactly one of an existing `instrument_id` or a pending `InstrumentCreate` descriptor using today's stock/option/forex fields. Shared pending descriptors resolve to the same natural-key instrument on commit. Order groups follow existing multi-leg semantics.

Use Decimal and existing persistence precision; output amounts as decimal strings. Do not accept caller-controlled `user_id`, Trade account or authoritative cash flow. Missing/invalid fields return field-path problems without producing a valid draft. Do not invent an account, contract, execution time, quantity, price or action.

Preserve current optional values: capital/risk/reward may remain null; omitted commission/fees use existing zero defaults and must be shown. New-contract defaults, including multiplier/style, must appear in the preview. No strategy-parameter, price or trading-intent inference is added.

### D04 · Entry time interpretation

Add operator environment setting `JOURNAL_TIMEZONE`: an IANA timezone, default `UTC`; invalid configuration fails startup. Include timezone data in runtime dependencies rather than depending on host/container timezone agreement.

- A timezone-less execution datetime uses its explicitly supplied IANA timezone, otherwise `JOURNAL_TIMEZONE`.
- An offset-bearing datetime uses that offset. If an IANA timezone is also supplied, they must agree for that local time.
- Reject nonexistent/ambiguous daylight-saving local times and request an explicit offset.
- Agents obtain `get_context` and turn “today” into a concrete date; the server does not persist relative date expressions.
- Drafts freeze concrete UTC instants; later configuration changes do not reinterpret them.
- Preview input timezone, server-default-timezone representation and UTC. Persist UTC under the current convention; do not change existing REST naive-as-UTC interpretation or browser display behavior.

### D05 · Immutable preview drafts

Bind drafts to owner, creating credential and `request_id`; pending drafts expire after 24 hours. The same credential/request ID with the same submitted request returns the same draft without extending its lifetime. The same ID with different content conflicts; changes require a new request/draft. Check the submitted-request identity before reapplying current defaults, so a retry does not reinterpret a saved draft.

Persist the submitted-request digest, normalized input, preview, applied defaults, source identity, expiry and commit result. States are `pending`/`committed`; expiry is determined from the pending draft's deadline. Preparation writes only the draft, never real instruments, Positions or Trades. Do not deduplicate separate requests merely because they describe similar fills.

Preview account, target/new Position, complete instruments, each leg's action/quantity/price/fees/times, calculated cash flow, pending instrument creations and defaults. Use the shared backend calculation and persistence precision. Resolving an existing instrument with conflicting specifications returns a field conflict rather than silently changing the requested contract.

### D06 · Atomic, idempotent commit

Recheck credential, active user, ownership, draft deadline and current target state. A new Position's account must satisfy existing account-availability rules; additions retain the current Trade/account contract. No weakening or incidental expansion of domain rules.

Create/reuse instruments, optionally create the Position, write all Trades, maintain opening dates and persist the draft result in one transaction. Any failure rolls everything back, including new underlyings/options, empty Positions, partial Trades and draft consumption.

Concurrent/repeated commits of the same draft create one set of records and return the saved result. Return retryable errors for transient SQLite contention; retries use the same draft. Committed-result retrieval is independent of the pending deadline but still requires the original valid credential and owner. Save credential ID, commit time, resulting IDs and relative website links; no credential plaintext.

Instrument creation retains today's natural keys. Website and MCP creation use the same database-level write coordination before rechecking natural keys, not a process-local lock. Use a fixed coordination row in `app_config`. Existing multiple matches/specification conflicts are explicit errors, not automatic historical cleanup. Do not add instrument uniqueness constraints or repair existing instruments as part of this task.

### D07 · Confirmation and permissions

Agents must show each prepared batch and obtain confirmation in chat before committing. Initialization guidance and tool descriptions describe that workflow. Immutable drafts bind submitted content to the preview; the server cannot independently prove that a human confirmation occurred in another agent's conversation. No website confirmation step is added.

Credential profiles: `read` grants context/query tools; `entry` adds prepare/commit. Handler authorization must reject manually invoked write tools under `read`, regardless of tool visibility. No arbitrary SQL, HTTP or general REST proxy tool is exposed.

### D08 · Credential lifecycle

Add cookie-authenticated management endpoints `GET /api/mcp-tokens`, `POST /api/mcp-tokens`, `DELETE /api/mcp-tokens/{id}`. Named credentials belong to a user and are revocable. Default expiry is 90 days; creation may explicitly select another future expiry or no expiry.

Generate high-entropy random secrets; store only their digest and display prefix. Return plaintext once on creation, never in subsequent lists, logs or audit records. DELETE marks revocation and retains draft provenance. Revocation, expiry or user deactivation affects subsequent requests. Another user's token returns 404.

Use separate Codex/Hermes credentials. MCP credentials are not browser sessions and do not authorize generic REST writes or credential administration. Frontend stores plaintext only in the current reveal state, clears it on dismiss/navigation, and never writes it to localStorage.

### D09 · Transport and deployment

Use the official Python MCP SDK with Streamable HTTP mounted at exactly `/api/mcp` in the existing FastAPI container/database. References: [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [Python SDK](https://github.com/modelcontextprotocol/python-sdk). Lock a version compatible with current Python/FastAPI without unrelated toolchain upgrades.

Manually configured Bearer authentication covers initialization, discovery, calls and other MCP HTTP requests; each tool also checks permissions. Do not construct or advertise a fake OAuth discovery/login flow. Use transport operation without process-local entry state; drafts survive restart.

Keep local loopback port mapping. Remote clients use the same endpoint through HTTPS reverse proxy. Add MCP-specific allowed Host/Origin configuration with local addresses as defaults; normal agent requests without Origin are allowed, explicitly disallowed origins are rejected. Protocol errors must not fall through to the SPA, login HTML or path redirects.

### D10 · Compatibility and data boundaries

Preserve server ownership, cross-user 404, archival exclusion, closed-Trade locks, frozen P&L, append-only plans, numeric precision and currency separation. New atomic Position + first-Trade entry serves MCP; the existing website's two-request creation/recovery flow is not migrated in this milestone.

Extracted services must preserve existing successful REST requests, responses, statuses and business behavior. Schema additions use new Alembic migrations; no edits to shipped migrations, historical backfill or real-data correction. Proposed application paths below do not yet exist. Only disposable databases and synthetic data may be used for implementation checks.

## 3. Complete atomic task cards

All cards inherit section 2. Backend module paths below are relative to `backend/src/trading_journal/`; migration names are under `backend/alembic/versions/`; other paths are repository-relative. If the migration head advances before execution, allocate the next revisions and retain their dependency order rather than overwriting another revision.

Execution order: **T7 phase A → T1 → T2 → T3 → T4 → T5 → T6 → T7 phase B**. Atomic means independently checkable delivery, not authorization to make Git commits. Tests belong to each card; integration checks do not replace them.

<a id="t1"></a>

### T1 · MCP-TIME: server entry timezone and context

**Goal/evidence:** current UTC normalization has no separate default entry-timezone setting. Establish a deterministic shared context.

**Dependencies:** none.

**Files/actions:** modify `backend/pyproject.toml`/`backend/uv.lock`, `config.py` and `services/datetimes.py`; create `schemas/journal_context.py`, `services/journal_context.py` and `backend/tests/test_journal_context.py`.

**Steps:** add runtime timezone data and validated `JOURNAL_TIMEZONE`; implement an injectable current clock and supported strategy/action context; normalize MCP time inputs and detect DST ambiguity without changing existing datetime-function behavior. No transport is exposed by this card.

**Acceptance:**

- [x] Default UTC and explicit server timezone work independently of the container system timezone.
- [x] Naive, offset and IANA inputs satisfy D04, including mismatch/nonexistent/ambiguous cases.
- [x] Context returns UTC/local now and supported enums using one clock reference.
- [x] Existing REST datetime regressions remain unchanged.

**Checks:** Ruff/strict mypy; `test_journal_context.py`, `test_trades.py`, `test_positions.py`.

**Migration/walkthrough:** no migration; fixed-clock winter/summer round trips.

**Reviewer focus:** entry interpretation versus UTC persistence; accidental changes to existing normalization.

<a id="t2"></a>

### T2 · MCP-AUTH: dedicated credential management

**Goal/evidence:** owners can issue/revoke separate agent credentials; only browser sessions exist today.

**Dependencies:** T1.

**Files/actions:**

- Create `models/mcp_token.py`, `schemas/mcp_token.py`, `services/mcp_tokens.py`, `auth/mcp.py`, `api/mcp_tokens.py`; modify `models/__init__.py`, `main.py`; create `0004_mcp_tokens.py`.
- Create `backend/tests/test_mcp_tokens.py`; update migration tests.
- Create `frontend/src/api/mcpTokens.ts`, `frontend/src/views/SettingsMcpView.vue`, `frontend/tests/SettingsMcpView.spec.ts`; modify router/navigation and the existing strategy settings page to link both settings pages; regenerate `frontend/src/api/schema.d.ts`.

**Steps:** implement digest verification, profiles, expiry/revocation and D08 cookie endpoints; expose an internal principal containing user/credential IDs and profile for later tools. Build issue/reveal/copy/list/revoke UI with failure handling and no persistent plaintext. Show Codex/Hermes configuration examples using environment-variable credential placeholders.

**Acceptance:**

- [x] Named `read`/`entry` credentials can be issued, listed as metadata and revoked.
- [x] Plaintext appears once, never in database/list/logs or after frontend refresh.
- [x] Expiry, revocation and disabled users fail verification; cross-user token access returns 404.
- [x] MCP Bearer credentials cannot call cookie-authenticated management endpoints.
- [x] UI failures are visible; existing login/settings/navigation still work.

**Checks:** full backend checks; frontend tests/build; OpenAPI/codegen freshness.

**Migration/walkthrough:** isolated upgrade/downgrade; issue two synthetic credentials in a browser and revoke one.

**Reviewer focus:** secret disclosure, cookie/Bearer confusion, immediate revocation and ownership.

<a id="t3"></a>

### T3 · MCP-CORE: shared domain services and queries

**Goal/evidence:** reuse existing business rules rather than copying router internals into MCP.

**Dependencies:** T2.

**Files/actions:** extend `services/instruments.py`, `services/positions.py`, `services/trades.py`; create `services/journal_queries.py`, `services/ownership.py`, `services/write_guard.py`; modify relevant `api/instruments.py`, `api/positions.py`, `api/trades.py`; create `0005_instrument_write_guard.py`; update existing domain/migration tests and create `backend/tests/test_journal_queries.py`.

**Steps:** extract instrument lookup/specifications/get-or-create into non-committing services; extract owned-resource resolution and Position construction; implement bounded MCP queries from D02 without changing REST query parameters. Add read-only pending-instrument resolution. Seed a fixed `app_config` coordination row and have website/MCP instrument writes acquire the database write guard before natural-key recheck. Preserve current natural keys; explicitly reject existing multiple matches/specification conflicts without repairing history.

**Acceptance:**

- [x] Successful REST behavior and financial results remain compatible.
- [x] Filters precede pagination; identical symbols with different currencies/exchanges remain distinguishable.
- [x] Another user's accounts/positions/trades remain inaccessible.
- [x] Read-only resolution never creates underlyings or contracts.
- [x] Independent database connections creating the same natural key produce one instrument.
- [x] Cross-connection protection does not depend on a process-local lock.

**Checks:** Ruff/strict mypy/full pytest; concurrency tests use independent sessions and a real isolated SQLite file.

**Migration/walkthrough:** add only the coordination row; do not modify existing domain data.

**Reviewer focus:** REST compatibility, commit ownership, natural keys and actual shared coordination.

<a id="t4"></a>

### T4 · MCP-DRAFT: structured input and preview preparation

**Goal/evidence:** produce an inspectable, repeatable preview before business writes.

**Dependencies:** T1, T2, T3.

**Files/actions:** create `models/journal_entry_draft.py`, `schemas/journal_entry.py`, `services/journal_entries.py`, `0006_journal_entry_drafts.py`, `backend/tests/test_journal_entry_prepare.py`; modify `models/__init__.py` and migration tests.

**Steps:** define D03 alternatives and reject unknown fields; validate principal/profile, ownership and current target state; resolve existing instruments read-only and validate pending descriptors; normalize times; calculate preview using shared Decimal/persistence precision. Persist normalized input, submitted-request digest, preview/defaults/provenance/expiry with a unique user+credential+request-ID constraint. Match/reject prepare retries as D05 specifies.

**Acceptance:**

- [x] New-position and addition requests prepare single-/multi-leg drafts.
- [x] Missing values, action-kind mismatch, fractional option quantity, invalid time and foreign/closed target do not create a valid draft.
- [x] Preview includes defaults, pending instruments and all time representations.
- [x] Preparation changes no real instrument/Position/Trade counts.
- [x] Identical retries return one draft; changed content under the same request ID conflicts.
- [x] Drafts contain no token plaintext and cannot be taken over by another credential.

**Checks:** Ruff/strict mypy; preparation and migration tests.

**Migration/walkthrough:** isolated upgrade; prepare a new Position with a missing option and confirm only a draft is added.

**Reviewer focus:** hidden business writes/defaults, request identity and preview/commit consistency.

<a id="t5"></a>

### T5 · MCP-COMMIT: atomic entry and safe retries

**Goal/evidence:** Position + first Trades succeed together; agent retries must not duplicate fills.

**Dependencies:** T4.

**Files/actions:** extend `services/journal_entries.py`, necessary shared services and `schemas/journal_entry.py`; create `backend/tests/test_journal_entry_commit.py`.

**Steps:** coordinate draft consumption inside the database transaction and revalidate principal/draft/current resources; return stored results for committed drafts. Resolve/create instruments, optionally create Position, write atomic Trades and maintain opening dates; persist result/provenance in the same commit. Roll back all writes/consumption on failure and identify transient contention as retryable.

**Acceptance:**

- [x] New Position + first fills, existing-position additions and multi-leg fills commit correctly.
- [x] Invalid later legs or injected failures leave no new instruments, empty Positions, partial Trades or consumed drafts.
- [x] Repeat/concurrent commits and retries after lost success responses return the same IDs.
- [x] Independent-connection tests establish atomicity and concurrency behavior.
- [x] Closing the Position, revoking credentials or disabling the user after preview prevents a new commit.
- [x] Expired pending drafts reject; committed results remain retrievable under D06.
- [x] Cash flow, opening dates, archival exclusion and closed locks do not regress.

**Checks:** Ruff/strict mypy/full pytest.

**Migration/walkthrough:** no new migration; inject failures and concurrency using independent sessions, inspect all affected tables.

**Reviewer focus:** intermediate commits, check-then-insert idempotency and consumed-draft residue after exceptions.

<a id="t6"></a>

### T6 · MCP-SERVER: HTTP tools and agent workflow

**Goal/evidence:** external MCP clients discover/call the services without browser cookies.

**Dependencies:** T1–T5.

**Files/actions:** modify backend dependencies/lockfile; create `mcp/__init__.py`, `mcp/server.py`, `mcp/tools.py`, `mcp/instructions.py`; extend `auth/mcp.py`, `config.py`, `main.py`; create `backend/tests/test_mcp_http.py`, `backend/tests/test_mcp_tools.py`; extend SPA fallback tests and, where needed, lifecycle fixtures.

**Steps:** mount exact `/api/mcp`, explicitly handle unsupported methods/path behavior; verify Bearer at the protocol boundary and propagate the principal; register D02 tools with per-tool permissions, structured results and stable error codes. Guidance requires context lookup, clarification, preview/confirmation and original-draft retries. Configure MCP-specific Host/Origin validation and session-manager lifespan. HTTP tests must not merely invoke tools through an authentication-bypassing in-memory client.

**Acceptance:**

- [x] HTTP initialization/discovery/query/prepare/commit complete successfully.
- [x] Missing/invalid/expired/revoked credentials fail at the protocol boundary.
- [x] Direct write-tool calls cannot bypass read-only permissions.
- [x] Errors distinguish invalid fields, missing resources, closed Positions, expired drafts, request conflicts and retryable contention.
- [x] Disallowed Host/Origin rejects; normal agents without Origin work.
- [x] Multiple connections and a process restart preserve pending-draft usability.
- [x] Endpoint errors produce no SPA/login HTML/internal exception leakage.
- [x] Existing health/login/SPA deep links continue working.

**Checks:** Ruff/strict mypy/full pytest; a separately started HTTP MCP client verifies real protocol requests.

**Migration/walkthrough:** no migration; clients connect only to the service using a disposable database.

**Reviewer focus:** complete protocol authentication, handler authorization, exact mount and real lifespan verification.

<a id="t7"></a>

### T7 · MCP-DOC: design delivery, integration and acceptance

**Goal:** self-contained execution contract and accurate implementation/check/review/owner-acceptance records.

**Dependencies/phases:** phase A delivers this design before T1; phase B follows T1–T6.

**Files/actions:** create this EN/ZH pair; update roadmap, documentation map, README pair, triage and related handoff references. At phase B update development/walkthrough guidance and their mirrors plus `example/docker-compose.yml` for actual timezone/Host/Origin settings. Detailed reports stay in ignored `development-notes/<run-id>/`.

**Steps:** phase A fixes decisions, task anchors/actions/checks and unstarted application status. Phase B executes section 4, supplies local/HTTPS and both client configurations, records candidates/results/skipped checks/owner acceptance and cleans up owned resources. SDK-client tests are not actual Codex/Hermes acceptance.

**Acceptance:**

- [x] Phase A: EN/ZH contracts/defaults/tasks/states match; links/anchors work.
- [x] Phase A: a fresh agent can establish scope without the conversation; planned features are not described as implemented.
- [x] Phase A: temporary evidence/secrets remain outside Git and image contexts.
- [ ] Phase B: local/remote setup is reproducible and contains no real secrets.
- [ ] Phase B: integration checks and actual Codex/Hermes outcomes are recorded separately.
- [ ] Phase B: missing client checks remain pending; cleanup and actual owner acceptance are recorded.

**Checks:** phase A links/anchors, bilingual parity and `git diff --check`; phase B full integration checks and Compose rendering against the disposable setup.

**Migration/walkthrough:** documentation delivery has no application/data actions; phase B uses section 4.

**Reviewer focus:** design versus implementation, checks versus acceptance, complete cross-card interfaces and truthful omissions.

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

After OpenAPI changes regenerate `schema.d.ts` from an isolated backend using the [development commands](../development.md#commands-and-environments), inspect the diff and verify freshness; never hand-edit it. Build the actual candidate image. Check fresh migration and a synthetic `0003` upgrade, runtime timezone data, startup/health/login/SPA deep links and MCP HTTP. Do not copy real records to construct upgrade fixtures.

Phase A documentation-only delivery runs targeted checks, not these application commands or an image build. The [current walkthrough](../walkthrough.md) supplies disposable-environment commands; MCP-specific commands must be added in phase B after the feature exists.

### 4.2 Owner walkthrough

Use a new temporary database, Compose project, image, port and agent configuration; do not replace existing agent configurations.

1. Issue separate Codex/Hermes entry credentials and one read-only credential in the website.
2. In Codex prepare a new Position with first fills; verify preview alone creates no business records, then confirm and inspect the website.
3. In Hermes query that Position and add fills; backfill an earlier execution and check the opening date.
4. Create a missing option as part of multi-leg entry; inspect full specifications, default multiplier, fees and cash flow.
5. Compare default-server and explicit-timezone inputs, draft UTC and browser local display.
6. Retry the same draft without increasing fill counts; revoke the credential and verify subsequent requests fail.
7. Confirm read-only queries work and preparation/commit fail.

Test remote routing through an isolated network and HTTPS reverse proxy. Without a real second machine, record the network path actually tested, not a claim of real cross-machine owner acceptance. If an installed agent is unavailable, record that part as unrun rather than substituting an SDK test.

### 4.3 Evidence and cleanup

Record each base/candidate SHA or reproducible snapshot including relevant untracked files, commands and passed/failed/unrun results, separate review/owner status, and created processes/containers/images/directories and their cleanup. Keep detailed evidence local and ignored. Clean up only resources created for this task. Never access/migrate production data or stop existing deployments incidentally.

## 5. Execution handoff, status and completion

### 5.1 Execution boundaries

Follow T7 phase A → T1–T6 → T7 phase B. Complete each card's checks and freeze a reproducible candidate before the next card. Atomic cards are not permission for Git writes.

Only a later explicit orchestration request invokes the then-current installed skill; do not copy its model choices, review loop or repair budget here. Independent initial review receives the original design/card and complete candidate, without implementation/fix reports or desired verdicts. Follow repository rules for rereview.

Surface material domain/scope changes before implementation; routine implementation details are the executing agent's responsibility. This documentation request does not start application work, delegation, release publication or deployment.

### 5.2 Status and completion

| Task | Implementation | Automated checks | Independent review | Owner acceptance |
|---|---|---|---|---|
| T1 time/context | Implemented | Passed (card checks and isolated timezone integration) | Passed (T1-C00) | Pending |
| T2 credentials | Implemented | Passed (full backend/frontend/migration/codegen; real HTTP isolation) | Passed (T2-C01; one repair) | Pending |
| T3 shared services | Implemented | Passed (447 backend tests; cross-process and precision HTTP integration) | Passed (T3-C02; two repairs) | Pending |
| T4 preparation | Implemented | Passed (455 backend tests; immutable/precision/currency boundary integration) | Passed (T4-C05; five repairs) | Pending |
| T5 commit | Implemented | Passed (465 backend tests; atomic/retry/lock-expiry integration) | Passed (T5-C01; one repair) | Pending |
| T6 HTTP MCP | Implemented | Passed (472 backend tests; real HTTP/SDK, restart and discarded-response retry) | Passed (T6-C01; one repair) | Pending |
| T7 phase A documentation | Implemented | Passed (targeted documentation checks) | Not requested | Pending |
| T7 phase B integration | Not started | Not run | Not requested | Pending |

Completion requires the shared contract and card acceptance criteria, relevant automated checks, accurate review status, and actual Codex/Hermes owner walkthrough or explicitly accepted omissions. Implementation is not automatically `accepted`.

2026-11-04 documentation delivery: the owner authorized persisting this revised design/related guidance and committing/pushing the documentation. Phase A is implemented. Targeted checks passed for local links/anchors, paired structure/checklists/commands/technical literals, complete task cards, preserved historical content, whitespace, documentation-only scope and ignored evidence boundaries. Application source, dependencies, executable configuration, generated types and databases are unchanged; application tests/builds, independent review and runtime/owner acceptance were not performed. The candidate is the documentation commit containing this record, against the baseline above, including both new milestone files. Reproducible file hashes and command/results are retained locally in `development-notes/mcp-design-20261104-01/`; actual commit/push results are established by Git history, not inferred from this record.

### 5.3 Deferred work

Screenshot extraction, model/provider integration, UI-03/UI-04, lifecycle/correction MCP tools, metadata/plan/account writes, OAuth and general audit expansion remain outside this milestone. Website Position + first-Trade atomicity remains deferred even though MCP gains a bounded atomic entry path. Other product/quality directions remain in the roadmap.
