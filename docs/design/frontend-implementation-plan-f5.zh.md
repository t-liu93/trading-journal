# 前端 Phase F5 — Dashboard

**Language:** [English](./frontend-implementation-plan-f5.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-28）。配套
> [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md)（macro
> 路线图）、[v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星）、
> [frontend-implementation-plan-f1.zh.md](./frontend-implementation-plan-f1.zh.md)
> （F1 模式参考），以及后端
> [backend-expansion-plan-p12.zh.md](./backend-expansion-plan-p12.zh.md)
> （P12.2 `GET /api/dashboard/summary`）。先在这里迭代，再动手写代码。

## 1. 目的

F5 建立在后端 **P12.2**（`GET /api/dashboard/summary`，已交付）和 F3/F4
前端交付物之上。它出货 journal 的只读总览面 —— 用户打开来问*"我做得
怎么样？"*的那一页：

- `vue-echarts` 驱动的按月已实现 PnL 柱状图，按
  [V1 release plan 决策 3](./v1-release-plan.zh.md#决策-3--图表vue-echarts)。
- Per-currency PnL 摘要卡（**无** FX 换算 —— 按
  [V1 决策 4](./v1-release-plan.zh.md#决策-4--positionv1-不加-archived_at)
  / data-model §6 currency-placement）。
- Open 与 Closed 仓位表，直接复用 `usePositions()`（F3 composable）——
  Dashboard 不必单独搞 `useDashboardPositions`，V1 切片小到一份 list
  分页就能撑两个表。
- 小巧的 `src/api/dashboard.ts` + `useDashboard()` 包装 P12.2 端点。

F5 是 F6（Docker）之前的**最后前端阶段**。F5 落地后 V1 功能集完整 ——
F6 只负责打包。

F5 沿用 F1/F2/F3/F4 模式；唯一全新部分是**图表库**，引入一次、单组件
使用。

### 图表形态 —— 已定

[V1 决策 3](./v1-release-plan.zh.md#决策-3--图表vue-echarts) 把库定为
`vue-echarts`。柱状图形态是 F5 级别的细节：

- **2026-05-28 已定：每月一根柱、按 currency 堆叠的堆叠柱。** 理由：
  - 一次渲染覆盖用户交易的所有 currency —— 无切换器，无额外点击。
  - 堆叠语义表达"按 currency 拆分的月合计"，符合交易者心智（"4 月：USD
    +$1,200、EUR -€80、按当前 FX 净 +$X，但 V1 故意不计算"）。
  - 用户只交易单 currency（V1 常见情况）时，堆叠优雅退化为单色柱。
  - Per-currency 切换器（备选）省屏幕但加一次交互；V1 页面有足够纵向
    空间放一张全宽图，所以取舍偏向"不点击"。

  已考虑的备选：
  - **Currency 切换器**（`<n-segmented>` 切图表展示的 currency）。
    Per-currency 视图更干净但加一次交互；如果堆叠视觉嘈杂，V1.x 改它。
  - **Grouped bars**（per-month 多 currency 并排）。密度最高，但小屏上
    最难读 —— 页面是 desktop-first。

  三种 ECharts 互切都简单；V1 取堆叠版。

## 2. 范围

### 在本计划范围内

- **`src/api/dashboard.ts`** —— P12.2 单端点 `GET /api/dashboard/summary`
  的类型化包装。
- **`useDashboard()` composable** —— 单次抓取包装。状态：`summary`
  （`DashboardSummary | null`）、`loading`、`error`、`refresh()`。
- **`vue-echarts` + `echarts` 依赖** —— 加进 `frontend/package.json`。
  仅 import 柱状图相关组件（不整 `echarts` bundle），保证 V1 构建体积
  小（增量 ~150 KB vs 全 bundle ~900 KB）。
- **`MonthlyPnlChart.vue`** —— 图表组件。读 summary 的
  `closed.monthly_pnl`，pivot 为 ECharts 按 currency 的 bar series。
- **`PerCurrencyCard.vue`** —— 单 `CurrencyAmount` 行的展示卡。dashboard
  的 open 与 closed 两侧都复用。
- **`OpenPositionsTable.vue`** —— 开仓表，列：symbol、strategy、
  opened_at、`net_cash_flow`、`days_open`、`roi_on_capital`、currency。
  逐行派生（`days_open`、`roi_on_capital`）用 **同一份** F3 引入的
  `src/utils/positionDerived.ts` helper —— V1 决策 5 一致性约束。
- **`ClosedPositionsTable.vue`** —— 平仓表，列：symbol、strategy、
  closed_at、`pnl_realized`、`result`、currency。
- **`DashboardView.vue` 重写** —— 把 F1/F2/F3/F4 占位卡替换为真正的
  dashboard：
  1. 总览条（per-currency open + closed PnL 卡、胜率仪表、计数）。
  2. 按月 PnL 图。
  3. 开仓表。
  4. 平仓表。
- **Codegen** —— `schema.d.ts` 已含 P12 的 `DashboardSummary`（已验证）。
  F5 不引新端点；codegen 不变。
- **后端回归** —— ≥406 条后端测试全绿；`ruff` + `mypy --strict` clean。

### 显式不在范围内（延后）

- **FX 换算 / 跨 currency 合计** —— V1.x；需要
  [data-model.zh.md §6](./data-model.zh.md#currency-placement) 的
  `FxRate` 表 + provider。
- **日期范围 picker**（按 V1 release plan §6.4）—— V1 展示 all-time；
  日期 picker 是 V1.x。
- **Per-strategy drill-down dashboards** —— V1.x。
- **未实现 PnL** —— 需要行情；V1.x。
- **多类型图表**（折线、散点等）—— V1.x。
- **Dashboard 缓存** —— V1 每次 mount 重抓。后端按
  [P12 §2](./backend-expansion-plan-p12.zh.md#2-scope) 也不缓存。
- **实时刷新**（websocket / polling）—— V1 按需。
- **图表柱点到过滤后的仓位列表** —— V1.x。
- **把 `useDashboard` 升 Pinia store** —— composable 够用。
- **`@unovis/vue` 评估** —— V1 决策 3 明定 `vue-echarts`；并排笔记记
  §9 备 V1.x 用，不阻塞 F5。
- **前端测试（Vitest / Playwright）** —— F5 不写；与前面阶段同。
- **空状态精修** —— F5 用通用 `<n-empty>` 表达空 bucket；定制空状态
  插画出 V1 范围。

## 3. 技术新增

**两条新运行时依赖** 加入 `frontend/package.json`：

```json
{
  "dependencies": {
    "echarts": "^5.5.0",
    "vue-echarts": "^7.0.0"
  }
}
```

Import 策略 —— **只引柱状图相关 piece**，不引整 `echarts` 全局，保持
V1 构建体积精简（~150 KB 增量，全 bundle 是 ~900 KB）：

```ts
// MonthlyPnlChart.vue（节选）
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

`vue-tsc` 直接吃 `vue-echarts` 默认 Vue 3 类型；无需 shim。

## 4. 目录结构变更

```
frontend/src/
├── api/
│   ├── dashboard.ts                    ← NEW
│   ├── trades.ts                       ← 不变（F4）
│   ├── positions.ts                    ← 不变（F3）
│   ├── tradePlans.ts                   ← 不变（F3）
│   ├── strategyMeta.ts                 ← 不变（F3）
│   ├── instruments.ts                  ← 不变
│   ├── strategyConfigs.ts              ← 不变
│   ├── accounts.ts                     ← 不变
│   ├── http.ts                         ← 不变
│   └── types.ts                        ← 不变
├── composables/
│   ├── useDashboard.ts                 ← NEW
│   └── （其他不变）
├── components/
│   ├── MonthlyPnlChart.vue             ← NEW
│   ├── PerCurrencyCard.vue             ← NEW
│   ├── OpenPositionsTable.vue          ← NEW
│   ├── ClosedPositionsTable.vue        ← NEW
│   ├── DashboardWinRateGauge.vue       ← NEW（小 KPI 块）
│   └── （其他不变）
├── utils/
│   ├── positionDerived.ts              ← 复用 F3 §9
│   ├── tradeCashFlow.ts                ← 不变（F4）
│   └── tradePatternBadge.ts            ← 不变（F4）
├── router/
│   └── index.ts                        ← 不变
└── views/
    ├── DashboardView.vue               ← CHANGED：全量重写
    └── （其他视图不变）
```

## 5. 构建交付物

推荐顺序：**API 客户端 → composable → 展示组件 → 图表组件 →
DashboardView 重写**。图表放最后，因为它依赖 `vue-echarts` 装好 +
composable 形态稳定。

### 5.1 API 客户端

**`src/api/dashboard.ts`** —— P12.2 单端点的类型化包装。

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

**`useDashboard()`** —— 最小的单次抓取包装。

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

### 5.3 展示组件

**`PerCurrencyCard.vue`** —— 单 `CurrencyAmount` 的小 KPI 块。

```vue
<script setup lang="ts">
defineProps<{
  label: string         // "Realized P/L" | "Net Cash Flow"
  currency: string      // ISO 4217，大写
  amount: string        // Decimal，直接来自 CurrencyAmount.amount
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

`formatAmount` 走 `Intl.NumberFormat(undefined, { minimumFractionDigits:
2, maximumFractionDigits: 4 }).format(Number(amount))`。同住
`src/utils/positionDerived.ts`（或新 `formatMoney.ts`）—— F3 的
`computePnlTotal` 多半已有兄弟格式化器。

**`DashboardWinRateGauge.vue`** —— 显示 `closed.win_rate` 的小仪表 KPI。

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

空状态语义：无 closed 仓位时 `winRate` 为 `null`，仪表展示 `—`（与后端
按 [P12 §1](./backend-expansion-plan-p12.zh.md#1-目的与上下文) 的 null
契约一致）。

**`OpenPositionsTable.vue`** —— 开仓表。复用 F3 的
`usePositions({ status: 'open' })`，组件内局部实例化：

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

列：
- **Symbol** —— 从 instrument map 关联（mount 时一次
  `/api/instruments?limit=200`，缓存）。
- **Strategy** —— 枚举可读化。
- **Opened at** —— 相对 + tooltip。
- **Net Cash Flow** —— `position.net_cash_flow`（P12.1），按 currency 加
  前缀。
- **Days open** —— `computeDaysOpen(position)`。
- **ROI** —— `computeRoi(position)` —— V1 中用 `net_cash_flow`（按 V1
  决策 5；V1.x 加未实现前 `pnl_total = net_cash_flow`）。
- **Currency** —— `position.currency`。
- **Actions** —— `Open` → `router.push('/positions/{id}')`。

**`ClosedPositionsTable.vue`** —— 平仓镜像。

列：
- **Symbol**、**Strategy** —— 同。
- **Closed at** —— 相对 + tooltip。
- **Realized P/L** —— `position.pnl_realized`（P8 关仓时冻结）。
- **Result** —— `computeResult(position)` 渲染为 `<n-tag>`（Win / Loss /
  Breakeven）。
- **Currency** —— 同。
- **Actions** —— `Open` 链接。

两张表默认按日期列降序。分页延后到 V1.x（底层 list `limit=200`，V1 够）。

### 5.4 `MonthlyPnlChart.vue`

Dashboard 唯一的图。把 `closed.monthly_pnl` 渲染为堆叠柱（每 currency
一栈）。

**数据 pivot。** `closed.monthly_pnl` 按
[P12.2 §4.2](./backend-expansion-plan-p12.zh.md#42-dashboardsummary--response-shape)
以 `(month ASC, currency ASC)` 排序 `MonthCurrencyAmount[]`。需要 pivot
成 ECharts series 形态：

```ts
function buildChartOption(rows: MonthCurrencyAmount[]) {
  // 收集 unique month（x 轴 category）和 currency（series）
  const monthsSet = new Set<string>()
  const currenciesSet = new Set<string>()
  for (const r of rows) {
    monthsSet.add(r.month)
    currenciesSet.add(r.currency)
  }
  const months = [...monthsSet].sort()
  const currencies = [...currenciesSet].sort()

  // (month, currency) → amount 索引
  const byKey = new Map<string, number>()
  for (const r of rows) {
    byKey.set(`${r.month}|${r.currency}`, Number(r.amount))
  }

  // 构 series
  const series = currencies.map(c => ({
    name: c,
    type: 'bar',
    stack: 'pnl',   // ← 关键：同 stack 名 → bar 堆叠
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

**组件形态。**

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

颜色选择：V1 直接吃 ECharts 默认调色板。V1.x 要加品牌色，通过
`option.color` 数组覆盖。负数自动绘到 x 轴下（ECharts 堆叠柱按
positive/negative 分子栈处理符号）。

### 5.5 `DashboardView.vue` 重写

把占位卡布局替换为真正 dashboard。

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

      <!-- 总览条 -->
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

      <!-- Per-currency 卡 -->
      <n-grid v-if="summary" :cols="4" :x-gap="12" :y-gap="12" style="margin-top: 16px">
        <n-gi v-for="row in summary.closed.per_currency_pnl" :key="`closed-${row.currency}`">
          <PerCurrencyCard label="Realized P/L (closed)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
        <n-gi v-for="row in summary.open.per_currency_net_cash_flow" :key="`open-${row.currency}`">
          <PerCurrencyCard label="Net Cash Flow (open)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
      </n-grid>

      <!-- 图表 -->
      <div style="margin-top: 24px">
        <MonthlyPnlChart v-if="summary" :rows="summary.closed.monthly_pnl" />
      </div>

      <!-- 表格 -->
      <n-grid :cols="1" :y-gap="16" style="margin-top: 24px">
        <n-gi><OpenPositionsTable /></n-gi>
        <n-gi><ClosedPositionsTable /></n-gi>
      </n-grid>

    </n-spin>
  </AuthenticatedLayout>
</template>
```

**空状态语义：**

- `summary.closed.count === 0 && summary.open.count === 0` → 只渲染胜率
  仪表（"—"）+ 计数块（"0"）；per-currency 网格空；图表用自身空状态。
- `closed.count === 0 && open.count > 0` → 只渲染 open 卡；图表空状态。
- `closed.count > 0 && open.count === 0` → 只渲染 closed 卡；图表渲染。

**布局响应式。** F5 是 desktop-first（按
[frontend-expansion-plan.zh.md §7](./frontend-expansion-plan.zh.md#7-路线图之后)）。
`<n-grid :cols="N">` 数值固定；小屏 Naive UI 的网格会合理自动换行。
响应式专项属 V1.x。

## 6. Codegen 工作流

F5 不引新后端端点 —— codegen 与 F4 同。

F5 出货并验完后，**锁住 CI codegen 新鲜度 gate**（按
[frontend-expansion-plan.zh.md §5](./frontend-expansion-plan.zh.md#5-横切--延后交付物已登记追踪) 建议）
如果还没出。F5 是 F6 Docker 构建之前的最后 F-phase；gate 防止 V1 与
V1.x 后端变更间 schema 漂移。

## 7. 测试策略

- **F5 不写自动化前端测试。** 手动 recipe（§8）是门槛。图表 pivot
  helper（`buildChartOption`）是干净的纯函数候选，V1.x 若长出分支可以
  补 Vitest；V1 里它是 ~30 行直接 pivot。
- **后端回归** —— F5 工作后保持绿。
- **视觉回归** —— Playwright 截图测试属 V1.x；V1 走手动 recipe 定性
  检查。
- **跨阶段一致性约束**（[V1 决策 5](./v1-release-plan.zh.md#决策-5--派生值单仓位前端算列表与聚合后端算)）
  手动验：开仓表逐行的 `roi_on_capital`（前端经 `computeRoi` 计算）必须
  与同 position 在详情页 Overview tab 显示的值一致。两边 import 同一份
  helper 文件 —— 单一真理源。

## 8. 手动验证 recipe

前提：后端 P12.2 部署；前端 `localhost:5173`；Alice 登录；有代表性数据
（多 currency、open + closed 混合、跨 ≥3 个日历月）。最简种子流程：重跑
F4 §8 recipe 到第 10 步，再至少关一个 position 让 `closed.monthly_pnl`
非空。

1. 以 Alice 登录 → 跳 `/` → `DashboardView` 渲染。
2. **总览条** —— 胜率仪表、Open positions 计数、Closed positions 计数都
   在顶部可见。数值与 `/api/dashboard/summary` 返回一致（curl 端点核对）。
3. **Per-currency 卡** —— 用户交易的每个 currency 都会同时渲染 "Open"
   （net cash flow）与 "Closed"（realized P/L）卡，前提是数据存在。
   负绿正红。用户只有单 currency 时只渲染该 currency 卡。
4. **按月 PnL 图：**
   - ≥1 个 closed 仓位时：图渲染，x 轴 = month，per-currency 堆叠柱，
     legend 列 currency。悬停柱 → tooltip 显示月份 + per-currency
     拆分。
   - 零 closed 仓位时：图显示空状态 *"No closed positions yet — chart
     will populate after the first close."*
5. **开仓表** —— 每个 open 仓位一行。列正确渲染：Symbol、Strategy、
   Opened at、Net Cash Flow（按符号绿/红、按 currency 加前缀）、
   Days open（前端算；应与 Position 详情 Overview 的 `days_open` 一致）、
   ROI %、Currency、Open 操作。点 Open → 跳 `/positions/{id}`。
6. **平仓表** —— 每个 closed 仓位一行。Realized P/L 与行的
   `pnl_realized` 一致；Result tag 正确显 Win/Loss/Breakeven。
7. **一致性约束（V1 决策 5）。** 挑一个 open 仓位；记下 dashboard 上的
   ROI。点 Open → 详情页 Overview tab 的派生卡 ROI **必须**与 dashboard
   值精确到两位小数一致。`days_open` 同。
8. **多 currency 压测。** 建一个 EUR 的 Position+Trade（EUR account +
   `currency=EUR` instrument）。刷 dashboard → 新 EUR 卡出现；如果有
   closed-month EUR 数据，图表 legend 也加 EUR。Dashboard **不**展示
   合并 "Total" 行 —— V1 故意不算 FX 换算。验证无该行。
9. **跨用户隔离。** 退出，注册 `bob@example.com`，登录 → dashboard 全
   零 / 空。Bob 看不到 Alice 数字。
10. **加载状态。** DevTools 限流 → 刷 `/` → `/api/dashboard/summary`
    在飞期间显示 `<n-spin>`。
11. **错误状态。** 停后端；刷 `/` → 显示 `<n-alert type="error">` 含
    "Failed to load dashboard" / 网络错误。关 alert → 状态留到下次
    `refresh()`。重启后端，导航离开再回 → alert 清掉，数据加载。
12. **鉴权 gate。** 退出 → 访 `/` → router 跳 `/login`（F0 行为）。
    未鉴权用户不会渲染半截 dashboard。
13. **构建体积理智检查。** `npm run build` → 看 `dist/` 体积；加
    `vue-echarts` + `echarts`（tree-shake 仅柱状图）应增量 ~150–200 KB
    gzipped。若爆到 >500 KB，§3 的 import 策略错了 —— 复查
    `use([...])` 里是否漏掉了不必要的 `BarChart` 邻近组件。
14. **vue-tsc 干净。** `npm run build` 无类型错。`vue-echarts` 类型应
    直接解析。
15. **Mount 语义。** 从 `/dashboard` 跳 `/positions` 再回。`useDashboard()`
    每次 mount 都该 `refresh()` —— 数据与后端状态同步无需手动刷页。
16. **F1–F4 全流程烟测。** 跑一遍完整 register → account → instrument
    → position → trade → close-position → refresh-dashboard 走查；预期：
    每个 dashboard 数字都反映最近一次动作。
17. 后端日志：只出预期请求，无 500、无 IntegrityError。所有步骤后
    `pytest -q` 仍绿。

## 9. F5 之后

F5 落地后，**V1 唯一剩下的工作是 F6**（单容器 Docker）。F6 后 V1 可
发版。

F5 期间种下的 V1.x 候选：

- **`@unovis/vue` 重评估** —— V1 决策 3 取了 `vue-echarts`；V1.x 长出
  多类型图且某一边明显更合适时换。单图出货让换成本极低。
- **日期范围 picker** 在 summary 端点（`?from=YYYY-MM-DD&to=YYYY-MM-DD`）
  —— 需要小后端扩展；出 V1 范围。
- **Per-strategy drill-down**（`?strategy_type=wheel`）—— 同形态。
- **多图 dashboard** —— 折线趋势、散点、日历热力图。
- **FX 换算视图** —— 需要 `FxRate` 表 + provider；点亮 per-currency 卡
  上的 "Convert to base currency" 开关。
- **未实现 PnL 行** —— 需要行情 provider；会在每 currency open 卡旁边
  加一张 "Pnl total (incl. unrealized)" 卡。
- **视觉回归测试** —— 布局稳定后用 Playwright 截图。
- **Currency 切换器图表变体** —— 堆叠柱的备选，ECharts 配
  `<n-segmented>` 跑同数据可轻易加。

F5 后 V1 横切清单收敛到：

- **CI codegen gate** —— 这里锁住（如果还没）。
- **Postgres 等价性验证** —— F6 部署前对 Postgres 跑测试套件
  （按 [V1 release plan §8.2](./v1-release-plan.zh.md#82-postgres-等价性验证)）。
- **人工验收 walkthrough** —— 当 F6 是最后未打勾 phase 时，写进 V1
  release plan §8.3（按 V1 §8.3 延后说明）。

---

## 变更日志

- **v0.1（2026-05-28）** —— F5 plan 初版。图表形态已定
  （[V1 决策 3](./v1-release-plan.zh.md#决策-3--图表vue-echarts) 决定了
  库；F5 决定柱状变体）：**per-currency 堆叠、每月一柱**，单张全宽
  图。备选（currency 切换器 / grouped bars）记录给 V1.x。Plan 覆盖：
  `src/api/dashboard.ts`、`useDashboard()` composable、5 个新展示组件
  （`MonthlyPnlChart`、`PerCurrencyCard`、`DashboardWinRateGauge`、
  `OpenPositionsTable`、`ClosedPositionsTable`）、`DashboardView` 全量
  重写，以及 `vue-echarts` + `echarts` 依赖（tree-shake import）。
  复用 F3 的 `src/utils/positionDerived.ts` 给开仓表逐行派生展示
  （V1 决策 5 一致性约束）。无内部子阶段。F5 出货后 V1 只剩 F6
  （Docker）。
