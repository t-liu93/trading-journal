# Frontend Phase F5 — Dashboard

**Language:** English | [中文](./frontend-implementation-plan-f5.zh.md)

> Status: **DRAFT v0.1** (2026-05-28). Companion to
> [frontend-expansion-plan.md](./frontend-expansion-plan.md) (macro
> roadmap), [v1-release-plan.md](./v1-release-plan.md) (V1 north star),
> [frontend-implementation-plan-f1.md](./frontend-implementation-plan-f1.md)
> (F1 pattern reference), and the backend plan
> [backend-expansion-plan-p12.md](./backend-expansion-plan-p12.md)
> (P12.2 `GET /api/dashboard/summary`). Iterate here before writing code.

## 1. Purpose

F5 sits on top of backend **P12.2** (`GET /api/dashboard/summary`,
shipped) and the F3/F4 frontend deliverables. It delivers the journal's
read-only summary surface — the page the user opens to ask *"how am I
doing?"*:

- A `vue-echarts`-powered monthly realized-PnL bar chart per
  [V1 release plan Decision 3](./v1-release-plan.md#decision-3--charts-vue-echarts).
- Per-currency PnL summary cards (no FX conversion — per
  [V1 Decision 4](./v1-release-plan.md#decision-4--position-no-archived_at-in-v1)
  / data-model §6 currency-placement).
- Open and closed Position tables sourced directly from
  `usePositions()` (F3 composable, reused) — the dashboard does not
  need a separate `useDashboardPositions` because the V1 cut is small
  enough to render both tables from one paginated list.
- A small `src/api/dashboard.ts` + `useDashboard()` wrapping the P12.2
  endpoint.

F5 is the **last frontend phase** before F6 (Docker). After F5 the V1
feature set is complete — F6 just packages it.

F5 builds on F1/F2/F3/F4 patterns; the only fundamentally new piece is
the **chart library**, vendored once and used in a single component.

### Chart shape — settled

[V1 Decision 3](./v1-release-plan.md#decision-3--charts-vue-echarts)
fixed the library as `vue-echarts`. The bar-chart shape is the F5-level
detail:

- **Settled 2026-05-28: stacked bars per currency, one bar per month.**
  Rationale:
  - A single rendering covers all currencies the user trades — no
    switcher widget, no extra clicks.
  - The stack semantically conveys "month total split by currency",
    which matches how a trader thinks ("April: +$1,200 in USD, -€80 in
    EUR, net +$X by current FX which we deliberately don't compute").
  - When a user trades only one currency (the common V1 case), the
    stack degrades gracefully to single-colored bars.
  - Per-currency switcher (alternative) saves screen space at the cost
    of an extra interaction; the V1 page has plenty of vertical room
    for one full-width chart, so the trade-off favors no-click.

  Considered alternatives:
  - **Currency switcher** (`<n-segmented>` toggling which currency the
    chart shows). Cleaner per-currency view but adds an interaction;
    deferred to V1.x if the stack proves visually noisy.
  - **Grouped bars** (currencies side-by-side per month). Densest, but
    hardest to read on small screens — and the page is desktop-first.

  All three shapes are easy to switch between in ECharts; the V1 choice
  is the stacked variant.

## 2. Scope

### In scope (this plan)

- **`src/api/dashboard.ts`** — typed wrapper for the single P12.2
  endpoint `GET /api/dashboard/summary`.
- **`useDashboard()` composable** — single-fetch wrapper. State:
  `summary` (`DashboardSummary | null`), `loading`, `error`, `refresh()`.
- **`vue-echarts` + `echarts` dependencies** — added to
  `frontend/package.json`. Only the bar-chart components imported (not
  the whole `echarts` bundle) so the build size stays small.
- **`MonthlyPnlChart.vue`** — the chart component. Reads
  `closed.monthly_pnl` from the summary; pivots to ECharts bar series
  per currency.
- **`PerCurrencyCard.vue`** — small presentational card for one
  `CurrencyAmount` row. Used by both the open-side block and the
  closed-side block on the dashboard.
- **`OpenPositionsTable.vue`** — table of open positions, columns:
  symbol, strategy, opened_at, `net_cash_flow`, `days_open`,
  `roi_on_capital`, currency. Per-row derived (`days_open`,
  `roi_on_capital`) uses **the same** `src/utils/positionDerived.ts`
  helpers F3 introduced — V1 Decision 5 consistency invariant.
- **`ClosedPositionsTable.vue`** — table of closed positions, columns:
  symbol, strategy, closed_at, `pnl_realized`, `result`, currency.
- **`DashboardView.vue` rewrite** — replace the F1/F2/F3/F4 placeholder
  cards with the real dashboard surface:
  1. Summary header (per-currency open + closed PnL cards, win rate
     gauge, counts).
  2. Monthly PnL chart.
  3. Open positions table.
  4. Closed positions table.
- **Codegen** — `schema.d.ts` already includes `DashboardSummary` from
  P12 (verified). No new endpoints in F5; codegen unchanged.
- **Backend regression** — ≥406 backend tests passing; `ruff` + `mypy
  --strict` clean.

### Explicitly NOT in scope (deferred)

- **FX conversion / cross-currency totals** — V1.x; needs `FxRate`
  table + provider per
  [data-model §6](./data-model.md#currency-placement).
- **Date-range pickers** (per V1 release plan §6.4) — V1 shows
  all-time; range picker is V1.x.
- **Per-strategy drill-down dashboards** — V1.x.
- **Unrealized PnL** — needs market quotes; V1.x.
- **Multiple chart types** (line trends, scatter, etc.) — V1.x.
- **Dashboard caching** — V1 just re-fetches on mount. Backend
  currently has no caching either (per
  [P12 §2](./backend-expansion-plan-p12.md#2-scope)).
- **Real-time refresh** (websocket / polling) — V1 is on-demand only.
- **Drilling from a chart bar to filtered position list** — V1.x.
- **Promoting `useDashboard` to a Pinia store** — composable suffices.
- **`@unovis/vue` evaluation** — V1 Decision 3 explicitly picks
  `vue-echarts`; the side-by-side write-up is recorded in §9 for
  V1.x reference but not blocking F5.
- **Frontend tests (Vitest / Playwright)** — none in F5; same line as
  prior phases.
- **Empty-state polish** — F5 renders generic `<n-empty>` for empty
  buckets; bespoke empty-state illustrations are out of scope.

## 3. Tech additions

**Two new runtime dependencies** added to `frontend/package.json`:

```json
{
  "dependencies": {
    "echarts": "^5.5.0",
    "vue-echarts": "^7.0.0"
  }
}
```

Import strategy — **only the bar-chart pieces**, not the whole
`echarts` global. This keeps the V1 build size lean (~150 KB added
vs ~900 KB for the full bundle):

```ts
// MonthlyPnlChart.vue (excerpt)
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([BarChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer])
```

`vue-tsc` typechecks `vue-echarts`'s default Vue 3 types; no shim
needed.

## 4. Directory structure changes

```
frontend/src/
├── api/
│   ├── dashboard.ts                    ← NEW
│   ├── trades.ts                       ← unchanged (F4)
│   ├── positions.ts                    ← unchanged (F3)
│   ├── tradePlans.ts                   ← unchanged (F3)
│   ├── strategyMeta.ts                 ← unchanged (F3)
│   ├── instruments.ts                  ← unchanged
│   ├── strategyConfigs.ts              ← unchanged
│   ├── accounts.ts                     ← unchanged
│   ├── http.ts                         ← unchanged
│   └── types.ts                        ← unchanged
├── composables/
│   ├── useDashboard.ts                 ← NEW
│   └── (others unchanged)
├── components/
│   ├── MonthlyPnlChart.vue             ← NEW
│   ├── PerCurrencyCard.vue             ← NEW
│   ├── OpenPositionsTable.vue          ← NEW
│   ├── ClosedPositionsTable.vue        ← NEW
│   ├── DashboardWinRateGauge.vue       ← NEW (small KPI tile)
│   └── (others unchanged)
├── utils/
│   ├── positionDerived.ts              ← REUSED from F3 §9
│   ├── tradeCashFlow.ts                ← unchanged (F4)
│   └── tradePatternBadge.ts            ← unchanged (F4)
├── router/
│   └── index.ts                        ← unchanged
└── views/
    ├── DashboardView.vue               ← CHANGED: full rewrite
    └── (other views unchanged)
```

## 5. Build deliverables

Suggested ordering: **API client → composable → presentational
components → chart component → DashboardView rewrite**. The chart lands
late because it depends on `vue-echarts` install + the composable being
shaped.

### 5.1 API client

**`src/api/dashboard.ts`** — typed wrapper for the single P12.2
endpoint.

```ts
import type { components } from './schema'
import { http } from './http'

export type DashboardSummary    = components['schemas']['DashboardSummary']
export type ClosedSummary       = components['schemas']['ClosedSummary']
export type OpenSummary         = components['schemas']['OpenSummary']
export type CurrencyAmount      = components['schemas']['CurrencyAmount']
export type MonthCurrencyAmount = components['schemas']['MonthCurrencyAmount']

export const dashboardApi = {
  summary: () => http.get('/api/dashboard/summary') as Promise<DashboardSummary>,
}
```

### 5.2 Composable

**`useDashboard()`** — minimal single-fetch wrapper.

```ts
import { ref } from 'vue'
import { type DashboardSummary, dashboardApi } from '../api/dashboard'
import { ApiError } from '../api/types'

export function useDashboard() {
  const summary = ref<DashboardSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let refreshSeq = 0

  async function refresh(): Promise<void> {
    const seq = ++refreshSeq
    loading.value = true
    error.value = null
    try {
      const result = await dashboardApi.summary()
      if (seq === refreshSeq) summary.value = result
    } catch (e) {
      if (seq === refreshSeq)
        error.value = e instanceof ApiError ? e.message : 'Failed to load dashboard'
    } finally {
      if (seq === refreshSeq) loading.value = false
    }
  }

  return { summary, loading, error, refresh }
}
```

### 5.3 Presentational components

**`PerCurrencyCard.vue`** — small KPI tile for one `CurrencyAmount`.

```vue
<script setup lang="ts">
defineProps<{
  label: string         // "Realized P/L" | "Net Cash Flow"
  currency: string      // ISO 4217, uppercase
  amount: string        // Decimal, comes straight from CurrencyAmount.amount
}>()
</script>

<template>
  <n-card size="small">
    <n-statistic :label="label">
      <span :class="Number(amount) > 0 ? 'text-success' : Number(amount) < 0 ? 'text-error' : ''">
        {{ currency }} {{ formatAmount(amount) }}
      </span>
    </n-statistic>
  </n-card>
</template>
```

`formatAmount` uses `Intl.NumberFormat(undefined, { minimumFractionDigits:
2, maximumFractionDigits: 4 }).format(Number(amount))`. Co-locate in
`src/utils/positionDerived.ts` (or a new `formatMoney.ts`) — F3's
`computePnlTotal` will likely have a sibling formatter already.

**`DashboardWinRateGauge.vue`** — small gauge / dial KPI showing
`closed.win_rate`.

```vue
<script setup lang="ts">
defineProps<{ winRate: string | null }>()

const pct = computed(() =>
  props.winRate == null ? null : Number(props.winRate) * 100,
)
</script>

<template>
  <n-card size="small">
    <n-statistic label="Win rate">
      <span v-if="pct == null">—</span>
      <span v-else :class="pct >= 50 ? 'text-success' : 'text-warning'">
        {{ pct.toFixed(1) }}%
      </span>
    </n-statistic>
  </n-card>
</template>
```

Empty-state semantics: when no closed positions exist, `winRate` is
`null` and the gauge renders `—` (matching the backend's null contract
per [P12 §1](./backend-expansion-plan-p12.md#1-purpose--context)).

**`OpenPositionsTable.vue`** — table of open positions. Re-uses F3's
`usePositions({ status: 'open' })` — instantiated locally inside the
component:

```vue
<script setup lang="ts">
import { usePositions } from '../composables/usePositions'
import { computeDaysOpen, computeRoi, formatMoney } from '../utils/positionDerived'

const { positions, refresh } = usePositions()
onMounted(() => { void refresh() })
</script>

<template>
  <n-card title="Open positions">
    <n-data-table
      :columns="[/* symbol, strategy, opened_at, net_cash_flow, days_open, roi_on_capital, currency, actions */]"
      :data="positions.filter(p => p.status === 'open')"
    />
  </n-card>
</template>
```

Columns:
- **Symbol** — joined from instrument map (a single
  `/api/instruments?limit=200` fetch on mount; cache).
- **Strategy** — prettified enum.
- **Opened at** — relative + tooltip.
- **Net Cash Flow** — `position.net_cash_flow` (P12.1), currency-prefixed.
- **Days open** — `computeDaysOpen(position)`.
- **ROI** — `computeRoi(position)` — uses `net_cash_flow` for V1 (per
  V1 Decision 5; `pnl_total = net_cash_flow` until unrealized lands in
  V1.x).
- **Currency** — `position.currency`.
- **Actions** — `Open` → `router.push('/positions/{id}')`.

**`ClosedPositionsTable.vue`** — mirror for closed.

Columns:
- **Symbol**, **Strategy** — same.
- **Closed at** — relative + tooltip.
- **Realized P/L** — `position.pnl_realized` (frozen on close by P8).
- **Result** — `computeResult(position)` rendered as `<n-tag>` (Win /
  Loss / Breakeven).
- **Currency** — same.
- **Actions** — `Open` link.

Both tables sort by their date column descending by default. Pagination
deferred to V1.x (limit=200 on the underlying list, ample for V1).

### 5.4 `MonthlyPnlChart.vue`

The dashboard's only chart. Renders `closed.monthly_pnl` as stacked
bars (one stack per currency).

**Data pivot.** `closed.monthly_pnl` arrives as `MonthCurrencyAmount[]`
sorted `(month ASC, currency ASC)` per
[P12.2 §4.2](./backend-expansion-plan-p12.md#42-dashboardsummary--response-shape).
We need a pivot into ECharts series shape:

```ts
function buildChartOption(rows: MonthCurrencyAmount[]) {
  // Collect unique months (x-axis categories) and currencies (series)
  const monthsSet = new Set<string>()
  const currenciesSet = new Set<string>()
  for (const r of rows) {
    monthsSet.add(r.month)
    currenciesSet.add(r.currency)
  }
  const months = [...monthsSet].sort()
  const currencies = [...currenciesSet].sort()

  // Index by (month, currency) → amount
  const byKey = new Map<string, number>()
  for (const r of rows) {
    byKey.set(`${r.month}|${r.currency}`, Number(r.amount))
  }

  // Build series
  const series = currencies.map(c => ({
    name: c,
    type: 'bar',
    stack: 'pnl',   // ← key: same stack name across series → bars stack
    emphasis: { focus: 'series' },
    data: months.map(m => byKey.get(`${m}|${c}`) ?? 0),
  }))

  return {
    title: { text: 'Monthly realized P/L' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: currencies },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value' },
    series,
  }
}
```

**Component shape.**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TitleComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { MonthCurrencyAmount } from '../api/dashboard'

use([BarChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ rows: MonthCurrencyAmount[] }>()
const option = computed(() => buildChartOption(props.rows))
</script>

<template>
  <n-card>
    <div v-if="rows.length === 0" class="empty">
      <n-empty description="No closed positions yet — chart will populate after the first close." />
    </div>
    <v-chart v-else :option="option" autoresize style="height: 360px" />
  </n-card>
</template>
```

Color choice: rely on the ECharts default palette in V1. If V1.x adds
brand colors, we override via `option.color` array. Negative amounts
render below the x-axis automatically (stacked bars handle signs by
splitting the stack into positive/negative sub-stacks via ECharts'
built-in behavior).

### 5.5 `DashboardView.vue` rewrite

Replace the placeholder-cards layout with the real dashboard.

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useDashboard } from '../composables/useDashboard'
import PerCurrencyCard from '../components/PerCurrencyCard.vue'
import DashboardWinRateGauge from '../components/DashboardWinRateGauge.vue'
import MonthlyPnlChart from '../components/MonthlyPnlChart.vue'
import OpenPositionsTable from '../components/OpenPositionsTable.vue'
import ClosedPositionsTable from '../components/ClosedPositionsTable.vue'

const { summary, loading, error, refresh } = useDashboard()
onMounted(() => { void refresh() })
</script>

<template>
  <AuthenticatedLayout>
    <n-page-header title="Dashboard" />

    <n-alert v-if="error" type="error" :title="error" closable @close="error = null" />
    <n-spin :show="loading">

      <!-- Summary strip -->
      <n-grid v-if="summary" :cols="6" :x-gap="12" :y-gap="12">
        <n-gi>
          <DashboardWinRateGauge :winRate="summary.closed.win_rate" />
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="Open positions" :value="summary.open.count" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="Closed positions" :value="summary.closed.count" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Per-currency cards -->
      <n-grid v-if="summary" :cols="4" :x-gap="12" :y-gap="12" style="margin-top: 16px">
        <n-gi v-for="row in summary.closed.per_currency_pnl" :key="`closed-${row.currency}`">
          <PerCurrencyCard label="Realized P/L (closed)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
        <n-gi v-for="row in summary.open.per_currency_net_cash_flow" :key="`open-${row.currency}`">
          <PerCurrencyCard label="Net Cash Flow (open)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
      </n-grid>

      <!-- Chart -->
      <div style="margin-top: 24px">
        <MonthlyPnlChart v-if="summary" :rows="summary.closed.monthly_pnl" />
      </div>

      <!-- Tables -->
      <n-grid :cols="1" :y-gap="16" style="margin-top: 24px">
        <n-gi><OpenPositionsTable /></n-gi>
        <n-gi><ClosedPositionsTable /></n-gi>
      </n-grid>

    </n-spin>
  </AuthenticatedLayout>
</template>
```

**Empty-state semantics:**

- `summary.closed.count === 0 && summary.open.count === 0` → only the
  win-rate gauge ("—") + count tiles ("0") render; per-currency grids
  are empty; chart shows its own empty-state via `MonthlyPnlChart`.
- `closed.count === 0 && open.count > 0` → only open cards render; chart
  shows empty-state.
- `closed.count > 0 && open.count === 0` → only closed cards render;
  chart renders.

**Layout responsiveness.** F5 is desktop-first (per
[frontend-expansion-plan §7](./frontend-expansion-plan.md#7-after-this-roadmap)).
The `<n-grid :cols="N">` values are fixed; on smaller screens Naive
UI's grid auto-wraps reasonably. A responsive pass is V1.x.

## 6. Codegen workflow

No new backend endpoints in F5 — codegen unchanged from F4.

After F5 ships and is verified, **lock in the codegen freshness gate**
in CI if it wasn't already shipped (recommended per
[frontend-expansion-plan §5](./frontend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked)).
F5 is the last F-phase before F6's Docker build; the gate prevents
schema drift between V1 and any V1.x backend changes.

## 7. Testing approach

- **No automated frontend tests in F5.** Manual recipe (§8) is the gate.
  The chart pivot helper (`buildChartOption`) is a clean pure function
  that *could* be Vitested in V1.x if its branching grows; in V1 it's
  ~30 lines of straight pivoting.
- **Backend regression** — must stay green after F5 work.
- **Visual regression** — Playwright screenshot tests are V1.x; for V1
  the manual recipe's qualitative checks suffice.
- **Cross-phase consistency invariant** ([V1 Decision 5](./v1-release-plan.md#decision-5--derived-values-frontend-per-position-backend-for-lists--aggregates))
  manually verified: the open-positions table's per-row `roi_on_capital`
  (frontend-computed via `computeRoi`) MUST match what Position detail
  Overview tab shows for the same position. Use the same helper file
  — single source of truth.

## 8. Manual verification recipe

Prerequisite: backend with P12.2 deployed; frontend on
`localhost:5173`; Alice logged in; a representative dataset (multi-currency,
mix of open + closed positions, ≥3 calendar months represented). Easiest
seed flow: re-use the F4 §8 recipe up to step 10 then close at least
one position to populate `closed.monthly_pnl`.

1. Log in as Alice → land on `/` → `DashboardView` renders.
2. **Summary strip** — Win rate gauge, Open positions count, Closed
   positions count all visible at the top. Values match what
   `/api/dashboard/summary` returns (verify by hitting the endpoint
   with curl).
3. **Per-currency cards** — for each currency the user trades, both an
   "Open" card (net cash flow) and a "Closed" card (realized P/L)
   render if data exists. Negative amounts in red, positive in green.
   When the user only has positions in one currency, only that
   currency's cards render.
4. **Monthly PnL chart:**
   - With ≥1 closed position: chart renders, x-axis = months, stacked
     bars per currency, legend lists currencies. Hover a bar → tooltip
     shows month + per-currency breakdown.
   - With zero closed positions: chart shows empty-state alert *"No
     closed positions yet — chart will populate after the first
     close."*
5. **Open positions table** — rows for each open position. Columns
   render correctly: Symbol, Strategy, Opened at, Net Cash Flow (green
   / red per sign, currency-prefixed), Days open (computed in
   frontend; should match Position detail Overview's `days_open`),
   ROI %, Currency, Open action. Click Open → navigate to
   `/positions/{id}`.
6. **Closed positions table** — rows for each closed position.
   Realized P/L matches the row's `pnl_realized`; Result tag shows
   Win/Loss/Breakeven correctly.
7. **Consistency invariant (V1 Decision 5).** Pick one open position;
   note its ROI on the dashboard. Click Open → on the detail page
   Overview tab, ROI in the derived card MUST equal the dashboard
   value to two decimal places. Same for `days_open`.
8. **Multi-currency stress.** Create a Position+Trade in EUR (account
   in EUR + instrument with `currency=EUR`). Refresh dashboard → new
   EUR cards appear; chart's legend gains EUR if any closed-month EUR
   data exists. The dashboard does NOT show a combined "Total"
   line — V1 deliberately omits FX conversion. Verify no such row
   appears.
9. **Cross-user isolation.** Log out, register `bob@example.com`, log
   in → dashboard renders all zeros / empty. Bob does not see Alice's
   numbers.
10. **Loading state.** Throttle network in DevTools → reload `/` →
    `<n-spin>` shown while `/api/dashboard/summary` is in flight.
11. **Error state.** Stop the backend; reload `/` → `<n-alert
    type="error">` with "Failed to load dashboard" / network error.
    Close the alert → state persists until next `refresh()`. Restart
    backend, navigate away + back → alert clears, data loads.
12. **Auth gate.** Log out → navigate to `/` → router redirects to
    `/login` (F0 behavior). No partial dashboard renders for an
    unauthed user.
13. **Build size sanity.** `npm run build` → check `dist/` size; adding
    `vue-echarts` + `echarts` (tree-shaken bar-chart only) should add
    ~150–200 KB gzipped. If it blows up to >500 KB, the import strategy
    in §3 is wrong — re-verify the `use([...])` list excludes
    `BarChart`-adjacent components we don't need.
14. **vue-tsc clean.** `npm run build` produces no type errors. The
    `vue-echarts` types should resolve out of the box.
15. **Mount semantics.** Navigate from `/dashboard` to `/positions` and
    back. `useDashboard()` should `refresh()` on each mount — the data
    is current with backend state without manual page reload.
16. **Smoke after every F1–F4 flow.** Run a full register → account →
    instrument → position → trade → close-position → refresh-dashboard
    walkthrough; expected: every dashboard number reflects the most
    recent action.
17. Backend log throughout: only expected requests, no 500s, no
    IntegrityErrors. `pytest -q` still green after all manual steps.

## 9. After F5

Once F5 ships, the **only V1 work remaining is F6** (Docker
single-container). After F6, V1 is shippable.

V1.x candidates seeded during F5:

- **`@unovis/vue` re-evaluation** — V1 Decision 3 picked
  `vue-echarts`; if V1.x grows multiple chart types and one library
  becomes a clearer fit, swap. The single chart we ship makes the
  swap-cost very low.
- **Date-range picker** on the summary endpoint
  (`?from=YYYY-MM-DD&to=YYYY-MM-DD`) — needs a small backend
  extension; out of V1.
- **Per-strategy drill-down** (`?strategy_type=wheel`) — same shape.
- **Multi-chart dashboard** — line trends, scatter, calendar heatmap.
- **FX conversion view** — requires `FxRate` table + provider; lights
  up a "Convert to base currency" toggle on the per-currency cards.
- **Unrealized PnL line** — requires quote provider; would add a
  "Pnl total (incl. unrealized)" card next to each currency's open
  card.
- **Visual regression tests** — Playwright screenshot tests of the
  dashboard once layout stabilizes.
- **Currency switcher chart variant** — alternative to stacked bars,
  trivially added in ECharts via `<n-segmented>` over the same data.

After F5 the V1 cross-cutting list converges on:

- **CI codegen gate** — lock in here if not already.
- **Postgres parity verification** — run the suite against Postgres
  before F6 deploys (per
  [V1 release plan §8.2](./v1-release-plan.md#82-postgres-parity-verification)).
- **Manual acceptance walkthrough** — written into V1 release plan
  §8.3 when F6 is the last unchecked phase (per V1 §8.3 deferral note).

---

## Changelog

- **v0.1 (2026-05-28)** — Initial F5 plan. Chart shape settled
  ([V1 Decision 3](./v1-release-plan.md#decision-3--charts-vue-echarts)
  gave the library; F5 picks the bar variant): **stacked bars per
  currency, one bar per month**, single full-width chart. Alternatives
  (currency switcher / grouped bars) noted for V1.x. Plan covers:
  `src/api/dashboard.ts`, `useDashboard()` composable, 5 new
  presentational components (`MonthlyPnlChart`, `PerCurrencyCard`,
  `DashboardWinRateGauge`, `OpenPositionsTable`, `ClosedPositionsTable`),
  `DashboardView` full rewrite, and the `vue-echarts` + `echarts`
  dependency add with tree-shaken imports. Reuses F3's
  `src/utils/positionDerived.ts` for the open-positions table's
  per-row derived display (V1 Decision 5 consistency invariant). No
  internal sub-phases. After F5 ships, only F6 (Docker) remains in V1.
