# Frontend Phase F3 — Position CRUD + Detail Page

**Language:** English | [中文](./frontend-implementation-plan-f3.zh.md)

> Status: **DRAFT v0.1** (2026-05-28). Companion to
> [frontend-expansion-plan.md](./frontend-expansion-plan.md) (macro roadmap),
> [v1-release-plan.md](./v1-release-plan.md) (V1 north star),
> [frontend-implementation-plan-f2.md](./frontend-implementation-plan-f2.md) (F2
> pattern reference), [data-model.md](./data-model.md), and the backend plans
> [backend-expansion-plan-p8.md](./backend-expansion-plan-p8.md) (Position),
> [backend-expansion-plan-p10.md](./backend-expansion-plan-p10.md)
> (strategy-meta), [backend-expansion-plan-p11.md](./backend-expansion-plan-p11.md)
> (TradePlan), and
> [backend-expansion-plan-p12.md](./backend-expansion-plan-p12.md) (`net_cash_flow`
> on Position list/detail). Iterate here before writing code.

## 1. Purpose

F3 sits on top of backend **P8** (Position CRUD), **P10** (strategy-meta
extensions), **P11** (TradePlan event stream), and **P12.1** (`net_cash_flow`
on Position list/detail) — all shipped. It delivers the user's primary
workspace:

- A browseable Position list at `/positions` (filter by `strategy_type` /
  `status`, default `status=open`, sorted `opened_at DESC`, surfacing the
  P12.1 `net_cash_flow` column).
- A Position create / edit modal — using F2's `InstrumentPicker` (extended
  with a new `allowCreate` prop so the user can spawn a brand-new instrument
  inline without leaving the form).
- A Position detail page at `/positions/:id` with the four-tab strip
  prescribed by [v1-release-plan §6.2](./v1-release-plan.md#62-f3--position-ui):
  **Overview** / **Meta** (wheel or PMCC, conditional on `strategy_type`) /
  **Plan** (TradePlan event stream) / **Trades** (placeholder until F4).
- The plumbing F4 will plug into: a `TradeEntryModal` slot inside the Position
  detail page (rendered in F4) and the Position-create flow that — under the
  Trade-led model — must spawn a `TradeEntryModal` to capture the mandatory
  first Trade. **F3 stops at the seam**: it builds the Position-create modal
  shell with a *first-trade subsection* whose actual implementation is left to
  F4. See §5.5 for the precise contract.

This is the user's primary workspace. After F3, every other V1 surface (F4
trade entry, F5 dashboard) is purely additive over what F3 puts on screen.

F3 builds entirely on the F1 + F2 patterns (codegen → resource API module →
composable → form modal → view + AuthenticatedLayout slot). The only new
shared building blocks are:

- `InstrumentPicker.allowCreate` prop (extension of the existing component).
- A small `PositionStatusBadge` (read-only display of `open` / `closed`).
- The detail page tab-strip pattern, which other entities can reuse later if
  they grow tab-shaped detail surfaces.

## 2. Scope

### In scope (this plan)

- **`src/api/positions.ts`** — typed wrapper for the 5 P8 endpoints (`list`,
  `get`, `create`, `update`, `remove`) returning `PositionRead` with the
  always-present P12.1 `net_cash_flow` field.
- **`src/api/tradePlans.ts`** — typed wrapper for the 4 P11 endpoints
  (`list`, `current`, `byRevision`, `append`).
- **`src/api/strategyMeta.ts`** — typed wrapper for the 8 P10 endpoints (4 per
  strategy: wheel get/create/update/delete + pmcc get/create/update/delete),
  nested under `/positions/{pid}/wheel-meta` and `.../pmcc-meta`.
- **`usePositions()` composable** — list state with `status` + `strategy_type`
  filters and `refresh()`.
- **`usePosition(positionId)` composable** — single-position state for the
  detail page; refreshes on PATCH and on tab data changes.
- **`useTradePlans(positionId)` composable** — append-only event-stream
  state for the Plan tab.
- **`useWheelMeta(positionId)` / `usePmccMeta(positionId)` composables** —
  1:1 strategy-meta state for the Meta tab.
- **`InstrumentPicker.vue` extension** — add `allowCreate` prop. When set,
  the picker's dropdown grows a *"+ Create new instrument"* footer entry
  that opens `InstrumentForm.vue` (already shipped in F2) in create mode;
  on `@saved`, the newly created instrument is auto-selected. F3's first
  consumer of `allowCreate` is `PositionFormModal`.
- **`PositionStatusBadge.vue`** — tiny presentational component:
  `<n-tag>` colored by `status` (`open` = success / `closed` = default).
- **`PositionFormModal.vue`** — create / edit modal. On **create**: includes
  the F2 `InstrumentPicker` (with `allowCreate`) for `primary_instrument_id`,
  Account selector, `StrategyType` selector, `opened_at` (derived from first
  Trade), and the manual fields (`capital_used`, `max_risk_at_open`,
  `max_reward_at_open`, `notes`). On create-mode submit, the modal **first**
  must capture the first Trade — F3 ships the *form shell* with a "First
  Trade" subsection placeholder; **F4 wires the actual `TradeEntryModal`
  into that slot**. See §5.5 *Trade-led seam* for the contract. On
  **edit**: only manual fields are writable (`account_id`,
  `primary_instrument_id`, `strategy_type`, `opened_at`, `currency`,
  `pnl_realized`, `status` are immutable per P8 — disabled in the form).
- **`PositionsView.vue`** (`/positions`) — list with `status` filter
  (default `open`) + `strategy_type` filter + `+ New position` button.
  Columns: symbol (from joined instrument; for V1, look up via
  `useInstruments`), `strategy_type`, `opened_at`, `net_cash_flow` (currency
  prefixed; label *"Net Cash Flow"* when status=open, *"Realized P/L"* when
  status=closed — same column slot per
  [P12 detail plan §8](./backend-expansion-plan-p12.md#8-after-p12)),
  `currency`, status badge, "Open" action.
- **`PositionDetailView.vue`** (`/positions/:id`) — page with header (symbol,
  strategy, status badge, opened_at, currency, "Edit" + "Delete" + "Close"
  actions) and a `<n-tabs>` strip:
  - **Overview** — manual + derived fields, capital efficiency.
  - **Meta** — wheel funding/loan/interest form (when
    `strategy_type === 'wheel'`) or PMCC LEAP picker (when
    `strategy_type === 'pmcc'`); empty state for other strategies.
  - **Plan** — TradePlan event stream: oldest-first revision list +
    "+ New revision" form.
  - **Trades** — chronological trade list **read-only placeholder** in F3
    ("F4 will add the entry modal here"). F3 *does* render the existing
    trades for the position (consuming P9's `GET /api/trades?position_id=`)
    so the page is not blank for users who already have trades via curl;
    pattern badges and the entry modal are F4.
- **Router** — add `/positions` and `/positions/:id` routes.
- **`AuthenticatedLayout.vue`** — add `Positions` nav entry between
  `Instruments` and `Settings`.
- **`DashboardView.vue`** — flip the `Positions` placeholder card to an
  active link (count from `usePositions`); leave `Trades (F4)` and
  `Dashboards (F5)` disabled.
- **Codegen** — `frontend/src/api/schema.d.ts` is already fresh from P12;
  no new run required. If P8/P10/P11/P12 receive patch fixes during F3,
  re-run.
- **Backend regression** — keep ≥406 backend tests passing; ruff + mypy
  strict clean.

### Explicitly NOT in scope (deferred)

- **`TradeEntryModal.vue`** — F4. F3 ships the *first-Trade slot* on
  `PositionFormModal` and the *Trades-tab placeholder* on
  `PositionDetailView` as **agreed seams**, but the entry-modal
  implementation, multi-leg row UX, and inline `action↔kind` validation
  are F4.
- **Pattern badges on Trades tab** (Assignment / Exercise / Expiration /
  IC-open detection) — F4.
- **Soft-delete UI for trades** — F4.
- **Dashboard summary consumption** (`/api/dashboard/summary`) — F5.
- **Position `archived_at`** — not in V1 (V1 release plan Decision 4).
- **Strategy-meta for non-wheel / non-pmcc strategies** — backend P10
  has no extension tables for `iron_condor` / `spot_stock` /
  `spot_forex`; the Meta tab shows a "No metadata for this strategy"
  empty state.
- **Bulk position operations** — out of scope.
- **Pagination** on `/positions` — backend caps `limit=200`; sufficient
  for V1 scale. If real users exceed it the day after launch, revisit.
- **Frontend unit tests (Vitest)** — still no qualifying logic; backend
  pytest + `vue-tsc` + manual click-through suffice. The first plausible
  Vitest candidates land in F4 (`action↔kind` validation, pattern
  detection) per the V1 release plan §3.
- **Promoting `usePositions` to a Pinia store** — composable suffices;
  promote only when ≥2 components need shared reactivity beyond what
  `refresh()` covers.
- **Optimistic updates** — manual `refresh()` after every PATCH/POST
  remains the F1 pattern.
- **PMCC LEAP autosuggest** — F3 ships the LEAP picker as a
  `<InstrumentPicker :kind="'option'">` with the existing typeahead;
  filtering specifically for LEAP candidates (long-dated, deep-ITM call
  options on the position's underlying) is deferred — the user picks
  manually for V1.

## 3. Tech additions

**None.** Same stack as F1 + F2.

`<n-tabs>` (Naive UI), `<n-data-table>`, `<n-tag>`, `<n-form>`,
`<n-collapse>` are all already in the project. The only new module
imports are the new schema types.

## 4. Directory structure changes

```
frontend/src/
├── api/
│   ├── schema.d.ts                  ← already fresh post-P12
│   ├── positions.ts                 ← NEW
│   ├── tradePlans.ts                ← NEW
│   ├── strategyMeta.ts              ← NEW
│   ├── instruments.ts               ← unchanged
│   ├── strategyConfigs.ts           ← unchanged
│   ├── accounts.ts                  ← unchanged
│   ├── http.ts                      ← unchanged
│   └── types.ts                     ← unchanged
├── composables/
│   ├── usePositions.ts              ← NEW
│   ├── usePosition.ts               ← NEW
│   ├── useTradePlans.ts             ← NEW
│   ├── useWheelMeta.ts              ← NEW
│   ├── usePmccMeta.ts               ← NEW
│   ├── useAccounts.ts               ← unchanged
│   ├── useInstruments.ts            ← unchanged
│   └── useStrategyConfigs.ts        ← unchanged
├── components/
│   ├── AuthenticatedLayout.vue      ← CHANGED: add Positions nav
│   ├── InstrumentPicker.vue         ← CHANGED: add allowCreate prop
│   ├── PositionFormModal.vue        ← NEW
│   ├── PositionStatusBadge.vue      ← NEW
│   ├── WheelMetaForm.vue            ← NEW
│   ├── PmccMetaForm.vue             ← NEW
│   ├── TradePlanForm.vue            ← NEW (append-revision form)
│   ├── TradePlanList.vue            ← NEW (revision history)
│   ├── PositionTradesPlaceholder.vue ← NEW (F3 placeholder, F4 swaps it)
│   ├── InstrumentForm.vue           ← unchanged
│   ├── CurrencySelect.vue           ← unchanged
│   └── AccountFormModal.vue         ← unchanged
├── router/
│   └── index.ts                     ← CHANGED: add /positions + /positions/:id
└── views/
    ├── PositionsView.vue            ← NEW
    ├── PositionDetailView.vue       ← NEW
    ├── DashboardView.vue            ← CHANGED: Positions card link active
    ├── InstrumentsView.vue          ← unchanged
    ├── SettingsStrategiesView.vue   ← unchanged
    └── AccountsView.vue             ← unchanged
```

`PositionTradesPlaceholder.vue` is intentionally split out of
`PositionDetailView` so F4 can swap to `PositionTradesTab.vue` cleanly
without touching the parent.

## 5. Build deliverables

The agent / implementer can sequence these however they like; the only
hard ordering is **API clients → composables → form components → views →
nav wiring**. Below is a suggested order that keeps `npm run build`
green after each chunk.

### 5.1 API clients

**`src/api/positions.ts`** — typed wrapper around the 5 P8 endpoints +
`net_cash_flow` field (P12.1).

```ts
import type { components } from './schema'
import { http } from './http'

export type Position       = components['schemas']['PositionRead']
export type PositionCreate = components['schemas']['PositionCreate']
export type PositionUpdate = components['schemas']['PositionUpdate']
export type PositionStatus = components['schemas']['PositionStatus']
export type StrategyType   = components['schemas']['StrategyType']

export const positionsApi = {
  list: (params?: { status?: PositionStatus; strategy_type?: StrategyType; limit?: number }) =>
    http.get(`/api/positions${buildQuery(params)}`) as Promise<Position[]>,
  get:    (id: string) => http.get(`/api/positions/${id}`) as Promise<Position>,
  create: (payload: PositionCreate) =>
    http.post('/api/positions', payload) as Promise<Position>,
  update: (id: string, payload: PositionUpdate) =>
    http.patch(`/api/positions/${id}`, payload) as Promise<Position>,
  remove: (id: string) => http.delete(`/api/positions/${id}`) as Promise<null>,
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${qs.toString()}`
}
```

`net_cash_flow` is a string (Decimal) per `schema.d.ts`. The composable
exposes it as-is; views render via `Number(...)` for arithmetic or
`new Intl.NumberFormat(...).format(...)` for display.

**`src/api/tradePlans.ts`** — typed wrapper for P11. Append-only,
oldest-first list, "current" alias for the max-revision row.

```ts
import type { components } from './schema'
import { http } from './http'

export type TradePlan       = components['schemas']['TradePlanRead']
export type TradePlanCreate = components['schemas']['TradePlanCreate']

export const tradePlansApi = {
  list:    (positionId: string) =>
    http.get(`/api/positions/${positionId}/trade-plans`) as Promise<TradePlan[]>,
  current: (positionId: string) =>
    http.get(`/api/positions/${positionId}/trade-plans/current`) as Promise<TradePlan | null>,
  byRevision: (positionId: string, revisionNo: number) =>
    http.get(`/api/positions/${positionId}/trade-plans/${revisionNo}`) as Promise<TradePlan>,
  append:  (positionId: string, payload: TradePlanCreate) =>
    http.post(`/api/positions/${positionId}/trade-plans`, payload) as Promise<TradePlan>,
}
```

**`src/api/strategyMeta.ts`** — typed wrappers for the 8 P10 endpoints.

```ts
import type { components } from './schema'
import { http } from './http'

export type WheelMeta       = components['schemas']['WheelMetaRead']
export type WheelMetaCreate = components['schemas']['WheelMetaCreate']
export type WheelMetaUpdate = components['schemas']['WheelMetaUpdate']

export type PmccMeta        = components['schemas']['PmccMetaRead']
export type PmccMetaCreate  = components['schemas']['PmccMetaCreate']
export type PmccMetaUpdate  = components['schemas']['PmccMetaUpdate']

export const wheelMetaApi = {
  get:    (pid: string) => http.get(`/api/positions/${pid}/wheel-meta`) as Promise<WheelMeta>,
  create: (pid: string, payload: WheelMetaCreate) =>
    http.post(`/api/positions/${pid}/wheel-meta`, payload) as Promise<WheelMeta>,
  update: (pid: string, payload: WheelMetaUpdate) =>
    http.patch(`/api/positions/${pid}/wheel-meta`, payload) as Promise<WheelMeta>,
  remove: (pid: string) => http.delete(`/api/positions/${pid}/wheel-meta`) as Promise<null>,
}

export const pmccMetaApi = {
  get:    (pid: string) => http.get(`/api/positions/${pid}/pmcc-meta`) as Promise<PmccMeta>,
  create: (pid: string, payload: PmccMetaCreate) =>
    http.post(`/api/positions/${pid}/pmcc-meta`, payload) as Promise<PmccMeta>,
  update: (pid: string, payload: PmccMetaUpdate) =>
    http.patch(`/api/positions/${pid}/pmcc-meta`, payload) as Promise<PmccMeta>,
  remove: (pid: string) => http.delete(`/api/positions/${pid}/pmcc-meta`) as Promise<null>,
}
```

Per [P10 settled decisions](./backend-expansion-plan-p10.md), the GET
endpoint **404s** when no meta row exists yet — the composable maps that
to `meta.value = null` rather than treating it as an error.

The Trades fetch for the F3 placeholder reuses `/api/trades?position_id=`
(P9). We don't ship a full `src/api/trades.ts` in F3 — that's F4 — but we
do need a one-liner read path:

```ts
// inline in usePosition.ts (temporary; F4 promotes to src/api/trades.ts)
export interface Trade {
  id: string
  position_id: string
  instrument_id: string
  action: components['schemas']['TradeAction']
  quantity: string
  price: string
  commission: string
  fees: string
  cash_flow: string
  executed_at: string
  order_group_id: string | null
  notes: string | null
  archived_at: string | null
}
```

Use `components['schemas']['TradeRead']` directly if it's already in
`schema.d.ts` (it is, verified in §1 prereq).

### 5.2 Composables

**`usePositions()`** — mirrors `useAccounts`. State: `positions`,
`loading`, `error`, `statusFilter` (default `'open'`),
`strategyTypeFilter` (default `''` meaning all). Watch both filters; call
`refresh()` on change. Expose `refresh()`, `create(payload)` (calls
`positionsApi.create`, then `refresh()`).

```ts
export function usePositions() {
  const positions = ref<Position[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const statusFilter = ref<PositionStatus | ''>('open')
  const strategyTypeFilter = ref<StrategyType | ''>('')
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const status = statusFilter.value || undefined
      const strategy_type = strategyTypeFilter.value || undefined
      const result = await positionsApi.list({ status, strategy_type })
      if (seq === refreshSeq) positions.value = result
    } catch (e) {
      if (seq === refreshSeq) error.value = e instanceof ApiError ? e.message : 'Failed to load positions'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  watch([statusFilter, strategyTypeFilter], () => { void refresh() })
  return { positions, loading, error, statusFilter, strategyTypeFilter, refresh }
}
```

**`usePosition(positionId)`** — single-position state. State: `position`,
`loading`, `error`, `refresh()`, `update(payload)`, `close()` (PATCH
`status=closed`), `remove()`. The detail page calls `refresh()` on mount
and after any tab data mutation.

**`useTradePlans(positionId)`** — append-only event-stream state. State:
`revisions` (oldest-first), `current` (computed: `revisions[revisions.length - 1] ?? null`),
`loading`, `error`, `refresh()`, `append(payload)`.

**`useWheelMeta(positionId)` / `usePmccMeta(positionId)`** — 1:1 meta
state. State: `meta` (nullable — null when 404), `loading`, `error`,
`refresh()`, `createOrUpdate(payload)` (POST if `meta == null`, PATCH
otherwise), `remove()`.

All composables follow the F1/F2 pattern: `refreshSeq` for
last-requested-wins, `error` set from `ApiError.message`, no Pinia.

### 5.3 `InstrumentPicker.vue` — add `allowCreate` prop

F2 shipped `InstrumentPicker` as select-only. F3's
`PositionFormModal` needs inline-create when the user types a symbol
that isn't in the catalog yet (Trade-led model dictates that Positions
are often created for a fresh instrument).

**Prop addition.**

```ts
defineProps<{
  modelValue: string | null
  kind?: InstrumentKind
  placeholder?: string
  allowCreate?: boolean    // NEW — default false (preserves F2 callers)
}>()
```

**Behavior when `allowCreate === true`.** When the typeahead query
yields zero matches, the dropdown shows a footer row:

> **+ Create new instrument matching "<query>"**

Click → opens `InstrumentForm.vue` (already shipped in F2) in create
mode, with the kind preselected (if `:kind` prop is set on the picker)
and the `symbol` field pre-populated from the picker's query string. On
`@saved` from `InstrumentForm`, the picker:

1. Auto-selects the newly created instrument (emits `update:modelValue`
   with the new id).
2. Closes both the InstrumentForm modal and the picker dropdown.
3. Adds the new instrument to the picker's local `useInstruments` list
   (optimistic; the next `refresh()` will confirm) so it shows in the
   selected-display.

When `kind="option"`, follow the two-step UX
([V1 release plan Decision 1](./v1-release-plan.md#decision-1--instrumentpicker-get-or-create--allowcreate-prop)):
the picker first prompts to pick *underlying* (a stock-kind picker
inside `InstrumentForm`'s option tab), then the user fills the
contract attributes (`opt_type` / `strike` / `expiry` / `multiplier`)
as dedicated fields. `InstrumentForm` already implements this in F2;
the picker just passes the kind through.

When `kind` is **unspecified**, the picker covers all kinds — the
"Create new" footer opens `InstrumentForm` with its kind selector
visible. The user picks the kind in the form.

### 5.4 `PositionStatusBadge.vue`

A 10-line presentational component for the list table + detail page
header. No props beyond `status`.

```vue
<script setup lang="ts">
import type { PositionStatus } from '../api/positions'
defineProps<{ status: PositionStatus }>()
</script>

<template>
  <n-tag :type="status === 'open' ? 'success' : 'default'" size="small">
    {{ status === 'open' ? 'Open' : 'Closed' }}
  </n-tag>
</template>
```

### 5.5 `PositionFormModal.vue` (create / edit)

Single modal with create + edit modes via a `mode` prop.

**Fields, create mode.**

| Field                 | Component                          | Required | Notes |
|---|---|---|---|
| `account_id`          | `<n-select>` over `useAccounts()`  | ✅ | Filter excludes `archived_at != null`. |
| `primary_instrument_id` | `<InstrumentPicker :allowCreate>` | ✅ | Picker exposes inline-create. |
| `strategy_type`       | `<n-select>` over `StrategyType`   | ✅ | Default unset; required before submit. |
| `opened_at`           | `<n-date-picker type="datetime">`  | ✅ | **See "Trade-led seam" below.** |
| `capital_used`        | `<n-input-number>`                 | optional | currency-prefixed by selected instrument's currency. |
| `max_risk_at_open`    | `<n-input-number>`                 | optional | same. |
| `max_reward_at_open`  | `<n-input-number>`                 | optional | same. |
| `notes`               | `<n-input type="textarea">`        | optional | max 4000 chars (data-model §4.4). |
| (server-derived)      | currency                            | — | read-only badge shown next to `primary_instrument_id`; pulled from `useInstruments` once selected. |

**Fields, edit mode.** Only the manual subset is enabled
(`capital_used`, `max_risk_at_open`, `max_reward_at_open`, `notes`).
`account_id`, `primary_instrument_id`, `strategy_type`, `opened_at`,
status, `pnl_realized`, `currency`, `net_cash_flow` all rendered
**read-only** (disabled inputs) per
[P8 settled decisions](./backend-expansion-plan-p8.md). Closing the
position is a **separate action** (see "Close position" on the detail
header, §5.7) — not buried inside the edit modal.

#### Trade-led seam (the F3↔F4 contract)

Per [v1-release-plan Decision 5](./v1-release-plan.md#decision-5--derived-values-frontend-per-position-backend-for-lists--aggregates)
and the
[P8 model decision](./backend-expansion-plan.md#6-design-decisions), a
new Position must be born with a first Trade whose `executed_at` equals
`opened_at`. F3 cannot fully honor this on its own because the
TradeEntryModal is an F4 deliverable.

**F3 ships the seam, not the implementation:**

1. `PositionFormModal` (create mode) renders a **"First Trade" subsection**
   below the manual fields. Heading: *"This position will be created with
   its first Trade — required by the Trade-led model."* The subsection
   is **a placeholder slot** rendering `<PositionTradesPlaceholder mode="first-trade" />`:
   *"First Trade entry will be wired in F4."*
2. **Provisional F3 behavior, behind a `?legacy=true` query param only:**
   For development convenience while F4 is in-flight, allow submitting
   the form with `opened_at` typed manually. This path posts only the
   Position; the user can attach Trades via curl. **This is a dev
   crutch, removed by F4.** Production users on the deployed V1 will
   *never* see the create modal without F4 active because both ship
   inside the same V1 release.
3. **F4 contract.** F4 replaces `PositionTradesPlaceholder` (in the
   first-trade slot) with the real `TradeEntryModal` *inline form*
   (not a nested modal — the trade rows live inside the Position-create
   modal). F4 also wires the submit handler: a single POST
   `/api/positions` (server-derived `currency`), followed by a POST
   `/api/trades` with the first Trade(s); `opened_at` is set from the
   first Trade's `executed_at` automatically by the modal.

**Why ship F3 with a placeholder instead of finishing both at once.**
F3 is large already (5 components, 5 composables, 2 views, 8
endpoints' worth of API clients). F4 will be focused exclusively on
TradeEntryModal + Trades-tab logic; bundling the inline-Trade form
into F3 would smear the scope. The seam is small (one slot
component); F4's plan §X documents the exact swap.

**Submit handler (edit mode).**

```ts
await positionsApi.update(props.positionId, payload)
message.success('Position updated')
emit('saved')
```

**Submit handler (create mode), F3 dev crutch path.**

```ts
const position = await positionsApi.create(payload)
message.success(`Position created — attach first Trade via Trades tab (F4)`)
emit('saved', position)
```

The F4 plan will replace this with the atomic Position+Trade flow.

### 5.6 `PositionsView.vue` (`/positions`)

Layout (inside `<AuthenticatedLayout>`):

- **Page header** — title "Positions", right-aligned `+ New position`
  button (opens `PositionFormModal` in create mode).
- **Filter strip:**
  - `<n-select>` for status: All / Open / Closed; default Open.
  - `<n-select>` for `strategy_type`: All / Wheel / Iron Condor / PMCC /
    Spot Stock / Spot Forex (enum pulled from `schema.d.ts`).
  - Both bound to `usePositions()`.
- **`<n-data-table>`:**
  - **Symbol** (string) — joined from `useInstruments` map (build a
    `Record<id, Instrument>` from a single `/api/instruments?limit=200`
    fetch on view mount; cache for the life of the view).
  - **Strategy** — label from `StrategyType` enum, prettified
    (`wheel` → "Wheel", `iron_condor` → "Iron condor", etc.).
  - **Opened At** — `<n-time :time>` relative + tooltip with absolute UTC.
  - **Net Cash Flow / Realized P/L** — same column slot, label flips by
    row's `status`. Value: `position.net_cash_flow` formatted as
    `<currency> <amount>` (e.g. `USD 125.00`). Color-coded: green when
    positive, red when negative, neutral when zero. For closed rows,
    show `pnl_realized` instead (mathematically equal to
    `net_cash_flow` per P12 design, but semantically the "realized"
    framing matches the user's mental model when the position is
    closed).
  - **Currency** — derived from `position.currency`.
  - **Status** — `<PositionStatusBadge>`.
  - **Actions** — `Open` button → `router.push('/positions/{id}')`.
- **Empty state** — `<n-empty>` "No positions yet" with `+ New position`
  CTA.
- **Loading state** — `<n-spin>` over the table during `refresh()`.
- **Error state** — `<n-alert type="error">` with `error.value` text +
  retry button.

On `PositionFormModal @saved`: call `refresh()` and either close the
modal (edit mode) or navigate to the new position's detail page (create
mode).

### 5.7 `PositionDetailView.vue` (`/positions/:id`)

Layout:

- **Page header** card:
  - Left: instrument symbol (big), strategy type, `<PositionStatusBadge>`,
    opened_at + (if closed) closed_at, currency.
  - Right: action buttons:
    - **Edit** — opens `PositionFormModal` in edit mode.
    - **Close** — disabled when `status === 'closed'`; otherwise prompts
      `<n-popconfirm>` *"Close this position? `pnl_realized` will be
      frozen as SUM(trade.cash_flow). This cannot be undone."* On
      confirm, calls `usePosition.close()` → PATCH `status=closed` →
      `refresh()`.
    - **Delete** — `<n-popconfirm>` *"Delete this position? Only allowed
      when no trades are attached."* On confirm, calls
      `usePosition.remove()`. On 409 from backend (trades attached),
      surface the inline error message *"This position has attached
      trades and cannot be deleted. Archive trades first."*
- **`<n-tabs>` with `type="line"`** — four tabs in order: Overview /
  Meta / Plan / Trades. Tab selection synced to route query
  (`?tab=meta` / etc.) for deep-linking; default tab is Overview.

The four tabs:

#### 5.7.1 Overview tab

Two-column grid (Naive UI `<n-grid :cols="2">`):

- **Left column — manual fields card.** Read-only display of
  `capital_used`, `max_risk_at_open`, `max_reward_at_open`, `notes`
  (with the currency prefix). Below: an inline "Edit" link → opens
  `PositionFormModal` in edit mode.
- **Right column — derived computations card** (per V1 Decision 5:
  computed in frontend). Fields:
  - `days_open` — `Math.floor((closed_at ?? now - opened_at) / 86_400_000)`,
    label flips: "Days open" for status=open, "Days held" for closed.
  - `net_cash_flow` — server-supplied (`position.net_cash_flow`), shown
    with sign and currency.
  - `pnl_total` — for V1 = `net_cash_flow` (since unrealized is V1.x).
    Identical to the displayed `net_cash_flow`; the field title flips
    its label depending on status as in the list. Kept as a separate
    line so when V1.x adds unrealized, the formula slot already exists.
  - `roi_on_capital` — `(pnl_total / capital_used) * 100` when
    `capital_used > 0`; "—" otherwise. Format: `12.50%` (two decimal
    places).
  - `result` — when status=closed: `pnl_realized > 0 ? 'Win' : pnl_realized < 0 ? 'Loss' : 'Breakeven'`
    rendered as a `<n-tag>`. Hidden when status=open.

Formatting rules: amounts use `Intl.NumberFormat(undefined, {
minimumFractionDigits: 2, maximumFractionDigits: 4 })`; positive
amounts colored green, negative red. Constants like the milliseconds-
per-day live in a small `src/utils/positionDerived.ts` exporting
`computeDaysOpen`, `computePnlTotal`, `computeRoi`, `computeResult` —
**reused by F5** (the dashboard's open-positions table uses the
identical helpers per V1 Decision 5 consistency invariant).

#### 5.7.2 Meta tab

Rendered conditionally on `position.strategy_type`:

- **`wheel`** — `<WheelMetaForm :positionId>`:
  - Fields: `funding_source` (enum: `cash` / `margin` / `loan`),
    `loan_amount`, `interest_rate_apr` (percentage), `interest_accrued`.
  - Calls `useWheelMeta(positionId)`. On mount: `refresh()` (gets 200 with
    row, or 404 → `meta = null`).
  - When `meta === null`: show inline form pre-filled with defaults
    (`funding_source = 'cash'`, rest empty) and a "Create wheel meta"
    submit button. Calls `createOrUpdate(payload)` which POSTs.
  - When `meta !== null`: render the same form pre-filled, with "Save"
    + "Delete meta" buttons. "Save" calls PATCH; "Delete meta" calls
    DELETE (with `<n-popconfirm>`).
- **`pmcc`** — `<PmccMetaForm :positionId>`:
  - Single field: `leap_instrument_id` via `<InstrumentPicker kind="option">`
    (NOT `allowCreate` — LEAP must be an existing option; if missing, user
    creates it in `/instruments` first then comes back).
  - **Validation hint:** A read-only note: *"LEAP must be an option on
    the same underlying as this position's primary instrument. The
    backend enforces this — pickers don't filter for it in V1."*
  - Same create-vs-edit branch as `WheelMetaForm`.
- **`iron_condor` / `spot_stock` / `spot_forex`** — empty state:
  `<n-empty>` *"No metadata for {strategy} positions in V1."*

Strategy-type-to-component dispatch happens in `PositionDetailView`'s
template via `v-if`; the form components themselves don't know about
other strategies.

#### 5.7.3 Plan tab

`<TradePlanList :positionId>` + `<TradePlanForm :positionId>` stacked
vertically.

- **`<TradePlanList>`** — calls `useTradePlans(positionId).refresh()` on
  mount. Renders a `<n-timeline>` (or `<n-list>`) of revisions
  oldest-first. Each entry: revision number, `effective_at` (relative +
  tooltip), `planned_entry`, `planned_stop_loss`, `planned_take_profit`,
  `target_rr`, `thesis` (truncated; expand-on-click). "Current" badge on
  the last entry (`revisions[revisions.length - 1]`).
- **`<TradePlanForm>`** — `+ Append revision` button → expands to a form
  below with: `effective_at` (datetime picker, default now),
  `planned_entry` / `planned_stop_loss` / `planned_take_profit`
  (`<n-input-number>` decimals), `target_rr` (`<n-input-number>`,
  optional), `thesis` (`<n-input type="textarea">`, max 8000 chars). On
  submit: `useTradePlans.append(payload)` → list auto-refreshes (the
  composable's `append()` triggers `refresh()`).

Empty state (when no revisions): `<n-empty>` *"No plan revisions yet"* +
the same append form pre-expanded.

#### 5.7.4 Trades tab (F3 placeholder)

`<PositionTradesPlaceholder :positionId>`:

- On mount: fetch `/api/trades?position_id={positionId}` (P9). Render
  rows in a `<n-data-table>` with columns: `executed_at`, `action`
  badge, `instrument` (joined symbol), `quantity`, `price`,
  `cash_flow`. **Read-only** — no edit, delete, or entry actions.
- Above the table: `<n-alert type="info">` *"Trade entry — including
  multi-leg flows — will land in F4. For now, trades created via
  the API or the Position-create flow's first-Trade subsection
  appear here read-only."*
- When zero trades: `<n-empty>` *"No trades yet on this position."*

F4 will replace this entire component with `PositionTradesTab.vue`
that adds the entry modal, pattern badges, soft-delete UX, and
`order_group_id` visual grouping. **No file-shape changes required
in `PositionDetailView`** — the import target is the same, only the
component implementation changes. Hence the F3 file is named
`PositionTradesPlaceholder.vue` (descriptive) and F4 will add a new
`PositionTradesTab.vue` alongside; the v-if in `PositionDetailView`
flips between them based on feature-detection rules F4 defines.
Alternatively F4 simply renames in place; either way is fine.

### 5.8 Router changes

```ts
// src/router/index.ts (excerpt)
{
  path: '/positions',
  name: 'positions',
  component: () => import('../views/PositionsView.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/positions/:id',
  name: 'position-detail',
  component: () => import('../views/PositionDetailView.vue'),
  meta: { requiresAuth: true },
  props: true,
},
```

The `props: true` flag lets `PositionDetailView` receive `id` as a
prop, avoiding `useRoute()` boilerplate.

### 5.9 `AuthenticatedLayout.vue` + `DashboardView.vue` updates

**`AuthenticatedLayout.vue`** — add `Positions` between `Instruments`
and `Settings`. Final nav order:

```
Dashboard | Accounts | Positions | Instruments | Settings
```

**`DashboardView.vue`** — flip the `Positions` placeholder to an active
card:

| Card | Content | Link |
|---|---|---|
| Your accounts | count from `useAccounts` | `/accounts` |
| Instruments | count from `useInstruments` | `/instruments` |
| **Positions** | count from `usePositions` (status=`open`) | `/positions` |
| Strategy caps | count from `useStrategyConfigs` | `/settings/strategies` |
| Trades (Phase F4) | disabled | none |
| Dashboards (Phase F5) | disabled | none |

The Positions card shows the open-position count, since the list view
defaults to open.

## 6. Codegen workflow

Same operational pattern as
[F2 §6](./frontend-implementation-plan-f2.md#6-codegen-workflow).

F3-specific reminders:

- `schema.d.ts` is already fresh post-P12. If P8/P10/P11/P12 receive
  any patch fixes during F3 work, re-run `npm run codegen` and commit
  the diff.
- F3 introduces **no new backend endpoints**, so the routine F3 PR
  should not modify `schema.d.ts`. If it does, that's a signal that
  something on the backend side was touched — review carefully.
- CI codegen gate: still recommended to bundle with F3 if not already
  shipped (see
  [frontend-expansion-plan §5](./frontend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked)).

## 7. Testing approach

Same as F0 / F1 / F2 — **no automated frontend tests in F3**. Backend
pytest is the regression guard. `npm run build` (`vue-tsc`) typechecks
the frontend.

**Frontend regressions to watch.** F3 changes `InstrumentPicker` (adds
`allowCreate` prop). Existing F2 callers (`InstrumentsView` search
field) MUST continue to behave the same — `allowCreate` defaults to
false, preserving select-only behavior. Manual verification §8 step
10 covers this.

Backend regression remains the hard gate. Must stay green after every
chunk of F3 work.

## 8. Manual verification recipe

Run end-to-end against `uvicorn` + `npm run dev` after the full F3
surface is built. Prerequisite: backend on `127.0.0.1:8000` with
P8/P9/P10/P11/P12 all deployed and migrated; frontend on
`localhost:5173`; SSH tunnel forwarding both; fresh DB.

> **Note on the Trade-led seam.** Steps below that create Positions use
> the F3 dev-crutch path (§5.5) — the first Trade is created via API
> directly. Once F4 ships, the Position-create modal will handle this
> atomically.

1. Register `alice@example.com` / `correct horse battery` → land on `/`
   → Dashboard shows 6 cards (Your accounts, Instruments, **Positions**,
   Strategy caps, Trades [F4] disabled, Dashboards [F5] disabled), all
   counts = 0.
2. Header nav shows: Dashboard | Accounts | Positions | Instruments |
   Settings.
3. Create prerequisites: Accounts → `+ New account` → Cash USD account.
   Instruments → `+ New instrument` → Stock `AAPL` USD NASDAQ.
4. Click `Positions` → `/positions`; empty state visible. Status filter
   defaults to `Open`.
5. Click `+ New position`:
   - Account dropdown shows Cash USD.
   - Click `primary_instrument_id` picker — typeahead `AAPL`, select.
     **Currency badge** appears showing `USD` next to the picker.
   - Strategy dropdown — select `Spot Stock`.
   - opened_at — pick now (datetime).
   - capital_used — 1000.
   - max_risk_at_open / max_reward_at_open / notes — leave blank.
   - **First Trade subsection** shows placeholder text: *"First Trade
     entry will be wired in F4."*
   - Submit → toast *"Position created — attach first Trade via
     Trades tab (F4)"*; navigate to `/positions/{id}`.
6. Detail page renders with header: AAPL Spot Stock badge=Open opened_at
   USD. Edit / Close / Delete buttons visible.
7. Overview tab active. Manual fields card shows `capital_used: USD
   1000.00`, rest "—". Derived card: `days_open: 0`, `net_cash_flow:
   USD 0.00`, `pnl_total: USD 0.00`, `roi_on_capital: 0.00%`, `result`
   hidden.
8. Click **Edit** → modal opens in edit mode. Account / Instrument /
   Strategy / opened_at / status all disabled. Change `notes` to "test
   note" → save → toast → notes appears in Overview card.
9. Switch to **Meta** tab → for `spot_stock`, see empty state *"No
   metadata for spot_stock positions in V1"*.
10. Switch to **Plan** tab → empty state with append form pre-expanded.
    Fill `effective_at` now, `planned_entry: 170`, `planned_stop_loss:
    160`, `planned_take_profit: 200`, `target_rr: 3.0`, `thesis:
    "earnings catalyst Q2"` → submit → revision 1 appears with
    "Current" badge.
11. Append a second revision (`effective_at` +1 hour, change
    `planned_stop_loss` to 165) → revision 2 appears below revision 1
    (oldest-first); "Current" badge moves to revision 2.
12. Switch to **Trades** tab → info alert visible, empty table.
13. From `/instruments` create an Option AAPL P 220 expiry+30d. Use
    curl (one-shot) to attach a Trade to the position:
    ```bash
    curl -fsSi http://localhost:8000/api/trades -b cookies.txt \
      -H 'Content-Type: application/json' \
      -d '{"position_id":"<pid>","instrument_id":"<stock_iid>",
           "action":"buy","quantity":"10","price":"170.50",
           "executed_at":"<opened_at>"}'
    ```
    Return to Trades tab → row visible read-only.
14. Refresh `/positions` list → AAPL Spot Stock row visible.
    `net_cash_flow` column reads `-USD 1705.00` (buy → negative cash
    flow) in red. Status column = Open badge.
15. **Verify `allowCreate` inline-create.** Click `+ New position` →
    in `primary_instrument_id` picker, type `TSLA` (not yet in
    catalog). The dropdown shows footer *"+ Create new instrument
    matching 'TSLA'"* → click → InstrumentForm opens with Stock tab
    selected, symbol pre-filled `TSLA`. Fill USD NASDAQ → submit →
    toast `Created TSLA` → InstrumentForm closes; picker auto-selects
    TSLA. Cancel the position-create modal (we don't want to commit a
    TSLA position in this test).
16. **Verify `allowCreate` does not break F2 callers.** Go to
    `/instruments` → the search box (which is an `InstrumentPicker`
    instance from F2) should still behave as select-only — no
    `+ Create` footer appears when query yields no matches. (The F2
    caller does not pass `allowCreate`.)
17. **Close a position.** Back to AAPL detail. Click **Close** →
    popconfirm. Confirm → toast → status badge flips to Closed,
    closed_at populated, Overview's `result` line appears ("Loss" if
    `pnl_realized < 0`; the buy alone produces a negative cash flow,
    so the result is Loss). The position now matches the "Realized
    P/L" column label in the list when filtered to Closed.
18. **Verify status filter.** Back to `/positions`. Status filter →
    `Closed` → AAPL row visible with "Realized P/L" label on the
    money column. `Open` → empty. `All` → AAPL row visible.
19. **Delete protection.** Detail of AAPL → **Delete** → popconfirm →
    confirm → expected error: *"This position has attached trades
    and cannot be deleted."* (Backend returns 409 due to the trade
    from step 13.)
20. Create a fresh Position without trades via the F3 modal (skip
    step 13's curl). Now **Delete** succeeds → navigate back to
    `/positions`, row gone.
21. **Wheel meta.** Create a Position with `strategy_type=wheel` on
    the AAPL stock. Go to Meta tab → empty wheel form (defaults
    `funding_source=cash`). Switch `funding_source` to `loan`, fill
    `loan_amount: 5000`, `interest_rate_apr: 7.5`, `interest_accrued:
    20` → "Create wheel meta" → success → form persists in edit mode
    with "Save" + "Delete meta" buttons. Reload page → values
    persisted.
22. **PMCC meta.** Create a Position with `strategy_type=pmcc` on the
    AAPL stock. Meta tab → form with single `leap_instrument_id`
    picker (option-kind). Pick the AAPL P 220 option from step 13 →
    "Create pmcc meta" → success. (Backend will reject if the option's
    underlying isn't AAPL; for this test it is, so success.)
23. **Cross-user isolation (optional).** Register `bob@example.com`,
    log in as Bob, navigate to `/positions` → empty. Try to navigate to
    Alice's position URL directly → 404 page (backend returns 404 per
    P8). Verify no leakage.
24. Backend log throughout: only expected requests; no 500s, no
    IntegrityErrors. After every step, `pytest -q` still green.

## 9. After F3

Once F3 ships, the next iteration is
[F4 — Trade entry](./frontend-expansion-plan.md#f4--trade-entry),
which consumes backend P9 (already shipped). F4 will:

- Build `src/api/trades.ts` proper (replacing the inline `Trade` type in
  `usePosition`).
- Build `TradeEntryModal` with Custom multi-leg form (V1 Decision 2 — no
  named flows in V1).
- Wire `TradeEntryModal` into `PositionFormModal`'s **First Trade
  subsection** so Position+Trade creation becomes atomic per the
  Trade-led model. Remove the F3 dev-crutch path (§5.5 step 2).
- Replace `PositionTradesPlaceholder` with `PositionTradesTab`: pattern
  badges (Assignment / Exercise / Expiration / IC-open), `order_group_id`
  visual grouping, soft-delete UX (P9 `archived_at`).
- Add a "+ New trade" button to the Position detail page's Trades tab
  and Overview card (V1 Decision: Add Trade entry lives only on Position
  detail).

If the **CI codegen gate** wasn't bundled with F2, F3 is also a fine
slot. F3 doesn't change any schemas, but the test stretch (registering,
positions, plans, meta) flushes out most surfaces — a passing codegen
job after F3 means F4 starts from a clean baseline.

A small follow-up worth tracking: extract the date-helper utilities
(`computeDaysOpen` etc.) from §5.7.1 into `src/utils/positionDerived.ts`
during F3 — F5 will import them for the dashboard's per-row derived
display.

---

## Changelog

- **v0.1 (2026-05-28)** — Initial F3 plan. Three structural decisions
  settled with user on 2026-05-28:
  1. **Position detail page format:** independent page `/positions/:id`
     with the four-tab strip (Overview / Meta / Plan / Trades) per the
     V1 release plan §6.2 original design.
  2. **"Add trade" entry point:** Position detail only; brand-new
     Positions are born via F3's `+ New position` flow with a
     **first-Trade subsection** that F4 wires.
  3. **F4 named-flow shortlist:** zero — Custom multi-leg is the only
     entry mode for V1 (decision lives in the F4 plan, recorded here for
     context).
  Plan covers: 5 new API clients (positions / tradePlans / strategyMeta
  with wheel + pmcc), 5 new composables, `InstrumentPicker.allowCreate`
  extension, `PositionFormModal` + 4 supporting form/list components,
  `PositionsView` + `PositionDetailView` with 4 tabs. The
  TradeEntryModal is **a deliberate seam** documented in §5.5 — F3
  ships the slot, F4 fills it. Trade-led atomic Position+Trade
  creation lands in F4. No new dependencies; no internal sub-phases.
