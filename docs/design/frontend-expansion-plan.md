# Frontend Expansion Plan — Horizontal UI (Phase F2+)

**Language:** English | [中文](./frontend-expansion-plan.zh.md)

> Status: **DRAFT v0.2** (2026-05-24). Macro roadmap for expanding the frontend
> beyond F0 (auth scaffold) and F1 (Account CRUD UI). Pairs with
> [backend-expansion-plan.md](./backend-expansion-plan.md) (Phase P6+) and rolls each
> F-phase up to a small contiguous batch of backend phases, so every F-phase is
> independently agent-executable end-to-end ("一把梭"). Companion docs:
> [data-model.md](./data-model.md), [mvp-implementation-plan.md](./mvp-implementation-plan.md),
> [frontend-implementation-plan.md](./frontend-implementation-plan.md) (F0 detailed),
> [frontend-implementation-plan-f1.md](./frontend-implementation-plan-f1.md) (F1 detailed),
> [frontend-implementation-plan-f2.md](./frontend-implementation-plan-f2.md) (F2 detailed —
> first plan written under this revision). Detailed per-F-phase docs land in
> `frontend-implementation-plan-fN.md` (one per F-phase).

## 1. Where we are

Frontend F0 (auth scaffold) and F1 (Account CRUD UI) shipped on `refactoring/rebuild`.
Backend P6 (Instrument CRUD for stock/option/forex) just shipped (92 backend tests
green). Backend P7–P12 not yet started; see
[backend-expansion-plan.md §4](./backend-expansion-plan.md#4-phase-roadmap).

**Sequencing decision (revised v0.2):** backend leads, frontend follows in the same
iteration — **but the F-phase granularity has been coarsened** so each F-phase
pairs with a *small contiguous batch* of backend phases and ships as one atomic UI
iteration. Result: every F-phase doc is one self-contained plan an agent can execute
end-to-end. The v0.1 sub-phase scheme (F2.1, F2.2, …) is dropped.

Why the revision: F1's patterns (codegen, AuthenticatedLayout, resource API module,
composable, modal form, confirm dialog) have proved cheap to extend per-entity, and
the underlying backend pieces (e.g., Instrument + StrategyConfig) often don't justify
their own user-facing screen — bundling them as one F-phase produces a more coherent
UI iteration than micro-stepped F2.x slices would.

## 2. Guiding principles

- **Same patterns as F1.** Most new entities are F1's recipe applied to a new resource.
- **Codegen is the API contract.** `openapi-typescript` regenerates
  `src/api/schema.d.ts` after every backend schema change; no hand-written types for
  entities already in the OpenAPI doc.
- **Each F-phase is one atomic iteration.** Scope is sized so an agent (or focused
  human session) can execute the F-phase doc end-to-end, then ship + verify. No
  internal sub-phases.
- **Reusable components over duplicated screens.** F2's `InstrumentPicker` is consumed
  by F3 (Position create) and F4 (Trade create) — we do not re-implement typeahead
  per screen.
- **Defer chart libraries until F5.** F2/F3/F4 are forms + tables only; Naive UI
  alone covers them. ECharts (or alternative) lands with F5 dashboards.
- **Manual click-through is the test until logic warrants Vitest.** Same justification
  as [F0 §7](./frontend-implementation-plan.md#7-testing-architecture) /
  [F1 §7](./frontend-implementation-plan-f1.md#7-testing-approach). Vitest + Playwright
  land later — see §5.

## 3. Backend ↔ Frontend mapping

| F-phase | Backend gate | UI deliverable | Status |
|---|---|---|---|
| **F2** | [P6](./backend-expansion-plan.md#p6--instrument-base--extensions) ✅ + [P7](./backend-expansion-plan.md#p7--strategyconfig) ✅ | `InstrumentPicker` component + `/instruments` browse page + `/settings/strategies` page | ✅ done (2026-05-26) |
| **F3** | [P8](./backend-expansion-plan.md#p8--position) + [P10](./backend-expansion-plan.md#p10--strategy-meta-extensions) + [P11](./backend-expansion-plan.md#p11--tradeplan-event-stream) | Position list + create/edit + detail page (with strategy-meta tabs and Plan tab) | ⏳ next (after P8/P10/P11) |
| **F4** | [P9](./backend-expansion-plan.md#p9--trade) | Trade entry (multi-leg `order_group_id` UX) + Position-detail trade log | — |
| **F5** | [P12](./backend-expansion-plan.md#p12--derived-read-layer) | Dashboards: per-currency PnL + open/closed positions + charts | — |
| **F6** | [Backend Phase 5](./mvp-implementation-plan.md#phase-5--docker-single-container-deployment) | Single-container Docker production build wiring (FastAPI serves `frontend/dist`) | — |

[P6.x — external instrument validation](./backend-expansion-plan.md#p6x--external-instrument-validation-first-external-api-integration-optional-non-blocking)
is **deferred and non-blocking**; it slips into F2 as a small enhancement (typeahead
autocomplete + "did you mean AAPL?") whenever it lands. Not gating F-phase
sequencing.

Execution cadence: `P6→P7→F2 / P8→P10→P11→F3 / P9→F4 / P12→F5 / Phase 5→F6`.

## 4. Phase roadmap

Each F-phase is detailed in its own `frontend-implementation-plan-fN.md` doc. The
sections below are scope summaries.

### F2 — Instrument & StrategyConfig frontend ✅ done (2026-05-26)

**Detailed plan:** [frontend-implementation-plan-f2.md](./frontend-implementation-plan-f2.md)
(+ [中文](./frontend-implementation-plan-f2.zh.md)).

**Goal.** End-to-end UI coverage for the two backend resources that don't justify
their own headline screen but are load-bearing for everything downstream: the
shared global Instrument dictionary and per-user strategy exposure caps.

**Headline deliverables.**
- `src/api/instruments.ts` + `useInstruments` + `InstrumentForm` (create modal) +
  `InstrumentPicker` (reusable typeahead) + `InstrumentsView` (`/instruments`
  browse page).
- `src/api/strategyConfigs.ts` + `useStrategyConfigs` + `SettingsStrategiesView`
  (`/settings/strategies` page).
- `AuthenticatedLayout` gains `Instruments` and `Settings` nav entries;
  `DashboardView` placeholder cards updated.

**Why this scope is the right "one bite".** `InstrumentPicker` is load-bearing for
F3 + F4 — needs to be solid before Position/Trade screens consume it. The
`/instruments` browse page is small but gives the picker its first real consumer
(also doubles as the catalog admin surface, since instruments have no PATCH/DELETE
backend). StrategyConfig is order-flexible with the rest and tiny; bundling it here
keeps F3 focused on Position alone.

### F3 — Position CRUD + detail page (with strategy-meta tabs + Plan tab)

**Goal.** The user's primary workspace — list, create, edit, archive Position; open
the detail page to see / edit strategy-specific snapshots and the trade plan.

**Headline deliverables.**
- `/positions` list view (filter by `strategy_type` and `status`) + create/edit
  modal using F2's `InstrumentPicker` for `primary_instrument_id`.
- Position detail page with tab strip: **Overview** (summary card +
  `max_risk_at_open` etc.) / **Meta** (wheel funding/loan/interest or PMCC LEAP
  picker, shown conditional on `strategy_type`) / **Plan** (append revision +
  history table, primarily for forex) / **Trades** (placeholder until F4).
- Archive flow as in F1; depends on
  [§6② decision](./backend-expansion-plan.md#6-open-design-decisions).

**Open dependency.** `Position.currency` is derived from
`primary_instrument.currency` per [data-model §6](./data-model.md#currency-placement);
form shows it as a read-only badge.

### F4 — Trade entry

**Goal.** The journal's data-entry workhorse. Multi-leg `order_group_id` UX is the
design crux — see §6②.

**Headline deliverables.**
- `TradeEntryModal` — discriminated by `action` (`buy` / `sell` / `bto` / `sto` /
  `btc` / `stc`); fields per [data-model §4.5](./data-model.md#45-trade-atomic-event).
- Multi-leg helper flows for the synthetic events in
  [data-model §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping): open
  iron condor (4 rows), assignment (2 rows), exercise (2 rows), expire (1 row).
- Position detail page **Trades** tab — chronological list grouped visually by
  `order_group_id` with pattern-detected badges (Assignment / Exercise /
  IC-open / Expire).
- `src/api/trades.ts` accepts both single and array payloads (atomic group submit).

**Acceptance.** Every flow from
[data-model §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping) (12 rows)
enterable through UI without curl.

### F5 — Dashboards & charts

**Goal.** The numbers that make the journal useful.

**Headline deliverables.**
- `/dashboard` rewrite: per-currency PnL summary card (no FX conversion in MVP,
  per [data-model §6](./data-model.md#currency-placement)) + open-positions table
  + closed-positions history table.
- First chart: per-month realized PnL bars per currency. Library landing here —
  see §6③.
- `src/api/stats.ts` (or `derived.ts`) wrappers around P12 endpoints.

### F6 — Single-container Docker production wiring

**Goal.** Deployable artifact.

**Headline deliverables.**
- Multi-stage Dockerfile: builder stage runs `npm run build`; runtime stage copies
  `frontend/dist/` into the FastAPI image.
- `main.py` adds `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`
  with SPA fallback so client-side router paths serve `index.html` (API paths stay
  under `/api/*`).
- Smoke test recipe: container spin-up + full F1+F2+F3+F4+F5 click-through from a
  fresh browser via port-mapped tunnel.

## 5. Cross-cutting & deferred deliverables (tracked)

- **CI codegen gate.** Flagged in
  [backend-expansion-plan.md §5](./backend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked).
  **Recommended slot: bundled with F2** — F2 pulls in two new backend schemas
  (Instrument + StrategyConfig), so the gate would catch the first stale-codegen
  hazard. Concrete shape:
  1. CI job runs backend migrations + starts uvicorn.
  2. `npm run codegen` against the running backend.
  3. `git diff --exit-code src/api/schema.d.ts` fails the job if stale.
- **Frontend tests.**
  - **Vitest** for `useAccounts` / `useInstruments` / `usePositions` once any of
    them grows non-trivial logic (optimistic updates, request cancellation, group
    pattern detection in F4). Most likely F4 timeframe.
  - **Playwright** for ≥3 user journeys: register + Account CRUD + Position CRUD;
    Trade entry happy path; dashboard sanity. Most likely between F4 and F5.
- **Dark mode toggle.** Naive UI's `darkTheme` is one prop away
  ([frontend-implementation-plan.md §2 NOT in scope](./frontend-implementation-plan.md#explicitly-not-in-scope-deferred)).
  Land whenever convenient — no dependency.
- **i18n.** Out of scope for MVP per
  [F0 §2](./frontend-implementation-plan.md#explicitly-not-in-scope-deferred). The
  bilingual docs (this file, et al.) do not imply a bilingual UI.
- **Account "Unarchive" button.** Flagged in
  [F1 §9 item 1](./frontend-implementation-plan-f1.md#9-after-f1); trivial when
  backend exposes the endpoint. Slot opportunistically.

## 6. Open design decisions

Each item is **OPEN** pending sign-off. My leanings noted.

1. **InstrumentPicker UX for options.** Options are identified by a 5-tuple
   `(underlying, opt_type, strike, expiry, multiplier)`. *Lean:* picker for option
   contexts splits into two steps — pick underlying (typeahead), then pick contract
   attributes via dedicated inputs; the picker's "select existing or create" call
   gets get-or-create semantics for free. Settled in F2.
2. **Trade entry multi-leg ergonomics.** Two designs:
   (a) one master "Add trade" modal with an "Add another leg" button that grows
   the row count, all sharing one `order_group_id`; or
   (b) prebuilt flows ("Open iron condor", "Record assignment") that emit the
   right rows automatically. *Lean:* ship (b) with a "Custom multi-leg" escape
   hatch that's (a) — named flows cover 90% of the
   [data-model §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping)
   mappings, custom escape hatch covers the long tail. Settled in F4.
3. **Dashboard chart library.** ECharts (most coverage), Plotly (data-science
   familiar), or Chart.js (smallest). *Lean:* **ECharts** — Vue 3 wrapper
   `vue-echarts` is mature; the combination chart range we eventually want
   (bars + lines + per-currency stacks) is well-served. Settled in F5.

## 7. After this roadmap

1. **Broker API integration.** Out of MVP; once it lands, Trade entry becomes
   import-driven and F4's manual entry becomes the fallback path.
2. **FX rate provider + opt-in conversion view.** Per
   [data-model §6](./data-model.md#currency-placement) and
   [§7 future extensions](./data-model.md#future-extensions-deferred-schema-not-committed-yet).
   F5 dashboards gain a "Convert to base currency" toggle once an `FxRate` table
   and provider exist.
3. **Mobile-responsive pass.** Naive UI is desktop-first; once F5 ships and the
   primary user journey is stable, a responsive audit makes sense.
4. **PWA / offline support, Dark mode, i18n** — opportunistic.

---

## Changelog

- **v0.3 (2026-05-26)** — Mark F2 as done. Delivered `InstrumentPicker` (typeahead,
  reusable for F3/F4), `InstrumentForm` (stock/option/forex tabs with get-or-create
  UX), `/instruments` browse page, `/settings/strategies` page (PATCH-aware,
  hard-delete-aware), and nav entries in `AuthenticatedLayout`. Decision ①
  (option picker UX) deferred — `InstrumentPicker` ships as select-only typeahead;
  the two-step underlying + contract attributes flow lands inside F3's Position
  create when `allowCreate` is added. Frontend: `vue-tsc` clean + `vite build` clean
  + `schema.d.ts` fresh against live OpenAPI.
- **v0.2 (2026-05-24)** — Re-scoped F-phases to coarser, "one-shot agent-executable"
  granularity. F2 collapses former F2.1/F2.2 (Instrument + StrategyConfig); former
  F2.3/F2.4/F2.5 (Position + meta + Plan) become F3; former F3 (Trade entry) becomes
  F4; former F4 (Dashboards) becomes F5; new F6 = Docker production wiring (was a
  loose end). Open decisions trimmed from 4 to 3 (drop F2-internal sequencing — no
  longer relevant). CI codegen gate moved to "bundled with F2".
- **v0.1 (2026-05-24)** — Initial macro roadmap with sub-phased F2 (F2.1–F2.5). See
  git history.
