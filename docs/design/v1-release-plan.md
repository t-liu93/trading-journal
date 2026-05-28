# V1 Release Plan

**Language:** English | [中文](./v1-release-plan.zh.md)

> Status: **DRAFT v0.1** (2026-05-27). North-star scope document for the first deployable release of the trading journal on `refactoring/rebuild`. Consolidates the V1-cut content from [backend-expansion-plan.md](./backend-expansion-plan.md) and [frontend-expansion-plan.md](./frontend-expansion-plan.md). Companion to [data-model.md](./data-model.md). After V1 ships, this document remains as the V1 record; the two macro roadmaps are archived.

## 1. Purpose and maintenance

This document is the **single source of truth for V1**:

- What ships in V1 vs. what defers to V1.x
- The five cross-cutting decisions settled on 2026-05-27
- Execution sequencing and dependency graph for remaining phases (P12, F3–F6)
- Pointers to per-phase detail plans (one EN+ZH doc per phase, sub-phases as sections inside)

**Maintenance discipline.** During V1 work, three documents move together:

- This V1 release plan — the V1 cut + V1 decisions
- [backend-expansion-plan.md](./backend-expansion-plan.md) — full backend macro roadmap incl. V1.x phases (e.g. PX)
- [frontend-expansion-plan.md](./frontend-expansion-plan.md) — full frontend macro roadmap

When a V1 scope or decision changes, all three are updated in the same change. The macro docs hold the long-term horizon; this doc holds the V1 cut. After V1 ships, the macros are archived and this becomes the record.

## 2. Where we are (2026-05-27)

**Backend (347 tests passing; `ruff` + `mypy --strict` clean):**

- Auth — FastAPI Users cookie + DB sessions
- Account CRUD ([mvp-implementation-plan.md Phase 4](./mvp-implementation-plan.md#phase-4--account-crud-the-vertical-slice))
- P6 Instrument (stock / option / forex + class-table extensions, get-or-create)
- P7 StrategyConfig
- P8 Position (Trade-led, manual status, server-frozen `pnl_realized`)
- P9 Trade (server-computed `cash_flow`, multi-leg via `order_group_id`, `archived_at` soft-delete)
- P10 Strategy-meta (`/positions/{pid}/wheel-meta` + `.../pmcc-meta`)
- P11 TradePlan (append-only event stream, server-allocated `revision_no`)

**Frontend (`vue-tsc` + `vite build` clean; `schema.d.ts` fresh):**

- F0 Auth scaffold + `AuthenticatedLayout`
- F1 Account CRUD UI
- F2 `InstrumentPicker` (select-only typeahead) + `InstrumentForm` + `/instruments` browse + `/settings/strategies`

**Not yet built:** P12 (backend derived read layer), F3 (Position UI), F4 (Trade entry UI), F5 (Dashboard), F6 (Docker single-container).

## 3. V1 cut

### In V1 (must-have)

| Phase | Deliverable | Macro reference |
|---|---|---|
| **P12** | Position list PnL column (SQL aggregate) + dashboard aggregate endpoints | [backend-expansion-plan.md §P12](./backend-expansion-plan.md#p12--derived-read-layer) |
| **F3** | Position list / create / edit / detail page (Overview / Meta / Plan / Trades tabs); `InstrumentPicker` gains `allowCreate` | [frontend-expansion-plan.md §F3](./frontend-expansion-plan.md#f3--position-crud--detail-page-with-strategy-meta-tabs--plan-tab) |
| **F4** | Trade entry UI (Custom multi-leg primary); Position-detail Trades tab grouped by `order_group_id` | [frontend-expansion-plan.md §F4](./frontend-expansion-plan.md#f4--trade-entry) |
| **F5** | Dashboard — per-currency PnL cards + open/closed tables + one chart (monthly realized PnL bars) | [frontend-expansion-plan.md §F5](./frontend-expansion-plan.md#f5--dashboards--charts) |
| **F6** | Single-container Docker: FastAPI serves `frontend/dist`, SPA fallback, SQLite volume | [frontend-expansion-plan.md §F6](./frontend-expansion-plan.md#f6--single-container-docker-production-wiring) + [mvp-implementation-plan.md §5 Phase 5](./mvp-implementation-plan.md#phase-5--docker-single-container-deployment) |

### Deferred to V1.x (explicitly out of V1)

Everything below stays in the macro roadmaps and lights up post-V1; no V1 work depends on them. The full deferred backlog is consolidated in §7.

- **PX** External instrument validation/enrichment — [backend-expansion-plan.md §4.PX](./backend-expansion-plan.md#4px--external-integrations-tracer-bullet-standalone-phase-opportunistic)
- Unrealized PnL (needs a market quote source not in V1)
- FX conversion + `FxRate` table — [data-model.md §6](./data-model.md#currency-placement)
- Broker API integration + `BrokerCredential`
- OAuth / MFA / AuditLog (future `auth-and-security.md`)
- Position `archived_at` ([data-model.md §7 Q5](./data-model.md#open-design-questions-still-need-a-decision-before-implementation))
- Account "Unarchive" button
- Vitest / Playwright systematic coverage
- Dark mode / i18n / mobile-responsive pass

## 4. Cross-cutting decisions (settled 2026-05-27)

Five V1-shaping decisions, in addition to the per-phase decisions already recorded in the macro docs.

### Decision 1 — `InstrumentPicker`: get-or-create + `allowCreate` prop

`InstrumentPicker` (F2 shipped select-only) gains an `allowCreate` prop for use inside Position-create (F3) and Trade-create (F4) flows. When the user types a symbol that doesn't match any existing instrument:

- **Stock**: picker shows a "Create new" sub-form with format-validated fields (symbol / exchange / currency); POST `/instruments` is **get-or-create**, so duplicate keys silently return the existing row (200) instead of erroring.
- **Option**: two-step — pick underlying via typeahead first, then fill `opt_type / strike / expiry / multiplier` as dedicated inputs; picker calls option get-or-create. This avoids trying to typeahead a 5-tuple identity.
- **Forex**: pick from existing list or type base/quote (`ForexPair` extension fields).

**Backend impact:** None — POST `/instruments` already implements get-or-create (P6).

**Frontend impact:** F3 adds `allowCreate` to `InstrumentPicker` plus the inline create sub-form; F4 reuses without further changes.

### Decision 2 — F4 Trade entry: Custom multi-leg primary

Multi-leg events ([data-model.md §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping)) are entered via a generic **Custom multi-leg form**: the user adds rows manually, the form shares one server-assigned `order_group_id` across all rows in the submission. This matches the user's Notion "encounter" mental model (4 rows of an iron condor entered as one bundle).

**Named flows** (e.g., "Open iron condor", "Record assignment") are **NOT promised for V1**. If F4 detail planning identifies high-frequency events whose row generation is mechanical (e.g., expiration = 1 row at price 0, fees 0), those land as opt-in helpers built on top of the custom form. The shortlist is settled inside the F4 detail plan, not here.

**Backend impact:** None — POST `/trades` already accepts arrays sharing a server-generated `order_group_id` (P9).

### Decision 3 — Charts: `vue-echarts`

Naive UI has no chart primitives. V1 uses `vue-echarts` (official Vue 3 wrapper around Apache ECharts) for the F5 monthly-PnL chart. Rationale: Vue-native, mature, widest chart-type coverage if V1.x adds more visualisations.

**Alternative compared:** `@unovis/vue` (D3-based viz library by F5 — **not** an ECharts variant). Side-by-side comparison happens in the F5 detail plan; `vue-echarts` is the lean.

### Decision 4 — Position: no `archived_at` in V1

V1 keeps the [P8 status quo](./backend-expansion-plan.md#p8--position):

- `DELETE /positions/{id}` is hard delete, **only** allowed when no `Trade` and no `TradePlan` rows are attached (409 otherwise).
- Frontend Position list defaults to `?status=open`; closed positions appear via a status filter or History tab.

Adding `archived_at` is a clean additive migration when needed ([data-model.md §7 Q5](./data-model.md#open-design-questions-still-need-a-decision-before-implementation) remains open). Deferred to V1.x.

### Decision 5 — Derived values: frontend per-position, backend for lists + aggregates

Split based on data-fetch shape and dataset size:

| Scope | Computed where | Why |
|---|---|---|
| Single position's `days_open` / `pnl_total` / `roi_on_capital` / `result` (detail page) | **Frontend** | Detail page already fetches the position's trades for the Trades tab — summing them is free. Saves a per-position derived endpoint. |
| Position list PnL column (across N positions) | **Backend SQL** | List view shouldn't pay an N-times trade-fetch cost; one `SUM(cash_flow) GROUP BY position_id` is cheap. |
| Dashboard aggregates (per-currency PnL, win rate, monthly bucket) | **Backend SQL** | Cross-position aggregation; backend SQL is the only sane place. |

**Consistency invariant.** Frontend and backend formulas for single-position realized PnL must agree. Both compute `SUM(trade.cash_flow)` for open positions; closed positions surface the frozen `pnl_realized` on the row. Trivial to keep in sync.

## 5. Sequencing and dependency graph

```
Backend already done:  P6 → P7 → P8 → P9 → P10 → P11 ✅
Frontend already done: F0 → F1 → F2 ✅

V1 remaining:

P12.1 (list PnL aggregate) ──┐
                              ├──> F3 ──> F4 ──┐
                              │                  ├──> F5 ──> F6
P12.2 (dashboard endpoints) ──┘                  │
                                                  └─ (F5 depends on P12.2)
```

**Default execution order** (recommended): **P12 → F3 → F4 → F5 → F6**, with P12 done as one phase containing both sub-deliverables. The two P12 sub-deliverables share SQL helpers, so splitting them would duplicate work.

**Alternative considered**: lead with F3 then F4 (frontend debug loops are longer; F3/F4 don't strictly depend on P12 since single-position derived is computed in frontend per Decision 5). Discussed and reverted on 2026-05-27 — user opted to land P12 first so frontend phases can hit a complete API surface.

## 6. Per-phase scope summary

Detailed plans live in their own `*-pN.md` / `*-fN.md` files (one EN + one ZH per phase, sub-phases as sections inside the same doc). The summaries here are the V1 cut only — they refine, but do not supersede, the macro docs.

### 6.1 P12 — Backend derived read layer

- **Macro reference:** [backend-expansion-plan.md §P12](./backend-expansion-plan.md#p12--derived-read-layer)
- **Detail plan:** `backend-expansion-plan-p12.md` (+ `.zh.md`) — to be written

**V1 scope.**

- **P12.1 — Position list enhancement.** `GET /positions` response gains a `current_pnl` field (name finalised in detail plan) sourced from a SQL `SUM(trade.cash_flow) GROUP BY position_id`. For open positions this is running realized PnL; for closed positions this surfaces the frozen `pnl_realized` on the row. Behind `?include_derived=true` flag or always-on is a sub-decision settled in the detail plan.
- **P12.2 — Dashboard aggregate endpoints** under `/dashboard/*` (or `/stats/*` — name settled in detail plan):
  - Per-currency PnL summary (open + closed split).
  - Win rate over closed positions: `count(pnl_realized > 0) / count(*)`.
  - Monthly realized PnL buckets per currency (for the F5 chart).
  - Open / closed position counts.

**Explicitly out of V1 P12:**

- Single-position derived endpoint — frontend computes (Decision 5).
- `pnl_unrealized` / `pnl_total` with market quotes — no quote provider in V1.
- FX-converted aggregates — no `FxRate` table in V1.

### 6.2 F3 — Position UI

- **Macro reference:** [frontend-expansion-plan.md §F3](./frontend-expansion-plan.md#f3--position-crud--detail-page-with-strategy-meta-tabs--plan-tab)
- **Detail plan:** `frontend-implementation-plan-f3.md` (+ `.zh.md`) — to be written

**V1 scope.**

- **`/positions` list view.** Filter by `strategy_type` and `status`; default `status=open`; sort `opened_at DESC`. Each row shows symbol / strategy / opened_at / `current_pnl` (from P12.1) / currency.
- **Position create/edit modal.** Uses `InstrumentPicker` with `allowCreate` (Decision 1). Form fields per [data-model.md §4.4](./data-model.md#44-position-universal-strategy-instance) writable subset.
- **Position detail page** with tabs:
  - **Overview** — summary card + writable manual fields (`capital_used` / `max_risk_at_open` / `max_reward_at_open` / `notes`) + read-only derived values (`days_open` / `pnl_total` / `roi_on_capital` / `result`) computed in frontend (Decision 5).
  - **Meta** — conditional on `strategy_type`: wheel funding/loan/interest form for `wheel`; LEAP picker for `pmcc`; empty state for other types. Backed by P10's `/positions/{pid}/wheel-meta` / `.../pmcc-meta` endpoints.
  - **Plan** — TradePlan event stream (P11): list revisions oldest-first, append-new-revision form. Read-mostly for non-forex strategies.
  - **Trades** — chronological trade log grouped visually by `order_group_id`. Initially a placeholder until F4 lands the entry path; the read pane and grouping logic ship here, the entry modal in F4.
- **Position delete** — current 409-aware flow; UI surfaces the "has attached trades / plans" error inline (no `archived_at`, per Decision 4).

### 6.3 F4 — Trade entry UI

- **Macro reference:** [frontend-expansion-plan.md §F4](./frontend-expansion-plan.md#f4--trade-entry)
- **Detail plan:** `frontend-implementation-plan-f4.md` (+ `.zh.md`) — to be written

**V1 scope.**

- **TradeEntryModal — Custom multi-leg form** (Decision 2):
  - Add/remove leg rows; each row carries `action / instrument / quantity / price / commission / fees / executed_at / notes`.
  - All rows in one submission share a server-generated `order_group_id` (POST `/trades` with an array body).
  - `InstrumentPicker` reused with `allowCreate` from F3; `action ↔ instrument.kind` validation matches the P9 backend rule.
  - Per-row `cash_flow` previewed client-side (display only — server is the source of truth).
- **Position detail Trades tab** rendering:
  - Chronological list, visually grouped by `order_group_id`.
  - Pattern-detected badges inferred from row shape: **Assignment** (option `btc/stc` @ 0 + stock fill at strike, paired by `order_group_id`), **Exercise** (similar), **Expiration** (option `btc/stc` @ 0, no paired stock), **IC-open** (4 option legs in one `order_group_id`).
  - Soft-delete via P9's `archived_at` (`DELETE /trades/{id}` then `?include_archived=true` to view).
- **Optional named flows.** Decided inside the F4 detail plan, not here. Default assumption: none for V1; mechanical helpers are added only if F4 planning identifies clear wins.

**Explicitly out of V1 F4:**

- No automatic strategy detection beyond visual pattern badges.
- No bulk import / CSV / broker fill ingestion.
- No Vitest unless the badge-detection logic warrants it.

### 6.4 F5 — Dashboard

- **Macro reference:** [frontend-expansion-plan.md §F5](./frontend-expansion-plan.md#f5--dashboards--charts)
- **Detail plan:** `frontend-implementation-plan-f5.md` (+ `.zh.md`) — to be written

**V1 scope.**

- **`/dashboard` rewrite** (currently placeholder cards):
  - Per-currency PnL summary cards (e.g., "+$1,250 USD" / "+€180 EUR") sourced from P12.2.
  - Open positions table — symbol / strategy / opened_at / `current_pnl` / currency.
  - Closed positions table — symbol / strategy / closed_at / `pnl_realized` / `result`.
  - **One chart**: per-month realized PnL bar chart. Per-currency stacks vs per-currency switcher — settled in detail plan. Powered by `vue-echarts` (Decision 3).
- **`src/api/dashboard.ts`** (or `stats.ts`) wrapping the P12.2 endpoints, with `useDashboard` composable in the F1 pattern.

**Explicitly out of V1 F5:**

- Multiple chart types (one is enough for V1).
- Cross-currency converted totals (no FX in V1).
- Per-strategy drill-down dashboards.
- Date-range pickers beyond month bucketing.

### 6.5 F6 — Single-container Docker production wiring

- **Macro reference:** [frontend-expansion-plan.md §F6](./frontend-expansion-plan.md#f6--single-container-docker-production-wiring) + [mvp-implementation-plan.md §5 Phase 5](./mvp-implementation-plan.md#phase-5--docker-single-container-deployment)
- **Detail plan:** `v1-implementation-plan-f6.md` (+ `.zh.md`) — to be written; final filename settled when F6 plan starts

**V1 scope.**

- **Multi-stage Dockerfile.**
  - Stage 1 (frontend builder): `node` base, `npm ci && npm run build` → emits `frontend/dist/`.
  - Stage 2 (backend builder): `python:3.12-slim`, `uv sync --no-dev --frozen`.
  - Stage 3 (runtime): copies backend venv + `frontend/dist`; `CMD uvicorn trading_journal.main:app --host 0.0.0.0 --port 8000`.
- **`main.py` static mount.** `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` with SPA fallback so client-side router paths serve `index.html`. API routes stay under their existing prefixes.
- **Entrypoint** runs `alembic upgrade head` before launching uvicorn.
- **`docker-compose.yml`** for dev parity (named volume for SQLite file, `.env` injection).

**Explicitly out of V1 F6:**

- HTTPS termination (handled by host reverse proxy, not in container).
- Multi-instance / horizontal scaling.
- Postgres-in-container (SQLite remains V1; Postgres parity verified offline — §8).

## 7. V1.x deferred backlog (consolidated)

Items explicitly out of V1. Each links to its trigger condition and macro reference.

| Item | Trigger to revisit | Reference |
|---|---|---|
| **PX** External instrument validation/enrichment | Opportunistic; light up typeahead/autofill in `InstrumentPicker` whenever convenient | [backend-expansion-plan.md §4.PX](./backend-expansion-plan.md#4px--external-integrations-tracer-bullet-standalone-phase-opportunistic) |
| Unrealized PnL | When a live quote source is available | [data-model.md §4.4](./data-model.md#44-position-universal-strategy-instance) |
| FX conversion + `FxRate` table | When cross-currency view is requested | [data-model.md §6](./data-model.md#currency-placement) / [§7](./data-model.md#future-extensions-deferred-schema-not-committed-yet) |
| Broker API integration + `BrokerCredential` | When manual entry becomes the bottleneck | [data-model.md §7](./data-model.md#future-extensions-deferred-schema-not-committed-yet) |
| OAuth / MFA / AuditLog | Before any sensitive action beyond password | `auth-and-security.md` (to be written) |
| Position `archived_at` | When closed-position clutter becomes a real complaint | [data-model.md §7 Q5](./data-model.md#open-design-questions-still-need-a-decision-before-implementation) |
| Account "Unarchive" button | When the user actually un-archives | [frontend-implementation-plan-f1.md §9](./frontend-implementation-plan-f1.md#9-after-f1) |
| Vitest / Playwright systematic coverage | When F4 (or later) introduces non-trivial logic | [frontend-expansion-plan.md §5](./frontend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked) |
| Dark mode toggle | Anytime; one prop on `n-config-provider` | — |
| i18n | Multi-locale demand | — |
| Mobile-responsive pass | After V1 user feedback | — |
| `@unovis/vue` vs `vue-echarts` re-evaluation | When V1.x adds a second chart and one library's strengths matter | Decision 3 above |
| `delta_at_open` / option-snapshot fields on Trade | When the user starts capturing option Greeks | [data-model.md §7 Q1](./data-model.md#open-design-questions-still-need-a-decision-before-implementation) |
| Position tags / labels | When categorisation beyond `strategy_type` is needed | [data-model.md §7 Q4](./data-model.md#open-design-questions-still-need-a-decision-before-implementation) |

## 8. V1 cross-cutting deliverables

### 8.1 CI codegen freshness gate

**Recommended slot:** alongside P12 / F3 — the next backend schema churn.

The check runs:

1. `alembic upgrade head` against a fresh SQLite.
2. Boot uvicorn against it.
3. `npm run codegen` against the running backend.
4. `git diff --exit-code src/api/schema.d.ts` — fail the job if stale.

Catches "backend schema changed, `schema.d.ts` wasn't regenerated" — increasingly likely as F3/F4/F5 expand the consumed API surface.

### 8.2 Postgres parity verification

Before any production deployment of V1:

- Run the existing migrations on Postgres.
- Run the full backend test suite against Postgres.
- Fix any incompatibilities (none expected — schema designed Postgres-compatible from day one).

Lands as a checklist item near F6, not a phase.

### 8.3 Manual acceptance walkthrough

**Deferred until V1 is nearly done** (per user direction 2026-05-27) — added to this document as a §8.3 expansion when F6 is the last unchecked phase. Will cover every primary flow: register → account → instrument (incl. inline create from picker) → position (create / edit / detail tabs) → trade (single + Custom multi-leg) → dashboard (cards / tables / chart).

## 9. After V1

V1.x candidates in rough priority order:

1. **PX** external integrations — light up typeahead / autofill in `InstrumentPicker`.
2. **Position `archived_at`** + Account "Unarchive" — if clutter becomes a real complaint.
3. **Frontend test runners** (Vitest unit + Playwright e2e) covering F4 entry + dashboard.
4. **Chart library re-evaluation** if F5 grows beyond the V1 one-chart cut.
5. **Broker API integration** (depends on `auth-and-security.md` and `BrokerCredential`).
6. **FX conversion view** (depends on `FxRate` table + provider).
7. **Mobile-responsive pass** + dark mode + i18n — opportunistic.

---

## Changelog

- **v0.1 (2026-05-27)** — Initial V1 release plan. Consolidates the V1 cut from `backend-expansion-plan.md` and `frontend-expansion-plan.md`. Five cross-cutting decisions settled:
  1. `InstrumentPicker` get-or-create + `allowCreate` prop; option flow is two-step (underlying then attrs).
  2. F4 Custom multi-leg primary; named flows deferred to F4 detail plan.
  3. `vue-echarts` for F5 charts; `@unovis/vue` comparison deferred to F5 plan.
  4. Position `archived_at` deferred to V1.x; V1 keeps hard-delete-when-empty + `?status=open` filter.
  5. Per-position derived computed in frontend; list + dashboard aggregates computed in backend SQL.
