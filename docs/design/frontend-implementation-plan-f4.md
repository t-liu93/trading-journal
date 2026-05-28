# Frontend Phase F4 — Trade Entry UI

**Language:** English | [中文](./frontend-implementation-plan-f4.zh.md)

> Status: **DRAFT v0.1** (2026-05-28). Companion to
> [frontend-expansion-plan.md](./frontend-expansion-plan.md) (macro roadmap),
> [v1-release-plan.md](./v1-release-plan.md) (V1 north star),
> [frontend-implementation-plan-f3.md](./frontend-implementation-plan-f3.md) (F3
> pattern reference + the seams F4 fills), [data-model.md](./data-model.md)
> (esp. [§4.5 Trade](./data-model.md#45-trade-atomic-event) and
> [§4.5.2 Notion-event ↔ atomic-trade mapping](./data-model.md#452-notion-event--atomic-trade-mapping)),
> and the backend plan
> [backend-expansion-plan-p9.md](./backend-expansion-plan-p9.md) (Trade).
> Iterate here before writing code.

## 1. Purpose

F4 sits on top of backend **P9** (Trade CRUD) and the F3 seams. It delivers
the journal's primary data-entry workhorse:

- A typed `src/api/trades.ts` client (replacing the inline `Trade` type F3
  put in `usePosition.ts`).
- A reusable `TradeEntryModal.vue` — the Custom multi-leg form per
  [V1 release plan Decision 2](./v1-release-plan.md#decision-2--f4-trade-entry-custom-multi-leg-primary).
  Add/remove leg rows; all rows in one submission share one server-assigned
  `order_group_id` (P9 multi-leg POST).
- Wiring `TradeEntryModal` into **two** consumer sites:
  1. **F3 `PositionFormModal` first-Trade subsection** — fulfils the
     Trade-led model (Position is born atomically with first Trade).
     Replaces the F3 dev-crutch path documented in
     [F3 §5.5](./frontend-implementation-plan-f3.md#55-positionformmodalvue-create--edit).
  2. **`PositionDetailView` Trades tab + Overview** — `+ New trade` button
     on subsequent Trades.
- `PositionTradesTab.vue` — replaces F3's `PositionTradesPlaceholder` with
  the live Trades view: `order_group_id` visual grouping, pattern-detected
  badges (Assignment / Exercise / Expiration / IC-open), and soft-delete
  UX (P9 `archived_at`).

After F4 ships, **manual data entry is complete**. F5 reads aggregates,
F6 ships the artifact. No further entry flows are required for V1.

F4 builds on the F1/F2/F3 patterns; the only fundamentally new pattern is
**multi-leg row dynamics inside a single form**, which is small enough to
not warrant a shared abstraction yet.

### Named flows — settled

V1 release plan §4 Decision 2 deferred the named-flow shortlist to this
detail plan. **Settled 2026-05-28: zero named flows in V1.** Custom
multi-leg is the only entry mode. Rationale:

- The Trades tab still gets pattern badges based on submitted row shape,
  so the *display* surfaces strategy patterns even though the *entry*
  doesn't enforce them.
- A future V1.x can add helpers (e.g., "Expire worthless" → fills one row
  with qty 0 / price 0 / fees 0) once real usage shows which patterns the
  user enters most often. Adding helpers atop Custom multi-leg is
  additive — the data shape is unchanged.
- Shipping zero named flows keeps F4 sharply scoped: one modal, one form,
  one set of validation rules. Risk of UX bugs and broker-style spoofing
  is minimized.

## 2. Scope

### In scope (this plan)

- **`src/api/trades.ts`** — typed wrapper for the 4 P9 endpoints
  (`list`, `create` — single or array body, `update` — notes only, `remove`
  — soft-delete). Replaces the inline `Trade` type F3 wedged into
  `usePosition.ts`.
- **`useTrades(positionId)` composable** — list state for one position
  with `includeArchived` toggle; `refresh()`, `createMany(rows)`,
  `archive(id)`, `unarchive(id)` (V1 archive button only; unarchive
  exposed via the include-archived toggle + a row action).
- **`TradeEntryModal.vue`** — Custom multi-leg form (V1 Decision 2).
  Internally renders a list of leg rows, each with the full Trade-create
  field set. Add/remove rows; submit posts the array (or a single object
  if one row) to `/api/trades`. **Used in two modes:**
  - **standalone** (Trades tab + Overview `+ New trade`) — `positionId`
    is fixed, modal posts directly.
  - **inline-in-PositionFormModal** (first-Trade subsection) — the modal
    *exposes* its row state to its parent so `PositionFormModal` can
    orchestrate the atomic "POST /positions then POST /trades" sequence
    described in §5.4.
- **`PositionTradesTab.vue`** — the live Trades tab implementation
  replacing F3's placeholder. Renders the position's trades in a `<n-list>`
  visually grouped by `order_group_id`; each group shows a pattern badge
  (see §5.5); `+ New trade` button opens `TradeEntryModal` in standalone
  mode; row-level archive / unarchive; archive toggle.
- **`PositionFormModal.vue` (modified)** — replace the F3 placeholder slot
  with the embedded `TradeEntryModal` inline form (NOT a nested modal —
  rows live inside `PositionFormModal`). Atomic submit handler:
  1. POST `/api/positions` with `opened_at` derived from
     `firstTrade.executed_at`.
  2. POST `/api/trades` with the first-Trade row array, `position_id`
     filled from step 1.
  3. On any failure between (1) and (2), surface a recoverable error and
     leave the user on the form. The Position created in step 1 stays
     orphaned (no trades) — the user can either retry the Trade submit or
     delete the orphan from `/positions`. See §5.4 "Failure recovery".
  Remove the F3 dev-crutch `?legacy=true` path entirely.
- **`PositionDetailView.vue` (modified)** — swap import:
  `PositionTradesPlaceholder` → `PositionTradesTab`. Add a small
  `+ Add trade` action on the Overview card (right side, secondary
  button) that opens `TradeEntryModal` in standalone mode. The Overview's
  derived computations card automatically updates after a trade lands
  (via `usePosition.refresh()`).
- **`DashboardView.vue`** — flip the Trades placeholder card to active
  (count from `useTradesTotalCount` — see §5.7 — or a derived computed
  off `useTrades` for all positions; lean: simplest aggregate the
  dashboard can already get is via the F5 path, so for F4 just label the
  card "Trades" without a count).
- **Codegen** — `schema.d.ts` already includes the Trade schemas; no new
  endpoints in F4 (P9 already shipped). Re-run only if any P9 patch lands.
- **Backend regression** — ≥406 backend tests passing; `ruff` + `mypy
  --strict` clean.

### Explicitly NOT in scope (deferred)

- **Named-flow helpers** (Expire, Assignment, Exercise, IC-open
  templates) — V1.x. Custom multi-leg is the only entry surface in V1.
- **Bulk import / CSV** — V1.x.
- **Broker API ingestion** — V1.x; needs `BrokerCredential` and an
  auth-and-security layer not in V1.
- **Edit-in-place for Trade fields other than `notes`** — P9 explicitly
  makes Trade immutable except `notes` (audit integrity). UI matches: the
  only edit action on a Trade row is "Edit notes". Other corrections
  require archive-and-re-enter.
- **Cross-position trade view** (a global `/trades` page) — V1 doesn't
  need it; F5 dashboard summarises across positions instead.
- **Pattern-badge cross-position detection** — badges are scoped within a
  single `order_group_id`. No "we noticed your stock was assigned by the
  option you sold last week" cross-group inference; assignment detection
  works only when both legs share the same group.
- **Frontend unit tests (Vitest)** — the two F4 candidates per
  [V1 release plan §3](./v1-release-plan.md#in-v1-must-have) are
  `action↔kind` validation and pattern badge detection. **Defer Vitest
  unless badge detection grows non-trivial** — at V1 scope both functions
  are ~30-line pure helpers covered by the manual recipe. Adding Vitest
  is a clean V1.x follow-up if either function gains branches.
- **`order_group_id` editing post-submit** — server doesn't expose it;
  out of scope.
- **Trade-create from `TradeAction.archived_at` other endpoints** — out
  of scope.

## 3. Tech additions

**None.** Same stack as F1 + F2 + F3.

A `useDebouncedRef` (~10 lines) may be reused for the cash-flow preview
display if computing per-row cash-flow on every keystroke proves laggy;
otherwise skipped.

## 4. Directory structure changes

```
frontend/src/
├── api/
│   ├── trades.ts                       ← NEW (replaces inline F3 type)
│   ├── positions.ts                    ← unchanged
│   ├── tradePlans.ts                   ← unchanged
│   ├── strategyMeta.ts                 ← unchanged
│   ├── instruments.ts                  ← unchanged
│   ├── strategyConfigs.ts              ← unchanged
│   ├── accounts.ts                     ← unchanged
│   ├── http.ts                         ← unchanged
│   └── types.ts                        ← unchanged
├── composables/
│   ├── useTrades.ts                    ← NEW
│   ├── usePosition.ts                  ← CHANGED: drop inline Trade type, import from trades.ts
│   └── (others unchanged)
├── components/
│   ├── TradeEntryModal.vue             ← NEW
│   ├── TradeLegRow.vue                 ← NEW (a single editable row inside TradeEntryModal)
│   ├── TradeActionBadge.vue            ← NEW (tiny presentational, like PositionStatusBadge)
│   ├── PositionTradesTab.vue           ← NEW (replaces PositionTradesPlaceholder consumer)
│   ├── PositionTradesPlaceholder.vue   ← KEEP for now, used only by …  See §5.5 "Deletion path".
│   ├── PositionFormModal.vue           ← CHANGED: replace first-Trade placeholder with inline TradeEntryModal
│   ├── InstrumentPicker.vue            ← unchanged (allowCreate already from F3)
│   └── (other components unchanged)
├── utils/
│   ├── tradeCashFlow.ts                ← NEW (client-side cash-flow preview)
│   └── tradePatternBadge.ts            ← NEW (pattern detection over a group)
├── router/
│   └── index.ts                        ← unchanged
└── views/
    ├── PositionDetailView.vue          ← CHANGED: import PositionTradesTab; add Overview "+ Add trade"
    ├── DashboardView.vue               ← CHANGED: Trades card label (count optional)
    └── (other views unchanged)
```

`utils/` is a new top-level folder if it doesn't exist after F3 (per F3
§9 a `positionDerived.ts` is recommended to live there); F4 adds two
companion helpers.

## 5. Build deliverables

Suggested ordering: **API client → composable → helpers → presentational
components → TradeEntryModal → PositionTradesTab → wiring into existing
views**. The atomic Position+Trade wiring (§5.4) lands last because it
depends on `TradeEntryModal` being importable in inline mode.

### 5.1 API client

**`src/api/trades.ts`** — typed wrapper for the 4 P9 endpoints.

```ts
import type { components } from './schema'
import { http } from './http'

export type Trade        = components['schemas']['TradeRead']
export type TradeCreate  = components['schemas']['TradeCreate']
export type TradeUpdate  = components['schemas']['TradeUpdate']  // notes only
export type TradeAction  = components['schemas']['TradeAction']

export const tradesApi = {
  list: (params?: {
    position_id?: string
    order_group_id?: string
    include_archived?: boolean
  }) => http.get(`/api/trades${buildQuery(params)}`) as Promise<Trade[]>,

  /** Single-row create. Backend leaves order_group_id NULL. */
  create: (payload: TradeCreate) =>
    http.post('/api/trades', payload) as Promise<Trade>,

  /** Multi-leg create. Backend assigns one shared order_group_id across all rows. */
  createMany: (payloads: TradeCreate[]) =>
    http.post('/api/trades', payloads) as Promise<Trade[]>,

  update: (id: string, payload: TradeUpdate) =>
    http.patch(`/api/trades/${id}`, payload) as Promise<Trade>,

  /** Soft-delete (sets archived_at). */
  remove: (id: string) =>
    http.delete(`/api/trades/${id}`) as Promise<null>,
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (entries.length === 0) return ''
  const qs = new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))
  return `?${qs.toString()}`
}
```

Important: the **same `/api/trades` POST endpoint** accepts both shapes
(object or array) per
[P9 settled decisions](./backend-expansion-plan-p9.md). `create` for the
1-row path is just an ergonomic alias.

### 5.2 Composable

**`useTrades(positionId)`** — single-position trade list.

```ts
export function useTrades(positionId: string) {
  const trades = ref<Trade[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const includeArchived = ref(false)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await tradesApi.list({
        position_id: positionId,
        include_archived: includeArchived.value,
      })
      if (seq === refreshSeq) trades.value = result
    } catch (e) {
      if (seq === refreshSeq)
        error.value = e instanceof ApiError ? e.message : 'Failed to load trades'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  async function createMany(rows: TradeCreate[]): Promise<Trade[]> {
    const created = rows.length === 1
      ? [await tradesApi.create(rows[0])]
      : await tradesApi.createMany(rows)
    await refresh()
    return created
  }

  async function archive(id: string): Promise<void> {
    await tradesApi.remove(id)
    await refresh()
  }

  watch(includeArchived, () => { void refresh() })
  return { trades, loading, error, includeArchived, refresh, createMany, archive }
}
```

### 5.3 Helpers

**`src/utils/tradeCashFlow.ts`** — client-side cash-flow preview (display
only; server is the source of truth per
[P9 §6④](./backend-expansion-plan.md#6-design-decisions)).

```ts
import type { TradeAction, TradeCreate } from '../api/trades'
import type { Instrument } from '../api/instruments'

const SIGN: Record<TradeAction, -1 | 1> = {
  buy: -1, bto: -1, btc: -1,
  sell: 1, sto: 1, stc: 1,
}

/**
 * Mirrors the backend formula in P9 §6④. Display only — never sent to
 * the server (P9 Create schema rejects client-supplied cash_flow).
 */
export function previewCashFlow(
  row: Pick<TradeCreate, 'action' | 'price' | 'quantity' | 'commission' | 'fees'>,
  instrument: Pick<Instrument, 'kind'> & { multiplier?: number | null },
): number {
  const sign = SIGN[row.action]
  const price = Number(row.price)
  const qty = Number(row.quantity)
  const multiplier =
    instrument.kind === 'option' && instrument.multiplier != null
      ? Number(instrument.multiplier)
      : 1
  const commission = Number(row.commission ?? 0)
  const fees = Number(row.fees ?? 0)
  return sign * price * qty * multiplier - commission - fees
}

export function isValidActionForKind(
  action: TradeAction,
  kind: Instrument['kind'],
): boolean {
  if (action === 'buy' || action === 'sell') return kind !== 'option'
  // bto/sto/btc/stc are option-only
  return kind === 'option'
}
```

**`src/utils/tradePatternBadge.ts`** — pattern detection over a group of
trades that share one `order_group_id`. Mirrors
[data-model §4.5.2](./data-model.md#452-notion-event--atomic-trade-mapping).

```ts
import type { Trade } from '../api/trades'
import type { Instrument } from '../api/instruments'

export type PatternBadge = 'assignment' | 'exercise' | 'expiration' | 'ic-open' | null

export function detectPattern(
  group: Trade[],
  instrumentMap: Record<string, Instrument>,
): PatternBadge {
  if (group.length === 0) return null

  const enriched = group.map(t => ({
    trade: t,
    instrument: instrumentMap[t.instrument_id],
  }))

  // IC-open: 4 option legs in one group, no stock
  if (
    group.length === 4 &&
    enriched.every(e => e.instrument?.kind === 'option') &&
    enriched.every(e => e.trade.action === 'sto' || e.trade.action === 'bto')
  ) {
    return 'ic-open'
  }

  const options = enriched.filter(e => e.instrument?.kind === 'option')
  const stocks = enriched.filter(e => e.instrument?.kind === 'stock')

  // Expiration: single option leg, price=0
  if (group.length === 1 && options.length === 1 && Number(group[0].price) === 0) {
    return 'expiration'
  }

  // Assignment / Exercise: 1 option close + 1 stock fill
  if (group.length === 2 && options.length === 1 && stocks.length === 1) {
    const optTrade = options[0].trade
    const isOptClose = optTrade.action === 'btc' || optTrade.action === 'stc'
    if (isOptClose && Number(optTrade.price) === 0) {
      // 'assignment' for short option (stc/btc) becoming a stock position;
      // 'exercise' for long option (btc) being exercised.
      // V1 simple rule: short-side close → assignment; long-side close → exercise.
      return optTrade.action === 'btc' ? 'exercise' : 'assignment'
    }
  }

  return null
}
```

Both helpers are pure functions; if Vitest is desired later, they're the
clean unit-test candidates.

### 5.4 `TradeEntryModal.vue` + `PositionFormModal` atomic flow

The Custom multi-leg form (V1 Decision 2). Two consumption modes:

**Standalone mode** (Trades tab `+ New trade`, Overview `+ Add trade`):
- Props: `:show` (v-model), `:positionId` (required), `:accountId`
  (required, derived from the parent Position).
- Renders 1 leg row by default; `+ Add leg` button appends; `Remove` per
  row (visible only when >1 row exists; the last row cannot be removed).
- Submit: collect rows, fill `position_id` + (server-derived) on each,
  call `tradesApi.create()` for 1 row or `createMany()` for ≥2.
- On success: emit `@saved`, parent closes modal + refreshes.

**Inline mode** (inside `PositionFormModal` first-Trade subsection):
- Props: `:show=false` (never shows as a modal in this mode), `:inline=true`,
  `:accountId` from the parent's `account_id` field.
- Renders rows but **does not submit on its own**. Exposes via
  `defineExpose({ rows, validate })` so `PositionFormModal` can read the
  rows during its atomic submit.
- The parent (`PositionFormModal`) wires:
  ```ts
  async function submitCreate() {
    const rows = tradeEntryRef.value?.rows ?? []
    if (rows.length === 0) {
      message.error('At least one Trade is required to create a Position.')
      return
    }
    if (!(await tradeEntryRef.value?.validate())) return

    // 1. derive opened_at from the earliest row's executed_at
    const opened_at = rows
      .map(r => r.executed_at)
      .sort()[0]

    // 2. create position
    const position = await positionsApi.create({
      ...positionPayload.value,
      opened_at,
    })

    // 3. create trade(s) — share order_group_id automatically when ≥2 rows
    const tradesPayload = rows.map(r => ({ ...r, position_id: position.id }))
    try {
      await tradesApi.createMany(tradesPayload)
    } catch (e) {
      message.error(
        `Position created (id=${position.id}) but Trade(s) failed: ` +
        `${e instanceof ApiError ? e.message : 'unknown error'}. ` +
        `Retry trade entry, or delete the orphan position from /positions.`,
      )
      return  // leave the user on the form with the position created
    }

    message.success('Position and Trade(s) created')
    emit('saved', position)
  }
  ```

**Form fields per row** (both modes):

| Field            | Component                            | Required | Validation |
|---|---|---|---|
| `instrument_id`  | `<InstrumentPicker allowCreate>`     | ✅ | inherits picker contracts; kind unconstrained (multi-leg can mix stocks + options) |
| `action`         | `<n-select>` over `TradeAction`      | ✅ | restricted by instrument kind via `isValidActionForKind` — UI disables incompatible options once instrument is set |
| `quantity`       | `<n-input-number>`                   | ✅ | `> 0`; **integer required for option** (`step=1` + `precision=0` when picked instrument's `kind === 'option'`); stock/forex allow decimals |
| `price`          | `<n-input-number>`                   | ✅ | `>= 0` (per data-model §4.5.2 worthless-expire/assignment uses 0) |
| `commission`     | `<n-input-number>`                   | optional | `>= 0`, default 0 |
| `fees`           | `<n-input-number>`                   | optional | `>= 0`, default 0 |
| `executed_at`    | `<n-date-picker type="datetime">`    | ✅ | default now |
| `notes`          | `<n-input type="textarea" size="small">` | optional | max 4000 chars |
| (preview)        | computed cash_flow                   | — | `previewCashFlow(...)`, shown read-only right of the row, currency-prefixed; **server is source of truth** disclaimer in form footer |

**Row-level validation** runs per-row on submit; per-form validation
also enforces:
- ≥1 row.
- All rows share consistent `executed_at`? **No** — rows can have
  different `executed_at` (e.g., a delayed leg fill) per
  [P9 §6④](./backend-expansion-plan.md#6-design-decisions); only the
  earliest is used for `opened_at` in inline mode.
- All rows use the same `account_id` — guaranteed by the modal taking
  `:accountId` as a prop, not per-row.

**Failure recovery (atomic flow, inline mode).**
The two-step "create Position then create Trades" pattern can fail
partway:

1. POST `/api/positions` succeeds, POST `/api/trades` fails →
   **orphan Position exists, modal stays open**. Toast surfaces the
   error with the orphan position id and a hint to retry trade entry or
   delete from `/positions`. The user does NOT have to re-fill the
   Position-level fields (already created). They CAN retry the Trade
   POST from the same modal (the rows are still in memory).
2. POST `/api/positions` fails → no orphan; modal stays open with all
   data intact.
3. Validation fails before POST → no network calls; modal stays open.

A future V1.x could add a server-side atomic endpoint that creates both
in one transaction; for V1, the orphan path is acceptable because:
- The race window is single-user single-tab.
- The user has a clean recovery action (delete orphan).
- The backend already has `DELETE /positions/{id}` for empty positions.

### 5.5 `PositionTradesTab.vue`

Replaces F3's `PositionTradesPlaceholder.vue`. Same import target in
`PositionDetailView.vue` — flip the import line.

Layout:

- **Header strip:**
  - Left: `<n-switch v-model:value="includeArchived">` *"Show archived"* —
    bound to `useTrades(positionId).includeArchived`.
  - Right: `+ New trade` button → opens `TradeEntryModal` standalone.
- **Group list.** Group trades by `order_group_id` (NULL groups treated
  as single-row groups). Use `<n-list>` with one item per group.
  - Group header: pattern badge (computed via
    `detectPattern(group, instrumentMap)`); `executed_at` of the group's
    earliest row (relative + tooltip); group count badge if >1 row.
  - Group rows: a small inner table with columns `action` badge,
    `instrument` symbol, `quantity`, `price`, `cash_flow`,
    `commission+fees`, actions.
  - Per-row actions:
    - **Edit notes** — `<n-popconfirm>`-style inline editor on `notes`
      field only (P9 only allows `notes` PATCH).
    - **Archive** — popconfirm → `useTrades.archive(id)`. Archived rows
      visually dimmed when `includeArchived === true`; hidden by default.
- **Empty state** — `<n-empty>` *"No trades yet on this position."*
  CTA `+ New trade` opens the modal.

**Pattern badge rendering.** A small `<TradePatternBadge :badge>`
component renders the four patterns with distinct colors:

| Badge        | Color   | Tooltip text |
|---|---|---|
| `ic-open`    | info    | "Iron Condor opened (4 option legs in one order)" |
| `assignment` | warning | "Assignment: short option closed, stock leg created" |
| `exercise`   | warning | "Exercise: long option closed, stock leg created" |
| `expiration` | default | "Option expired worthless (price=0)" |
| `null`       | (none)  | no badge — generic group |

The badges are **inferred from row shape, not declared by the user**.
This means an iron condor whose user only entered 3 legs won't show
`ic-open` — that's correct behavior (it's not actually an IC). Pattern
detection is purely display sugar.

**Deletion path.** Keep `PositionTradesPlaceholder.vue` in the F3 commit
history but delete the file at the end of F4. F4's manual recipe
verifies the swap.

### 5.6 `PositionDetailView.vue` changes

Two edits:

1. Change the import + component reference:
   ```ts
   // import PositionTradesPlaceholder from '../components/PositionTradesPlaceholder.vue'
   import PositionTradesTab from '../components/PositionTradesTab.vue'
   ```
   And in `<template>`:
   ```vue
   <n-tab-pane name="trades" tab="Trades">
     <PositionTradesTab :positionId="position.id" />
   </n-tab-pane>
   ```
2. Add a small `+ Add trade` button to the Overview card (right side, in
   line with Edit, secondary type). Opens `TradeEntryModal` standalone.
   After `@saved`: refresh `usePosition` + (if on Trades tab) the
   tab's `useTrades` via a small event bus or by simply calling
   `position.refresh()` (the page-level `usePosition` already triggers
   `net_cash_flow` re-read; the tab's `useTrades` refreshes on mount).
   Cleanest: emit a `@trade-saved` event from `PositionDetailView` and
   have both `usePosition` and the tab subscribe.

### 5.7 `DashboardView.vue` updates

Flip the Trades placeholder card from disabled to active. The card's
count is **optional** for F4 — wiring a `useTradesGlobalCount` requires
either a backend `/api/trades?limit=…` global call or a new endpoint.
For V1, label the card just `Trades` (no count) and link it to
`/positions` (since trades are viewed inside positions). The Dashboard
proper grows real numbers in F5.

| Card | Content | Link |
|---|---|---|
| Your accounts | count from `useAccounts` | `/accounts` |
| Instruments | count from `useInstruments` | `/instruments` |
| Positions | count from `usePositions` (status=`open`) | `/positions` |
| Strategy caps | count from `useStrategyConfigs` | `/settings/strategies` |
| **Trades** | label only (no count) | `/positions` |
| Dashboards (Phase F5) | disabled | none |

## 6. Codegen workflow

No new backend endpoints in F4 — codegen unchanged from F3. If any P9
patch lands during F4 work, re-run `npm run codegen` and commit.

## 7. Testing approach

- **No automated frontend tests in F4.** Manual recipe (§8) is the gate.
  The two pure helpers (`previewCashFlow`, `detectPattern`) are clean
  Vitest candidates but defer to V1.x unless either grows non-trivial
  branches (e.g., a complex pattern lookup).
- **Backend regression** — must stay green after every chunk of F4 work.
- **F3 regression** — `PositionFormModal`'s atomic flow replaces the F3
  dev-crutch path; ensure `?legacy=true` is removed (manual recipe
  step 23 verifies).
- **The `previewCashFlow` ↔ backend formula consistency invariant**
  ([V1 Decision 5](./v1-release-plan.md#decision-5--derived-values-frontend-per-position-backend-for-lists--aggregates))
  is a manual cross-check: after submitting any trade, compare the
  preview cash_flow shown in the form against the cash_flow returned
  by the server. Mismatch is a regression.

## 8. Manual verification recipe

Prerequisite: backend on `127.0.0.1:8000` with P9 deployed; frontend on
`localhost:5173`; fresh DB; Alice logged in; Cash USD account + AAPL
stock instrument already created (see F3 §8 steps 1–3).

> Where F3 §8 used the dev-crutch `?legacy=true` path to create
> Positions, F4 uses the real atomic path through `TradeEntryModal`
> inline. The `?legacy=true` query string is removed in F4.

1. Navigate to `/positions` → empty.
2. Click `+ New position` → modal opens. Account = Cash USD,
   Instrument = AAPL, Strategy = Spot Stock, opened_at = (will be
   derived from first-Trade `executed_at`; the modal still shows the
   field but it's auto-synced — try editing and the auto-sync warns
   "opened_at derives from first-Trade executed_at").
3. **First Trade subsection** — F4 inline form renders with one default
   leg row. Fill row: action=buy, quantity=10, price=170.50,
   executed_at=now → cash_flow preview shows `-USD 1705.00` (red, with
   "preview" tag).
4. Submit → toast "Position and Trade(s) created" → navigate to
   `/positions/{id}`. Overview shows `net_cash_flow: -USD 1705.00`;
   Trades tab now uses `PositionTradesTab`; one un-grouped trade row
   visible, no pattern badge (single non-option).
5. Click Trades tab `+ New trade` → standalone modal. Add another buy
   row: action=buy, quantity=5, price=172.00, executed_at=now → preview
   `-USD 860.00` → submit → row count 2; net_cash_flow updates to
   `-USD 2565.00`.
6. **Multi-leg test (Iron Condor open).** Create another Position with
   strategy=Iron Condor on AAPL. In the first-Trade subsection, add 4
   leg rows:
   - sto AAPL P 170 expiry+30d qty=1 price=2.50
   - bto AAPL P 165 expiry+30d qty=1 price=1.50
   - sto AAPL C 200 expiry+30d qty=1 price=3.00
   - bto AAPL C 205 expiry+30d qty=1 price=2.00
   For each option leg: the picker needs the option contract. Use
   `allowCreate` to inline-create the underlying options if not present.
   Submit → Position + 4 Trades created → navigate to detail; Trades
   tab shows one group of 4 rows with **IC-open** badge (info color).
7. Verify `cash_flow` preview parity: each row's preview matches the
   server-returned cash_flow on the saved row (`+250.00`, `-150.00`,
   `+300.00`, `-200.00` for the 4 legs respectively, assuming
   multiplier=100; total = `+200.00` net credit).
8. **Expiration pattern.** From step 6's IC, create a new Trade group
   with one option `btc` leg @ price=0, quantity=1 (close the short put
   at expiry worthless). The new group should display **Expiration**
   badge.
9. **Assignment pattern.** Create an order group with:
   - stc AAPL P 170 expiry @ price=0, quantity=1
   - buy AAPL @ price=170, quantity=100
   Both in one submission → one group of 2 rows → **Assignment** badge
   (warning color).
10. **Exercise pattern.** Mirror: btc AAPL C 200 @ price=0, quantity=1
    + buy AAPL @ price=200, quantity=100 → **Exercise** badge.
11. **Action↔kind validation.** `+ New trade` on a Spot Stock position.
    Pick stock AAPL instrument. The `action` dropdown should disable
    `bto / sto / btc / stc` (option-only). Pick option AAPL P 170 → the
    `buy / sell` options should disable.
12. **Integer-only quantity for options.** With an option instrument
    selected, `quantity` input shows `precision=0`, scroll-to-increment
    by 1. Typing `2.5` → on blur, value rounds to `2` or rejects per
    `<n-input-number>` precision config; submit with `2.5` is rejected
    422 by backend regardless (verifies the front+back agree).
13. **Cash flow preview = server cash flow.** After any submit, open
    the saved row, compare the preview shown in the form's row to the
    `cash_flow` column in the table. They MUST match to the cent. Any
    mismatch is a regression (V1 consistency invariant).
14. **Archive a trade.** Trades tab → row → Archive → popconfirm →
    confirm → row disappears from default view. Toggle "Show archived"
    → row reappears dimmed. `position.net_cash_flow` should drop by the
    archived row's cash_flow (per P12 archived-trade exclusion). The
    Overview's derived card updates after refresh.
15. **Edit notes only.** Click "Edit notes" on a trade row → inline
    editor opens with current notes → change to "broker assigned manually"
    → save → notes update. Try to PATCH other fields via curl: backend
    returns 422 (P9 immutability invariant).
16. **Soft-deleted trade can't be modified.** Archive a trade. Try
    `Edit notes` on it (while Show archived is on): row should disable
    that action — archived trades are read-only (frontend choice,
    backend allows). Unarchive via the new "Unarchive" action or by
    contacting support — V1: simply re-create.
17. **Position close after trades.** Detail page → Close → confirm.
    `pnl_realized` frozen = `net_cash_flow` at the moment of close.
    Subsequent archive of a trade should NOT change the frozen
    `pnl_realized` (P9 audit invariant); verify by archiving a closed-
    position's trade and observing `pnl_realized` unchanged in detail.
18. **DashboardView regression.** Navigate to `/` → Trades card visible
    (no count), links to `/positions`. Positions card shows updated
    open-position count.
19. **Atomic-flow failure recovery.** Simulate by attempting to submit
    a Position with first-Trade row whose `instrument_id` is invalid
    (manually edit DOM state to set instrument_id to a random UUID).
    Position POST succeeds → Trade POST fails 422 → toast surfaces the
    orphan position id with a recovery hint → navigate to
    `/positions`, see the orphan → delete it (no trades attached, so
    409 doesn't fire).
20. **Multi-row atomic.** Submit a Custom multi-leg Position with 4 legs
    but the third leg has invalid data. Submission should NOT post 3
    legs and skip the 4th — backend rejects the whole array per P9
    atomic semantics. Frontend toast surfaces the validation error;
    the position is also NOT created (we POST Position first; the
    server-side validation happens on Trade POST). Verify: list shows
    no new Position (the orphan path only runs when Position POST
    succeeds but Trade POST fails; here Trade POST fails on the array,
    so the orphan exists — and we still leave it for the user to
    delete). Mark this as the documented behavior; future V1.x can
    consider rollback.
21. **F3 dev-crutch removed.** Navigate to `/positions/new?legacy=true`
    (the F3 query string) → behaves identically to `/positions/new`
    (i.e., NO crutch path). The form requires First Trade.
22. **F3 regression — Plan / Meta still work.** Detail page Plan tab →
    append a revision (as in F3 §8 step 10). Works as before. Meta
    tab → for a wheel position, create wheel meta. Works as before.
23. Backend log throughout: no 500s, no IntegrityErrors. After all
    steps, `pytest -q` still green.

## 9. After F4

Once F4 ships, the next iteration is
[F5 — Dashboard](./frontend-expansion-plan.md#f5--dashboards--charts),
which consumes backend P12.2 (`GET /api/dashboard/summary`). F5 will:

- Build `src/api/dashboard.ts` wrapping the P12.2 endpoint.
- Rewrite `/dashboard` with per-currency PnL cards, open + closed
  position tables, and one monthly-PnL chart via `vue-echarts`
  ([V1 Decision 3](./v1-release-plan.md#decision-3--charts-vue-echarts)).
- Reuse `src/utils/positionDerived.ts` from F3 §9 for the open-positions
  table's per-row derived display (consistency invariant per V1
  Decision 5).

F6 (Docker) follows F5.

V1.x candidates seeded during F4:

- **Vitest** for `previewCashFlow` and `detectPattern` if either grows
  branches.
- **Named-flow helpers** (Expire / Assignment / Exercise / IC-open
  templates) — additive over Custom multi-leg, no breaking change.
- **Server-side atomic Position+Trade endpoint** — would eliminate the
  orphan-position recovery path; clean V1.x cleanup.
- **Trade edit-in-place** — beyond `notes` — requires changing P9
  immutability invariant; needs a `Trade.archived_at` audit story.

---

## Changelog

- **v0.1 (2026-05-28)** — Initial F4 plan. V1 release plan §4 Decision 2's
  TBD ("named-flow shortlist for V1 — decided inside F4 detail plan") is
  settled here: **zero named flows in V1; Custom multi-leg is the only
  entry mode.** Rationale: smallest surface to ship, pattern badges still
  fire on display, helpers are easy additive V1.x work.
  Plan covers: `src/api/trades.ts` (replacing F3's inline type), `useTrades`
  composable, `TradeEntryModal` with two modes (standalone for Position
  detail entry, inline for `PositionFormModal`'s atomic Position+Trade
  flow per the Trade-led model), `PositionTradesTab` replacing F3's
  placeholder with pattern-badge grouping + soft-delete UX, two pure
  helpers (`previewCashFlow`, `detectPattern`). The atomic Position+Trade
  failure-recovery path (orphan Position + retry hint) is documented but
  flagged as a V1.x candidate for a server-side atomic endpoint. F3's
  `?legacy=true` dev-crutch is removed.
