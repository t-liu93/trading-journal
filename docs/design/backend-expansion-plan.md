# Backend Expansion Plan — Horizontal CRUD (Phase 6+)

**Language:** English | [中文](./backend-expansion-plan.zh.md)

> Status: **DRAFT v0.1** (2026-05-21). The macro roadmap for expanding the backend
> beyond the Account tracer bullet, on `refactoring/rebuild`. Companion to
> [mvp-implementation-plan.md](./mvp-implementation-plan.md) (backend Phase 0–5),
> [data-model.md](./data-model.md), and the frontend plans. This document fixes the
> **phase ordering and scope**; the detailed per-phase task/test breakdowns land in
> follow-up iterations (one short section or doc per phase, like
> [frontend-implementation-plan-f1.md](./frontend-implementation-plan-f1.md)).
>
> **V1 release plan:** The V1-cut subset of this roadmap is consolidated in
> [v1-release-plan.md](./v1-release-plan.md) (the V1 north star). When V1 scope
> or cross-cutting decisions change, update both this macro and the V1 plan in
> the same change.

## 1. Where we are

Backend Phase 0–4 shipped (skeleton, `/health`, the **full v0.2 ORM schema for every
entity**, FastAPI Users auth, and `Account` CRUD). Phase 5 (Docker) is deferred.
Frontend F0 (auth) + F1 (Account CRUD UI, incl. `openapi-typescript` codegen) shipped.

**Crucial fact:** every entity's SQLAlchemy model already exists
(`instrument`, `position`, `trade`, `trade_plan`, `strategy_config`, `strategy_meta`),
but **only `Account` has Pydantic schemas + API endpoints**. The remaining work to a
usable journal is *horizontal CRUD expansion* — turning the existing models into typed
request/response schemas and routers, entity by entity.

**Sequencing decision (settled):** finish the **backend** breadth first, in small steps,
*then* resume the frontend (F2+). Rationale: the frontend is pure API consumption; once
the backend API surface is stable, frontend screens are cheap and flexible to change.
The frontend F2 (Position UI) is blocked on these backend endpoints either way.

## 2. Guiding principles

- **Same patterns as Account.** `Account` (`schemas/account.py` + `api/accounts.py`) is
  the template: owner-scoped queries, 404-not-403 for cross-user access, `extra="forbid"`
  on write schemas, `from_attributes` on read schemas, soft-delete where applicable.
  Most new endpoints are this recipe applied to a new model.
- **Expandability is the killer requirement.** The polymorphic `Instrument` (class-table
  inheritance) and the generic `Position` are the two expandability lynchpins. Get those
  two interface shapes right early — they are the highest-value, highest-risk steps.
- **Small, sequential, verifiable steps.** Each phase keeps the backend green
  (`pytest` + `ruff` + `mypy --strict`) before the next starts. No phase depends on a
  later one.
- **Defer computation that needs market data.** Realized PnL (sum of trade cash flows)
  and `days_open` are pure arithmetic and feasible now. *Unrealized* PnL needs a live
  quote source we don't have — deferred.

## 3. Dependency graph

```
User ─┬─> Account ─────────────┐
      │                        ├─> Position ─┬─> Trade
      └─> StrategyConfig        │            ├─> TradePlan (event stream)
                                │            └─> Wheel/PmccCycleMeta (1:1 ext.)
Instrument (NO user_id; global ─┘
 reference data) + OptionContract / ForexPair extensions
                                            └─> (derived read layer: PnL, days_open, ROI)
```

- **`Instrument` is the root** and has **no `user_id`** — it is global, shared reference
  data (see §6 Decision ①), referenced by `Position.primary_instrument_id`,
  `Trade.instrument_id`, `OptionContract.underlying_id`, `PmccCycleMeta.leap_instrument_id`.
- **`StrategyConfig`** depends only on `User` — fully independent, order-flexible.
- **`Position`** needs `Account` + `Instrument`. **`Trade`/`TradePlan`/strategy-meta** need
  `Position`. The **derived read layer** aggregates across `Trade` rows.

## 4. Phase roadmap

| Phase | Entity / scope | Risk | Unblocks | Status |
|---|---|---|---|---|
| **P6** | `Instrument` + `OptionContract` + `ForexPair` (create / get / list / search; update/delete restricted — see §6①) | ⭐⭐⭐ | everything; frontend instrument picker | ✅ done (2026-05-24) |
| **P7** | `StrategyConfig` CRUD (`(user_id, strategy_type)` unique, upsert-style) | ⭐ | strategy settings UI | ✅ done (2026-05-24) |
| **P8** | `Position` CRUD (owner-scoped; Trade-led — see §6②; manual `status`/`closed_at`/`capital_used`) | ⭐⭐ | frontend F3 | ✅ done (2026-05-26) |
| **P9** | `Trade` CRUD (atomic fills; `order_group_id` multi-leg; server computes `cash_flow`; action↔kind validated — see §6④) | ⭐⭐⭐ | frontend F4 | ✅ done (2026-05-26) |
| **P10** | `WheelCycleMeta` + `PmccCycleMeta` (1:1 Position extensions) | ⭐ | strategy-specific views | ✅ done (2026-05-27) |
| **P11** | `TradePlan` event-stream (append revision / list / current) | ⭐⭐ | forex plan UI | ✅ done (2026-05-27) |
| **P12** | Derived read layer (services): per-position `net_cash_flow` on list/detail + `GET /dashboard/summary`; unrealized deferred | ⭐⭐⭐ | dashboards / charts (F5) | ✅ done (2026-05-28) |
| **PX** | External Integrations Tracer Bullet (stocks via OpenFIGI lookup, forex local seed, DB cache table, feature-flagged, graceful degrade) — see §4.PX | ⭐⭐ | typeahead + autofill in F2/F3; lays the reusable integrations seam | — (opportunistic) |

> Phase numbers continue the `mvp-implementation-plan` lineage (Phase 0–5). Phase 5
> (Docker) is still pending and slots in flexibly — see §5.

### P6 — Instrument (base + extensions) ✅ done (2026-05-24)

- **Goal.** A typed API to create and look up tradeable instruments across all three
  MVP kinds (`stock`, `option`, `forex`), with the class-table-inheritance pattern
  (base `Instrument` + 1:1 `OptionContract` / `ForexPair`) expressed cleanly so future
  kinds (`future`, `crypto`) are additive.
- **Scope.** `GET /instruments` (list/search by `symbol`/`kind`), `GET /instruments/{id}`
  (joins the extension), `POST /instruments` (**get-or-create**, branches on `kind`).
  No update/delete (shared, referenced by others' positions).
- **Create semantics (settled).**
  - **get-or-create + dedup** on a natural key: stocks `(kind, symbol, exchange, currency)`,
    options `(underlying, opt_type, strike, expiry, multiplier)`. Existing row → 200; new → 201.
  - **symbol normalization** (`.upper().strip()`) before lookup/insert.
  - **stock** identity = `symbol` + `currency` (required), `exchange` optional.
  - **option** auto-creates its underlying stock from `underlying_symbol`
    (`underlying_exchange` optional); `currency` is shared and inherited (option currency
    == underlying currency, data-model §4.3) — not asked twice.
  - **forex** derives `Instrument.currency` from `ForexPair.quote_currency` so the §4.3
    invariant cannot be violated; payload carries `base_currency`/`quote_currency`/`pip_size`.
  - **Validation = format only** in the core (currency `^[A-Z]{3}$`, non-empty symbol,
    `strike>0`, valid `expiry`, enum membership). Factual validation (is this a real ticker)
    is the **PX** layer (see §4.PX).
- **Settled decisions.** Ownership & dedup (§6①). External factual validation
  / enrichment was promoted out of P6 into the standalone **PX — External
  Integrations Tracer Bullet** (§4.PX) on 2026-05-26 — it has no phase
  blocking it and blocks no phase, so it can land any time without disturbing
  the P8 → P12 sequence.

### P7 — StrategyConfig ✅ done (2026-05-24)

- **Goal.** Per-user strategy-level config (exposure caps). Nearly a copy of `Account`,
  minus soft-delete, plus the `(user_id, strategy_type)` uniqueness constraint.
- **Scope.** Create/upsert, get-by-strategy, list, update, delete. Order-flexible — can
  ship anytime after P6 (or even before, as a warm-up).

### P8 — Position ✅ done (2026-05-26)

- **Goal.** The universal strategy-instance aggregate, owner-scoped like `Account`.
- **Model (settled §6②):** *Trade-led, hybrid-derive.* The frontend F4 flow is
  "record a Trade → attach to an existing Position or create a new one inline",
  so a Position is always born with a first Trade. Backend reflects this:
  - **`opened_at`** is required at create time and **must equal the first Trade's
    `executed_at`** (the F4 inline-create flow supplies it). Backend treats it as
    a normal field; there is no NULL "awaiting first trade" interim state.
  - **`status`**, **`closed_at`**, **`capital_used`**, **`max_risk_at_open`**,
    **`max_reward_at_open`**, **`notes`** are user-supplied / user-managed.
    Defaults: `status="open"`, the rest `NULL`.
  - **`pnl_realized`** is frozen by the server on the `open→closed` transition
    (PATCH) as `SUM(trade.cash_flow)` for the position. While open it stays NULL.
  - **`currency`** is derived from `primary_instrument.currency` (data-model §6);
    the client never sends it.
  - Auto close-detection (e.g., net qty → 0 implies closed) is **deferred**.
    Reserve a `services/positions.py` seam so a future detector can be added
    without changing the API.
- **Scope.**
  - `POST /positions` — owner-scoped create. Required: `account_id`,
    `primary_instrument_id`, `strategy_type`, `opened_at`. Optional manual:
    `capital_used`, `max_risk_at_open`, `max_reward_at_open`, `notes`. Server
    sets `status="open"`, derives `currency` from the instrument.
  - `GET /positions` — list, filterable by `status` and `strategy_type`,
    ordered by `opened_at DESC`.
  - `GET /positions/{id}` — fetch one; 404 across users.
  - `PATCH /positions/{id}` — partial update of manual fields, **plus** the
    `status` transition `open → closed` (server freezes `pnl_realized` +
    `closed_at` in the same call). `account_id`, `primary_instrument_id`,
    `strategy_type`, `opened_at`, `currency`, `pnl_realized` are immutable
    via PATCH.
  - `DELETE /positions/{id}` — **hard delete only when no `Trade` rows exist**
    for the position (cascade rules would otherwise corrupt history). With
    trades attached, return 409. Soft-delete deliberately not introduced.
- **Out of scope for P8.** Cap enforcement against `StrategyConfig.max_exposure`
  (deferred to a services layer); trade aggregation derived reads (`days_open`,
  `pnl_unrealized`); auto close-detector.

### P9 — Trade ✅ done (2026-05-26)

- **Goal.** Record atomic broker-level fills under a Position; the data entry workhorse.
- **Scope.** Create (single, and multi-row sharing one `order_group_id` for IC /
  assignment / exercise per data-model §4.5.2); list by position; update / delete.
  Ownership flows through `position.user_id`; `account_id` denormalized to match
  the position (server-enforced, not client-supplied).
- **Validation (settled §6④).**
  - `action ↔ instrument.kind` consistency — `bto/sto/btc/stc` ⇒ option; `buy/sell`
    ⇒ stock/forex. Reject 422.
  - `quantity > 0` always; **integer required for options**; stock / forex allow
    fractional (matches fractional shares + forex micro-lots).
  - `price > 0` always (per-unit fill price; sign lives in `cash_flow`/`action`).
  - `commission >= 0`, `fees >= 0`. Both are unsigned costs; server deducts them
    in the `cash_flow` formula.
  - **`cash_flow` is server-computed** (not accepted from the client):
    ```
    cash_flow = sign(action) × price × quantity × multiplier
                − commission − fees
    where sign(action) = -1 for buy/bto/btc,
                        +1 for sell/sto/stc,
          multiplier   = OptionContract.multiplier for options,
                       = 1 otherwise.
    ```
    The Trade create schema does not include `cash_flow`. Servers single-source-of-truth
    avoids client / server formula drift and broker-API spoofing concerns.
- **`order_group_id` semantics.** Optional. When present, all rows in the same
  POST are validated together and share that UUID; ungrouped trades have NULL.
  The endpoint accepts either a single object or an array (atomic multi-leg
  submission). Pattern detection (Assignment / Exercise / IC-open) lives in the
  frontend display layer (data-model §4.5.2).

### P10 — Strategy-meta extensions ✅ done (2026-05-27)

- **Goal.** 1:1 Position extensions holding strategy-specific snapshot/config
  (`WheelCycleMeta`: funding/loan/interest; `PmccCycleMeta`: `leap_instrument_id`).
- **Scope.** Create/get/update tied to a Position; only meaningful for the matching
  `strategy_type`.

### P11 — TradePlan event stream ✅ done (2026-05-27)

- **Goal.** Append-only plan revisions per Position; query "current plan".
- **Scope.** Append revision (auto-increment `revision_no` per position), list history,
  get current (`MAX(revision_no)`). No update/delete of historical revisions
  (data-model §4.6).

### P12 — Derived read layer ✅ done (2026-05-28)

- **Goal.** The numbers that make a journal useful, computed at read time from `Trade`
  rows (data-model §4.4 "Derived — NOT stored").
- **Delivered.** Per-position `net_cash_flow` field added to `GET /positions` and
  `GET /positions/{id}` (SUM(trade.cash_flow) GROUP BY, archived trades excluded,
  always present — `Decimal("0")` when no trades). New
  `GET /api/dashboard/summary` endpoint returns `ClosedSummary` (count, win_rate,
  per-currency PnL, monthly per-(month, currency) PnL) + `OpenSummary` (count,
  per-currency net_cash_flow). Owner-scoped. No DB migration — all values derived.
  Reused `services/positions.py` for the batched `compute_net_cash_flows` helper;
  introduced `services/dashboard.py` with `compute_summary(session, user_id)`.
- **Deferred.** `pnl_unrealized`, `pnl_total`, `annualized_return` — need a market quote
  source (not in MVP). Per-position `days_open` / `roi_on_capital` / `result` computed
  in frontend per V1 release plan Decision 5. FX conversion and granular endpoints
  (`/per-currency`, `/monthly-pnl`, etc.) deferred to V1.x.

## 5. Cross-cutting & deferred deliverables (tracked)

These are not in the dependency chain but must not be lost:

- **Phase 5 — Docker single-container deployment.** Defined in
  [mvp-implementation-plan.md §5 Phase 5](./mvp-implementation-plan.md). Not blocking;
  recommended slot: just before resuming the frontend, so the deployable artifact wraps
  a meaningful backend.
- **CI pipeline (MVP deliverable).** No `.github/workflows` exists yet. Minimum:
  backend `ruff` + `mypy --strict` + `pytest`; frontend `npm run build` (`vue-tsc`).
  **Include a codegen-freshness gate**: a job that runs `npm run codegen` against a
  freshly migrated backend and `git diff --exit-code src/api/schema.d.ts` — catches
  "backend schema changed but `schema.d.ts` wasn't regenerated", which becomes a real
  hazard as P6+ adds many new schemas. (Frontend F1 §6 flagged this as a post-F1
  follow-up.)
- **Codegen mechanism — DONE (F1.1).** `openapi-typescript` devDep, `codegen` npm
  script, committed `frontend/src/api/schema.d.ts`, README workflow all in place. The
  only gap is the CI gate above. After each backend phase that changes schemas,
  re-run `npm run codegen` and commit the diff.

## 6. Design decisions

All four of the project-spanning decisions are now **settled**. Recorded here so future
phases share the same vocabulary; the per-phase detail plans implement them.

1. **Instrument ownership & dedup** (was blocking P6). **Settled in P6
   (2026-05-24):** `Instrument` has no `user_id` → global shared reference data.
   Any authenticated user can create + get + search. **Get-or-create dedup** on
   natural keys (stocks `(kind, symbol, exchange, currency)`; options
   `(underlying, opt_type, strike, expiry, multiplier)`). **No update/delete** —
   instruments are referenced across users' positions. External factual
   validation/enrichment is the non-blocking **PX** phase (renamed from P6.x),
   not a write-time dependency.

2. **Position creation semantics** (was blocking P8). **Settled 2026-05-26:**
   *Trade-led with hybrid derive.* Position is always born alongside a first Trade
   (F4's inline-create flow). `opened_at` is supplied by the client at create
   time and **must equal the first Trade's `executed_at`** (no NULL interim
   state). `status` / `closed_at` / `capital_used` / `max_risk_at_open` /
   `max_reward_at_open` / `notes` are user-managed; server sets
   `status="open"` by default and freezes `pnl_realized` + `closed_at` on the
   explicit PATCH `open→closed` transition. Auto close-detection (net-qty → 0
   ⇒ closed) is deferred; a `services/positions.py` seam is reserved for a
   future detector.

3. **How much computation in MVP** (shapes P8/P9/P12). **Settled 2026-05-26:**
   - **Stored**: `pnl_realized` (frozen at close), `cash_flow` per Trade
     (server-computed at Trade create — see §4 / §6④).
   - **Derived on read in P12**: `days_open`, `pnl_total`, `roi_on_capital`,
     `result` (win/loss). No "denormalized for speed" duplication.
   - **Deferred**: `pnl_unrealized`, `annualized_return` — need a market quote
     source not in MVP.

4. **Trade validation depth** (was blocking P9). **Settled 2026-05-26:**
   - `action ↔ instrument.kind` consistency enforced (422 on mismatch).
   - `quantity > 0` always; integer required for option trades; fractional
     allowed for stock / forex.
   - `price >= 0` always (per-unit fill price; sign lives entirely in cash_flow
     via the action sign — see data-model §4.5.2 for worthless-expire / assignment
     flows that legitimately use price=0).
   - `commission >= 0`, `fees >= 0` (unsigned costs).
   - **`cash_flow` is server-computed** from
     `sign(action) × price × quantity × multiplier − commission − fees`;
     the Create schema does not accept it. Single source of truth → no
     client/server formula drift, no broker-API spoofing risk.

## 4.PX — External Integrations Tracer Bullet (standalone phase, opportunistic)

> Originally tracked as "P6.x". Promoted to a standalone phase **PX** on
> 2026-05-26 — it has no phase blocking it and blocks no phase, so the numeric
> stream P8 → P12 is now strictly sequential. Slot PX in whenever convenient.

- **Why it matters beyond Instrument.** This is the project's *first* external-API
  integration, done deliberately as a tracer bullet to establish two reusable seams
  that every later integration (broker fills, FX rates, market quotes) needs:
  - **① external API access** — a backend `integrations/` module, API key in
    `config.py` (`.env`), an async `httpx` client, timeout + graceful degrade;
    **never raises into the write path**.
  - **② external data storage/cache** — a persistence pattern so repeated lookups
    don't re-hit the provider. *Lean:* a DB-backed cache table
    `(provider, query) → payload + fetched_at` with TTL. Alternative: in-memory TTL.
- **User-facing behavior.** Backend `GET /instruments/lookup?q=` powers frontend
  typeahead + "did you mean AAPL?" hints and create-time enrichment (autofill
  exchange/currency). Manual entry + format validation stays the always-works
  core; the lookup layer degrades silently when the provider is unconfigured/down/empty.
  **Never blocks** instrument creation.
- **Scope by kind.** Stocks: validate/enrich via a free provider (lean
  **OpenFIGI**). Forex: seed a local list of common pairs (no external call).
  Options: skip external; validate only the underlying via the stock path.
- **Sub-decisions to settle when PX is scheduled.** (a) provider — *lean
  OpenFIGI* (free, official-ish, symbol→security/exchange mapping); Finnhub /
  FMP as alternatives. (b) cache mechanism — DB table vs in-memory TTL (*lean
  DB table*, to actually establish the storage seam). (c) feature flag + key
  layout in `config.py`/`.env`.
- **Sequencing.** No phase is blocked; this slot is opportunistic. If PX lands
  during F3 or later, the frontend `InstrumentPicker` and `InstrumentForm`
  gain typeahead + autofill without code changes to other phases (it just
  populates new behavior behind the same API surface).

## 7. After this roadmap

1. **Frontend F3** (Position list / detail / edit — *no inline create*; create
   lives inside F4 per the Trade-led model) once P8 + P10 + P11 land. **F4**
   (Trade entry with inline Position-create) after P9.
2. **F5 dashboards/charts** consume the P12 derived layer.
3. **Postgres parity & deployment** — backend Phase 5 Docker (F6) + verify the
   migration against Postgres before any production use (mvp-implementation-plan §9).
4. **PX** can land any time it's convenient — typeahead + autofill light up in
   F2/F3 automatically once the backend lookup endpoint exists.

---

## Changelog

- **v0.6 (2026-05-28)** — P12 derived read layer shipped on `refactoring/rebuild`. P12.1
  added `net_cash_flow: Decimal` to `PositionRead` (list + detail), powered by
  batched `services/positions.compute_net_cash_flows` (one SUM-GROUP-BY per request,
  no N+1). P12.2 added `GET /api/dashboard/summary` returning per-currency closed
  P/L + monthly buckets + win_rate + per-currency open net_cash_flow snapshot.
  New files: `schemas/dashboard.py`, `services/dashboard.py`, `api/dashboard.py`,
  `tests/test_dashboard.py` (13 tests). `tests/test_positions.py` extended with
  `net_cash_flow` coverage. `frontend/src/api/schema.d.ts` regenerated. Backend test
  suite: **406 passing** (was 347); `ruff` + `mypy --strict` clean. V1 backend cut
  is now complete; remaining V1 work is frontend F3 → F4 → F5 → F6. PX still
  opportunistic.
- **v0.5 (2026-05-27)** — P8 / P9 / P10 / P11 all shipped on `refactoring/rebuild`.
  P8 introduced `services/positions.py` (Trade-led, manual status, server-frozen
  `pnl_realized`). P9 introduced `services/trades.py` (atomic fills, server-computed
  `cash_flow`, multi-leg via `order_group_id`, soft-delete via `Trade.archived_at`).
  P10 introduced `services/strategy_meta.py` (8 endpoints across nested
  `/positions/{pid}/wheel-meta` and `.../pmcc-meta`). P11 introduced
  `services/trade_plans.py` with strictly append-only event stream (4 endpoints,
  server-allocated `revision_no`, no PATCH/DELETE). Status table flips: P8 → P9 →
  P10 → P11 all ✅ done; **P12 is now ⏳ next**. V1 release plan
  ([v1-release-plan.md](./v1-release-plan.md)) consolidates the V1 cut and the
  P12 scope refinement (per-position derived computed in frontend; backend P12
  delivers list aggregate + dashboard endpoints only). Backend test suite: **347
  passing**; `ruff` + `mypy --strict` clean.
- **v0.4 (2026-05-26)** — P9 Trade CRUD shipped. §6④ amended:
  `price > 0` → `price >= 0` to honor data-model §4.5.2 worthless-expire /
  assignment flows that legitimately use `price=0`. Backend test suite: 272
  passing.
- **v0.3 (2026-05-26)** — Decisions ②③④ all settled.
  ② Position is **Trade-led**: `opened_at` supplied at create-time as the first
  Trade's `executed_at`; `status`/`closed_at`/`capital_used` manual; `pnl_realized`
  frozen on PATCH `open→closed`; auto close-detector deferred behind a `services/`
  seam. ③ Stored = `pnl_realized` + `cash_flow`; derived in P12 = `days_open`,
  `pnl_total`, `roi`. ④ Trade validation: action↔kind enforced, option qty
  integer, stock/forex qty fractional, `price > 0`, `cash_flow` **server-computed
  only** (Create schema rejects client value). Renumbered `P6.x` → standalone
  **PX — External Integrations Tracer Bullet** (§4.PX, opportunistic, blocks
  nothing). P8/P9 narrative sections rewritten under the settled rules.
- **v0.2 (2026-05-26)** — Mark P6 and P7 as done (shipped 2026-05-24). Decision ①
  (Instrument ownership/dedup) settled in P6. Backend test suite: 127 passing
  (`pytest` + `ruff` + `mypy --strict` green).
- **v0.1 (2026-05-21)** — Initial macro roadmap. Phase 6–12 ordering + scope, starting
  from Instrument; cross-cutting CI/Docker tracking; four open design decisions. Detailed
  per-phase task/test breakdowns deferred to follow-up iterations.
