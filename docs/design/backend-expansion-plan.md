# Backend Expansion Plan — Horizontal CRUD (Phase 6+)

**Language:** English | [中文](./backend-expansion-plan.zh.md)

> Status: **DRAFT v0.1** (2026-05-21). The macro roadmap for expanding the backend
> beyond the Account tracer bullet, on `refactoring/rebuild`. Companion to
> [mvp-implementation-plan.md](./mvp-implementation-plan.md) (backend Phase 0–5),
> [data-model.md](./data-model.md), and the frontend plans. This document fixes the
> **phase ordering and scope**; the detailed per-phase task/test breakdowns land in
> follow-up iterations (one short section or doc per phase, like
> [frontend-implementation-plan-f1.md](./frontend-implementation-plan-f1.md)).

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

| Phase | Entity / scope | Risk | Unblocks |
|---|---|---|---|
| **P6** | `Instrument` + `OptionContract` + `ForexPair` (create / get / list / search; update/delete restricted — see §6①) | ⭐⭐⭐ | everything; frontend instrument picker |
| **P7** | `StrategyConfig` CRUD (`(user_id, strategy_type)` unique, upsert-style) | ⭐ | strategy settings UI |
| **P8** | `Position` CRUD (owner-scoped; MVP manual fields — see §6②) | ⭐⭐ | frontend F2 |
| **P9** | `Trade` CRUD (atomic fills under a Position; `order_group_id` multi-leg) | ⭐⭐⭐ | frontend F3 |
| **P10** | `WheelCycleMeta` + `PmccCycleMeta` (1:1 Position extensions) | ⭐ | strategy-specific views |
| **P11** | `TradePlan` event-stream (append revision / list / current) | ⭐⭐ | forex plan UI |
| **P12** | Derived read layer (services): `days_open`, `pnl_realized` on close, `pnl_total`, `roi`; unrealized deferred | ⭐⭐⭐ | dashboards / charts (F4) |

> Phase numbers continue the `mvp-implementation-plan` lineage (Phase 0–5). Phase 5
> (Docker) is still pending and slots in flexibly — see §5.

### P6 — Instrument (base + extensions)

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
    is the P6.x layer.
- **Open decisions.** Ownership & dedup confirmed (§6①). Remaining: see P6.x sub-decisions.

### P6.x — External instrument validation (first external-API integration; optional, non-blocking)

- **Why it matters beyond Instrument.** This is the project's *first* external-API
  integration, done deliberately as a tracer bullet to establish two reusable seams that
  every later integration (broker fills, FX rates, market quotes) needs:
  - **① external API access** — a backend `integrations/` module, API key in `config.py`
    (`.env`), an async `httpx` client, timeout + graceful degrade; **never raises into the
    write path**.
  - **② external data storage/cache** — a persistence pattern so repeated lookups don't
    re-hit the provider. *Lean:* a DB-backed cache table `(provider, query) → payload +
    fetched_at` with TTL (note data-model §6 dislikes JSON-heavy columns → prefer
    structured columns or accept a small cache-only JSON column). Alternative: in-memory TTL.
- **User-facing behavior.** Backend `GET /instruments/lookup?q=` powers frontend typeahead
  + "did you mean AAPL?" hints and create-time enrichment (autofill exchange/currency).
  Manual entry + format validation stays the always-works core; the lookup layer degrades
  silently when the provider is unconfigured/down/empty. **Never blocks** instrument creation.
- **Scope by kind.** Stocks: validate/enrich via a free provider. Forex: seed a local list
  of common pairs (no external call). Options: skip external; validate only the underlying
  via the stock path.
- **Open sub-decisions.** (a) provider — *lean OpenFIGI* (free, official-ish, symbol→
  security/exchange mapping); Finnhub / FMP as alternatives. (b) cache mechanism — DB table
  vs in-memory TTL (*lean DB table*, to actually establish the storage seam). (c) feature
  flag + key in `config.py`/`.env`.
- **Sequencing.** Ships **after** P6 core, so provider selection/flakiness never blocks the
  Instrument foundation.

### P7 — StrategyConfig

- **Goal.** Per-user strategy-level config (exposure caps). Nearly a copy of `Account`,
  minus soft-delete, plus the `(user_id, strategy_type)` uniqueness constraint.
- **Scope.** Create/upsert, get-by-strategy, list, update, delete. Order-flexible — can
  ship anytime after P6 (or even before, as a warm-up).

### P8 — Position

- **Goal.** The universal strategy-instance aggregate, owner-scoped like `Account`.
- **Scope.** Create with `account_id` + `primary_instrument_id` + `strategy_type`;
  `currency` derived from the instrument (not user-provided, data-model §6). List/filter
  by `status` and `strategy_type`. Update notes/manual snapshots. Soft-delete or hard?
  (TBD with §6②.)
- **Open decisions.** Manual vs trade-derived `opened_at`/`status`/`closed_at` (§6②).

### P9 — Trade

- **Goal.** Record atomic broker-level fills under a Position; the data entry workhorse.
- **Scope.** Create (single, and multi-row sharing one `order_group_id` for IC/assignment
  pairs); list by position; update/delete. Ownership flows through `position.user_id`;
  `account_id` denormalized to match the position.
- **Open decisions.** Validation depth — action↔kind consistency, integer option qty,
  server-computed vs client-supplied `cash_flow` (§6④).

### P10 — Strategy-meta extensions

- **Goal.** 1:1 Position extensions holding strategy-specific snapshot/config
  (`WheelCycleMeta`: funding/loan/interest; `PmccCycleMeta`: `leap_instrument_id`).
- **Scope.** Create/get/update tied to a Position; only meaningful for the matching
  `strategy_type`.

### P11 — TradePlan event stream

- **Goal.** Append-only plan revisions per Position; query "current plan".
- **Scope.** Append revision (auto-increment `revision_no` per position), list history,
  get current (`MAX(revision_no)`). No update/delete of historical revisions
  (data-model §4.6).

### P12 — Derived read layer

- **Goal.** The numbers that make a journal useful, computed at read time from `Trade`
  rows (data-model §4.4 "Derived — NOT stored").
- **Scope (MVP-feasible).** `days_open`, realized PnL (sum of `cash_flow`), and on the
  status→`closed` transition freeze `pnl_realized` onto the row; `roi_on_capital`.
  Likely a `services/` module to keep routers thin.
- **Deferred.** `pnl_unrealized`, `pnl_total`, `annualized_return` — need a market quote
  source (not in MVP).

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

## 6. Open design decisions (resolve per-phase, before coding it)

Carried forward from planning discussion. My leanings are noted but every item is **OPEN**
pending sign-off.

1. **Instrument ownership & dedup** (blocks P6). `Instrument` has no `user_id` → global
   shared reference data. To settle: who may create; whether to "get-or-create" /
   dedup on `(kind, symbol, exchange, currency)` for stocks and on
   `(underlying, opt_type, strike, expiry, multiplier)` for options; whether
   update/delete of a globally-referenced instrument is allowed. **Settled:** open
   create+get/search to any authenticated user, get-or-create dedup on natural key,
   no update/delete (instruments are referenced by other users' positions). External
   factual validation/enrichment is the non-blocking **P6.x** slice (in MVP), not a hard
   write-time dependency.
2. **Position creation semantics** (blocks P8). MVP manual `opened_at`/`status`/
   `closed_at`/`capital_used` with an explicit "close" action, **vs** auto-derived from
   the position's trades. *Lean:* MVP manual; auto-derivation moves to P12.
3. **How much computation in MVP** (shapes P8/P9/P12). Store realized PnL / `days_open`
   manually on the row, **vs** compute them on read in P12. *Lean:* keep the row
   honest (only what the user/broker supplies) and compute derived values in P12;
   freeze `pnl_realized` only at the close transition.
4. **Trade validation depth** (blocks P9). Enforce action↔instrument-kind consistency
   (`bto/sto/btc/stc` ⇒ option; `buy/sell` ⇒ stock/forex)? Integer quantity for options?
   `cash_flow` server-computed from `action+price+qty+commission+fees`, or trusted from
   the client (data-model says the broker reports it directly)? *Lean:* enforce
   action↔kind + integer option qty; accept client `cash_flow` but validate its sign
   against the action.

## 7. After this roadmap

1. **Resume frontend F2** (Position UI) once P6 + P8 land; F3 (Trade entry) after P9.
2. **F4 dashboards/charts** consume the P12 derived layer.
3. **Postgres parity & deployment** — Phase 5 Docker + verify the migration against
   Postgres before any production use (mvp-implementation-plan §9).

---

## Changelog

- **v0.1 (2026-05-21)** — Initial macro roadmap. Phase 6–12 ordering + scope, starting
  from Instrument; cross-cutting CI/Docker tracking; four open design decisions. Detailed
  per-phase task/test breakdowns deferred to follow-up iterations.
