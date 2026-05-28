# 前端 Phase F3 — Position CRUD + 详情页

**Language:** [English](./frontend-implementation-plan-f3.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-28）。配套
> [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md)（macro 路线图）、
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星）、
> [frontend-implementation-plan-f2.zh.md](./frontend-implementation-plan-f2.zh.md)
> （F2 模式参考）、[data-model.zh.md](./data-model.zh.md)、以及后端
> [backend-expansion-plan-p8.zh.md](./backend-expansion-plan-p8.zh.md)
> （Position）、[backend-expansion-plan-p10.zh.md](./backend-expansion-plan-p10.zh.md)
> （strategy-meta）、[backend-expansion-plan-p11.zh.md](./backend-expansion-plan-p11.zh.md)
> （TradePlan）、[backend-expansion-plan-p12.zh.md](./backend-expansion-plan-p12.zh.md)
> （Position list/detail 上的 `net_cash_flow`）。先在这里迭代，再动手写代码。

## 1. 目的

F3 建立在后端 **P8**（Position CRUD）、**P10**（策略元数据扩展）、
**P11**（TradePlan 事件流）以及 **P12.1**（Position list/detail 上的
`net_cash_flow`）之上 —— 这些后端已全部交付。F3 提供用户的主工作区：

- `/positions` 上的可浏览 Position 列表（按 `strategy_type` / `status` 过滤，
  默认 `status=open`，按 `opened_at DESC` 排序，展示来自 P12.1 的
  `net_cash_flow` 列）。
- Position 创建 / 编辑 modal —— 复用 F2 的 `InstrumentPicker`，新增
  `allowCreate` prop，让用户能在表单里就地新建 instrument，不必跳出。
- `/positions/:id` 的 Position 详情页，按
  [v1-release-plan.zh.md §6.2](./v1-release-plan.zh.md#62-f3--position-ui)
  方案上四 tab：**Overview** / **Meta**（按 `strategy_type` 条件渲染 wheel 或
  PMCC）/ **Plan**（TradePlan 事件流）/ **Trades**（F3 占位，F4 接入实操）。
- F4 的接驳点：Position 详情页里给 F4 的 `TradeEntryModal` 留好槽位；
  Position 创建流程因 Trade-led 模型需要嵌入 `TradeEntryModal` 收第一笔
  Trade。**F3 只到接缝为止**：F3 把 Position 创建表单和"首笔 Trade 子区域"
  的外壳搭好，子区域的真正实现留给 F4。精确契约见 §5.5。

这是用户的主工作区。F3 落地之后，剩余 V1 表面（F4 trade 录入、F5
dashboard）相对 F3 都只是叠加。

F3 完全沿用 F1 + F2 的模式（codegen → 资源 API 模块 → composable → 表单
modal → 视图 + AuthenticatedLayout 槽位）。唯一新增的共享构件：

- `InstrumentPicker.allowCreate` prop（既有组件扩展）。
- 小组件 `PositionStatusBadge`（只读展示 `open` / `closed`）。
- 详情页的 tab 条范式 —— 未来其他实体若也长成 tab-shaped 详情，可复用。

## 2. 范围

### 在本计划范围内

- **`src/api/positions.ts`** —— P8 的 5 个端点（`list`、`get`、`create`、
  `update`、`remove`）的类型化包装，返回带 P12.1 `net_cash_flow` 字段的
  `PositionRead`。
- **`src/api/tradePlans.ts`** —— P11 的 4 个端点（`list`、`current`、
  `byRevision`、`append`）的类型化包装。
- **`src/api/strategyMeta.ts`** —— P10 的 8 个端点（wheel 4 个 + pmcc 4 个），
  嵌套在 `/positions/{pid}/wheel-meta` 与 `.../pmcc-meta`。
- **`usePositions()` composable** —— 列表状态，带 `status` + `strategy_type`
  过滤器与 `refresh()`。
- **`usePosition(positionId)` composable** —— 详情页单仓位状态；在 PATCH
  和子 tab 数据变化后刷新。
- **`useTradePlans(positionId)` composable** —— Plan tab 的 append-only 事件流
  状态。
- **`useWheelMeta(positionId)` / `usePmccMeta(positionId)` composable** ——
  Meta tab 的 1:1 策略元数据状态。
- **`InstrumentPicker.vue` 扩展** —— 新增 `allowCreate` prop。开启后，picker
  下拉列表底部多一行 *"+ Create new instrument"*；点击会以创建模式打开
  F2 既有的 `InstrumentForm.vue`；`@saved` 后 picker 自动选中新建的
  instrument。F3 中 `allowCreate` 的首位消费者是 `PositionFormModal`。
- **`PositionStatusBadge.vue`** —— 极小展示组件，用 `<n-tag>` 表示 `status`
  （`open` 走 success / `closed` 走 default）。
- **`PositionFormModal.vue`** —— 创建 / 编辑 modal。**创建态**含 F2
  `InstrumentPicker`（带 `allowCreate`）选 `primary_instrument_id`，Account
  选择器，`StrategyType` 选择器，`opened_at`（来自首笔 Trade），以及手填
  字段（`capital_used`、`max_risk_at_open`、`max_reward_at_open`、`notes`）。
  创建态提交时**必须先收下首笔 Trade** —— F3 先把"首笔 Trade"子区域的*外壳*
  做出来；**F4 在那个槽位里接入实际的 `TradeEntryModal`**。契约详见 §5.5
  *Trade-led 接缝*。**编辑态**仅手填字段可写（按 P8，`account_id`、
  `primary_instrument_id`、`strategy_type`、`opened_at`、`currency`、
  `pnl_realized`、`status` 不可变 —— 在表单中渲染为 disabled）。
- **`PositionsView.vue`**（`/positions`）—— 列表，带 `status` 过滤（默认
  `open`）+ `strategy_type` 过滤 + `+ New position` 按钮。列：symbol（从
  关联 instrument 取；V1 通过 `useInstruments` 查表）、`strategy_type`、
  `opened_at`、`net_cash_flow`（带 currency 前缀；status=open 时列标题为
  *"Net Cash Flow"*，status=closed 时切换为 *"Realized P/L"* —— 同一列槽位
  双标签，依
  [P12 详细计划 §8](./backend-expansion-plan-p12.zh.md#8-after-p12)
  约定）、`currency`、状态 badge、"Open" 操作。
- **`PositionDetailView.vue`**（`/positions/:id`）—— 页面含 header（symbol、
  strategy、状态 badge、opened_at、currency、"Edit" + "Delete" + "Close"
  按钮）和 `<n-tabs>`：
  - **Overview** —— 手填字段 + 派生 + 资金效率。
  - **Meta** —— wheel funding/loan/interest 表单（`strategy_type === 'wheel'`
    时）或 PMCC LEAP picker（`strategy_type === 'pmcc'` 时）；其他策略
    显示空状态。
  - **Plan** —— TradePlan 事件流：oldest-first 修订列表 + "+ New
    revision" 表单。
  - **Trades** —— 时间线列表，F3 **只读占位**（"F4 会在这里接入录入
    modal"）。F3 *会* 渲染该 position 的既有 trade（消费 P9 的
    `GET /api/trades?position_id=`），让通过 curl 创建过 trade 的用户
    看到非空页面；pattern badge 和录入 modal 留给 F4。
- **路由** —— 新增 `/positions` 与 `/positions/:id`。
- **`AuthenticatedLayout.vue`** —— 在 `Instruments` 与 `Settings` 之间加
  `Positions` 导航项。
- **`DashboardView.vue`** —— 把 `Positions` 占位卡翻为活动链接（计数取自
  `usePositions`）；`Trades (F4)`、`Dashboards (F5)` 保持 disabled。
- **Codegen** —— P12 后 `frontend/src/api/schema.d.ts` 已新鲜；F3 通常无需
  再跑。若 P8/P10/P11/P12 在 F3 期间收到补丁修复，再跑一次。
- **后端回归** —— 保持 ≥406 条后端测试全绿；ruff + mypy strict clean。

### 显式不在范围内（延后）

- **`TradeEntryModal.vue`** —— F4 交付。F3 在 `PositionFormModal` 上留
  *首笔 Trade 槽位*、在 `PositionDetailView` 上留 *Trades tab 占位*；
  录入 modal 实现、多腿行 UX 和前端 `action↔kind` 校验全部是 F4。
- **Trades tab 上的 pattern badge**（Assignment / Exercise / Expiration /
  IC-open 识别）—— F4。
- **trade 软删 UX** —— F4。
- **Dashboard summary 消费**（`/api/dashboard/summary`）—— F5。
- **Position `archived_at`** —— V1 不做（V1 决策 4）。
- **非 wheel / 非 pmcc 策略的 strategy-meta** —— 后端 P10 对
  `iron_condor` / `spot_stock` / `spot_forex` 没有扩展表；Meta tab 展示
  "No metadata for this strategy" 空状态。
- **批量 position 操作** —— 出 V1 范围。
- **`/positions` 分页** —— 后端 `limit=200` 上限；V1 规模足够。如果用户
  上线第二天就超了，再来评估。
- **前端单测（Vitest）** —— 仍没有够格的逻辑；后端 pytest + `vue-tsc` +
  手动点击足够。最早合适的 Vitest 候选在 F4（`action↔kind` 校验、pattern
  识别），按 V1 release plan §3。
- **把 `usePositions` 升为 Pinia store** —— composable 够用；只有当 ≥2
  组件需要超出 `refresh()` 的共享反应时才升级。
- **乐观更新** —— 每次 PATCH/POST 后手动 `refresh()`，沿用 F1 模式。
- **PMCC LEAP 自动建议** —— F3 的 LEAP picker 是
  `<InstrumentPicker :kind="'option'">` 复用既有 typeahead；专门为 LEAP
  候选（远到期、深 ITM call）做过滤延后 —— V1 用户手动挑。

## 3. 技术新增

**无。** 与 F1 + F2 同栈。

`<n-tabs>`、`<n-data-table>`、`<n-tag>`、`<n-form>`、`<n-collapse>` 都已在
项目中。唯一新增的 import 是新的 schema 类型。

## 4. 目录结构变更

```
frontend/src/
├── api/
│   ├── schema.d.ts                  ← P12 后已新鲜
│   ├── positions.ts                 ← NEW
│   ├── tradePlans.ts                ← NEW
│   ├── strategyMeta.ts              ← NEW
│   ├── instruments.ts               ← 不变
│   ├── strategyConfigs.ts           ← 不变
│   ├── accounts.ts                  ← 不变
│   ├── http.ts                      ← 不变
│   └── types.ts                     ← 不变
├── composables/
│   ├── usePositions.ts              ← NEW
│   ├── usePosition.ts               ← NEW
│   ├── useTradePlans.ts             ← NEW
│   ├── useWheelMeta.ts              ← NEW
│   ├── usePmccMeta.ts               ← NEW
│   ├── useAccounts.ts               ← 不变
│   ├── useInstruments.ts            ← 不变
│   └── useStrategyConfigs.ts        ← 不变
├── components/
│   ├── AuthenticatedLayout.vue      ← CHANGED：加 Positions 导航
│   ├── InstrumentPicker.vue         ← CHANGED：加 allowCreate prop
│   ├── PositionFormModal.vue        ← NEW
│   ├── PositionStatusBadge.vue      ← NEW
│   ├── WheelMetaForm.vue            ← NEW
│   ├── PmccMetaForm.vue             ← NEW
│   ├── TradePlanForm.vue            ← NEW（append 修订表单）
│   ├── TradePlanList.vue            ← NEW（修订历史）
│   ├── PositionTradesPlaceholder.vue ← NEW（F3 占位，F4 替换）
│   ├── InstrumentForm.vue           ← 不变
│   ├── CurrencySelect.vue           ← 不变
│   └── AccountFormModal.vue         ← 不变
├── router/
│   └── index.ts                     ← CHANGED：加 /positions + /positions/:id
└── views/
    ├── PositionsView.vue            ← NEW
    ├── PositionDetailView.vue       ← NEW
    ├── DashboardView.vue            ← CHANGED：Positions 卡片激活
    ├── InstrumentsView.vue          ← 不变
    ├── SettingsStrategiesView.vue   ← 不变
    └── AccountsView.vue             ← 不变
```

`PositionTradesPlaceholder.vue` 刻意拆出 `PositionDetailView`，F4 可以直接
替换为 `PositionTradesTab.vue` 而不动父组件。

## 5. 构建交付物

实施者可按自己的节奏组织顺序；硬约束只有 **API 客户端 → composable →
表单组件 → 视图 → 导航接线**。下面是一个能保证每段提交后 `npm run build`
都绿的推荐顺序。

### 5.1 API 客户端

**`src/api/positions.ts`** —— P8 的 5 个端点 + P12.1 `net_cash_flow` 字段的
类型化包装。

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

`net_cash_flow` 按 `schema.d.ts` 是 string（Decimal）。composable 原样暴露；
view 用 `Number(...)` 做算术或 `new Intl.NumberFormat(...).format(...)`
展示。

**`src/api/tradePlans.ts`** —— P11 包装。append-only、oldest-first 列表、
"current" 是最大 revision 行的别名。

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

**`src/api/strategyMeta.ts`** —— P10 的 8 个端点。

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

按 [P10 已定决策](./backend-expansion-plan-p10.zh.md)，没有 meta 行时
GET **404**；composable 把这映射为 `meta.value = null`，而不是当错误。

F3 占位用的 Trades 读取复用 `/api/trades?position_id=`（P9）。F3 不完整
出货 `src/api/trades.ts` —— 那是 F4 —— 但需要一条简短读取路径：

```ts
// 内联在 usePosition.ts（临时；F4 提到 src/api/trades.ts）
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

若 `schema.d.ts` 已有 `components['schemas']['TradeRead']`（已确认有），直接
用它即可。

### 5.2 Composables

**`usePositions()`** —— 仿 `useAccounts`。状态：`positions`、`loading`、
`error`、`statusFilter`（默认 `'open'`）、`strategyTypeFilter`（默认 `''`
表示全部）。watch 两个过滤器；变动时调 `refresh()`。暴露 `refresh()`、
`create(payload)`（调 `positionsApi.create` 后 `refresh()`）。

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

**`usePosition(positionId)`** —— 单仓位状态。状态：`position`、`loading`、
`error`、`refresh()`、`update(payload)`、`close()`（PATCH `status=closed`）、
`remove()`。详情页 mount 时调 `refresh()`，每次 tab 数据变动后也调一次。

**`useTradePlans(positionId)`** —— append-only 事件流。状态：`revisions`
（oldest-first）、`current`（computed：`revisions[revisions.length - 1] ?? null`）、
`loading`、`error`、`refresh()`、`append(payload)`。

**`useWheelMeta(positionId)` / `usePmccMeta(positionId)`** —— 1:1 meta 状态。
状态：`meta`（可空 —— 404 时为 null）、`loading`、`error`、`refresh()`、
`createOrUpdate(payload)`（`meta == null` 时 POST，否则 PATCH）、`remove()`。

所有 composable 沿用 F1/F2 模式：`refreshSeq` 实现 last-requested-wins、
`error` 取自 `ApiError.message`、不引 Pinia。

### 5.3 `InstrumentPicker.vue` —— 新增 `allowCreate` prop

F2 的 `InstrumentPicker` 是 select-only。F3 的 `PositionFormModal` 需要在
用户输入未入库的 symbol 时就地新建（Trade-led 模型决定了新 Position 常
对应全新的 instrument）。

**Prop 扩展。**

```ts
defineProps<{
  modelValue: string | null
  kind?: InstrumentKind
  placeholder?: string
  allowCreate?: boolean    // NEW —— 默认 false（保留 F2 调用方行为）
}>()
```

**`allowCreate === true` 时的行为。** 当 typeahead 查询无结果时，下拉
末尾多一行：

> **+ Create new instrument matching "<query>"**

点击 → 以创建模式打开 F2 既有的 `InstrumentForm.vue`，kind 预选（picker
传了 `:kind` 时）、`symbol` 预填 picker 当前输入。`InstrumentForm` 触发
`@saved` 后：

1. picker 自动选中新建 instrument（emit `update:modelValue` 携新 id）。
2. 关闭 InstrumentForm modal 和 picker 下拉。
3. 把新建 instrument 塞进 picker 本地的 `useInstruments` 列表（乐观；下次
   `refresh()` 会复核），让已选项可以正常显示。

`kind="option"` 时按
[V1 release plan 决策 1](./v1-release-plan.zh.md#决策-1--instrumentpicker get-or-create--allowcreate-prop)
走两步式 UX：picker 先要求选 *underlying*（option 标签页内嵌一个
stock-kind picker），然后填合约属性（`opt_type` / `strike` / `expiry` /
`multiplier`）。F2 的 `InstrumentForm` 已实现这一切；picker 只是把 kind
透传。

`kind` **未指定**时，picker 覆盖全部 kind —— "Create new" 末尾行打开
`InstrumentForm`，由用户在表单里挑 kind。

### 5.4 `PositionStatusBadge.vue`

列表 + 详情页 header 用的 10 行展示组件。除 `status` 外无其他 prop。

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

### 5.5 `PositionFormModal.vue`（创建 / 编辑）

单个 modal，按 `mode` prop 切换 create / edit。

**字段，create 态。**

| 字段                  | 组件                                | 必填 | 备注 |
|---|---|---|---|
| `account_id`          | `<n-select>` 跑 `useAccounts()`     | ✅ | 过滤 `archived_at != null`。 |
| `primary_instrument_id` | `<InstrumentPicker :allowCreate>` | ✅ | picker 提供就地创建。 |
| `strategy_type`       | `<n-select>` 跑 `StrategyType`      | ✅ | 默认不选；提交前必填。 |
| `opened_at`           | `<n-date-picker type="datetime">`   | ✅ | **见下方"Trade-led 接缝"。** |
| `capital_used`        | `<n-input-number>`                  | 可选 | 按所选 instrument 的 currency 加前缀。 |
| `max_risk_at_open`    | `<n-input-number>`                  | 可选 | 同上。 |
| `max_reward_at_open`  | `<n-input-number>`                  | 可选 | 同上。 |
| `notes`               | `<n-input type="textarea">`         | 可选 | data-model §4.4，最大 4000 字符。 |
| （服务端派生）        | currency                            | — | 选中 instrument 后从 `useInstruments` 取值，在 picker 旁以只读 badge 展示。 |

**字段，edit 态。** 仅手填子集可写（`capital_used`、`max_risk_at_open`、
`max_reward_at_open`、`notes`）。`account_id`、`primary_instrument_id`、
`strategy_type`、`opened_at`、status、`pnl_realized`、`currency`、
`net_cash_flow` 全部 **只读**（按
[P8 已定决策](./backend-expansion-plan-p8.zh.md)）渲染为 disabled。关仓
是**独立动作**（见详情页 header 的 "Close position"，§5.7）—— 不藏在编辑
modal 里。

#### Trade-led 接缝（F3↔F4 契约）

按 [v1-release-plan 决策 5](./v1-release-plan.zh.md#决策-5--派生值单仓位前端算列表与聚合后端算)
和
[P8 模型决策](./backend-expansion-plan.zh.md#6-设计决策)，新 Position
必须与首笔 Trade 同生，首笔 Trade 的 `executed_at` 等于 `opened_at`。F3
靠自己无法完整兑现，因为 TradeEntryModal 是 F4 交付物。

**F3 只出接缝，不出实现：**

1. `PositionFormModal`（create 态）在手填字段下方渲染一个 **"First
   Trade" 子区域**。标题：*"This position will be created with its first
   Trade — required by the Trade-led model."* 子区域**是一个槽位**，
   渲染 `<PositionTradesPlaceholder mode="first-trade" />`：*"First
   Trade entry will be wired in F4."*
2. **F3 临时行为，只在 `?legacy=true` query param 开启时存在：** F4 在
   工时，允许只 POST Position（`opened_at` 手填）而不强制首笔 Trade。
   用户通过 curl 后挂 Trade。**这是开发临时拐杖，F4 落地时拆除。** V1
   生产用户永远看不到没有 F4 的创建 modal，因为两者在同一个 V1 发版
   里出货。
3. **F4 契约。** F4 把首笔 Trade 槽位里的 `PositionTradesPlaceholder`
   替换为真正的 `TradeEntryModal` *内联表单*（不是嵌套 modal —— trade
   行就生活在 Position 创建 modal 里）。F4 还接管 submit handler：
   一次 POST `/api/positions`（服务端派生 `currency`），紧接一次 POST
   `/api/trades` 写首笔 Trade；`opened_at` 由 modal 自动取自首笔 Trade
   的 `executed_at`。

**为什么 F3 出占位而不一次性把两者都做完。** F3 已经够大（5 组件、5
composable、2 视图、8 个端点级的 API 客户端）。F4 会专注于
TradeEntryModal + Trades-tab 逻辑；如果把 inline-Trade 表单塞进 F3，会
冲淡范围。接缝很小（一个槽位组件）；F4 的 plan 会记录精确替换步骤。

**Submit handler（edit 态）。**

```ts
await positionsApi.update(props.positionId, payload)
message.success('Position updated')
emit('saved')
```

**Submit handler（create 态，F3 拐杖路径）。**

```ts
const position = await positionsApi.create(payload)
message.success(`Position created — attach first Trade via Trades tab (F4)`)
emit('saved', position)
```

F4 计划会用 Position+Trade 原子流取代这段。

### 5.6 `PositionsView.vue`（`/positions`）

布局（`<AuthenticatedLayout>` 之内）：

- **页头** —— 标题 "Positions"，右对齐 `+ New position` 按钮（以创建模式
  打开 `PositionFormModal`）。
- **过滤条：**
  - status `<n-select>`：All / Open / Closed；默认 Open。
  - `strategy_type` `<n-select>`：All / Wheel / Iron Condor / PMCC /
    Spot Stock / Spot Forex（枚举从 `schema.d.ts` 取）。
  - 都绑到 `usePositions()`。
- **`<n-data-table>`：**
  - **Symbol**（字符串）—— 从 `useInstruments` map 关联（view mount 时一次
    `/api/instruments?limit=200`，构建 `Record<id, Instrument>` 缓存视图
    生命周期）。
  - **Strategy** —— `StrategyType` 枚举的可读化（`wheel` → "Wheel"、
    `iron_condor` → "Iron condor" 等）。
  - **Opened At** —— `<n-time :time>` 相对 + tooltip 显示绝对 UTC。
  - **Net Cash Flow / Realized P/L** —— 同列槽位，按行 `status` 切换标签。
    值：`position.net_cash_flow` 以 `<currency> <amount>` 格式渲染（如
    `USD 125.00`）。颜色：正数绿、负数红、零中性。已平仓行展示
    `pnl_realized`（按 P12 设计与 `net_cash_flow` 数学相等，但 status=closed
    时"已实现"框架更贴近用户心智）。
  - **Currency** —— `position.currency`。
  - **Status** —— `<PositionStatusBadge>`。
  - **Actions** —— `Open` 按钮 → `router.push('/positions/{id}')`。
- **空状态** —— `<n-empty>` "No positions yet" + `+ New position` CTA。
- **加载** —— `<n-spin>` 罩表格期间。
- **错误** —— `<n-alert type="error">` 显示 `error.value`，带 retry。

`PositionFormModal @saved` 时：调 `refresh()`，关闭 modal（edit 态）或
跳到新建 position 详情页（create 态）。

### 5.7 `PositionDetailView.vue`（`/positions/:id`）

布局：

- **页头**卡：
  - 左：instrument symbol（大）、strategy type、`<PositionStatusBadge>`、
    opened_at +（如已平仓）closed_at、currency。
  - 右：操作按钮：
    - **Edit** —— 以 edit 态打开 `PositionFormModal`。
    - **Close** —— `status === 'closed'` 时 disabled；否则 `<n-popconfirm>`
      *"Close this position? `pnl_realized` will be frozen as
      SUM(trade.cash_flow). This cannot be undone."* 确认后调
      `usePosition.close()` → PATCH `status=closed` → `refresh()`。
    - **Delete** —— `<n-popconfirm>` *"Delete this position? Only allowed
      when no trades are attached."* 确认后调 `usePosition.remove()`。
      后端 409（有 trade 挂着）时内联展示 *"This position has attached
      trades and cannot be deleted. Archive trades first."*
- **`<n-tabs type="line">`** —— 顺序：Overview / Meta / Plan / Trades。
  tab 选择与路由 query 同步（`?tab=meta` 等）实现深链；默认 Overview。

四个 tab：

#### 5.7.1 Overview tab

两列网格（`<n-grid :cols="2">`）：

- **左列 —— 手填字段卡。** 只读展示 `capital_used`、`max_risk_at_open`、
  `max_reward_at_open`、`notes`（带 currency 前缀）。下方内联 "Edit" 链接
  → 以 edit 态打开 `PositionFormModal`。
- **右列 —— 派生计算卡**（按 V1 决策 5：前端算）。字段：
  - `days_open` —— `Math.floor((closed_at ?? now - opened_at) / 86_400_000)`，
    标签切换：status=open 时 "Days open"，已平仓时 "Days held"。
  - `net_cash_flow` —— 服务端供（`position.net_cash_flow`），带符号 + 货币
    展示。
  - `pnl_total` —— V1 中等于 `net_cash_flow`（未实现属 V1.x）。与
    `net_cash_flow` 显示值一致；标签按 status 在列表里同样切换。单独一行
    保留，V1.x 加未实现时公式槽位已就位。
  - `roi_on_capital` —— `capital_used > 0` 时 `(pnl_total / capital_used)
    * 100`；否则 "—"。格式：`12.50%`（两位小数）。
  - `result` —— status=closed 时：`pnl_realized > 0 ? 'Win' : pnl_realized
    < 0 ? 'Loss' : 'Breakeven'`，渲染为 `<n-tag>`。status=open 时隐藏。

格式规则：金额走 `Intl.NumberFormat(undefined, { minimumFractionDigits:
2, maximumFractionDigits: 4 })`；正绿负红。毫秒/天等常量住在一个小工具
`src/utils/positionDerived.ts`，导出 `computeDaysOpen`、`computePnlTotal`、
`computeRoi`、`computeResult` —— **F5 复用**（按 V1 决策 5 一致性约束，
dashboard 的 open-positions 表用同一组 helper）。

#### 5.7.2 Meta tab

按 `position.strategy_type` 条件渲染：

- **`wheel`** —— `<WheelMetaForm :positionId>`：
  - 字段：`funding_source`（枚举：`cash` / `margin` / `loan`）、
    `loan_amount`、`interest_rate_apr`（百分比）、`interest_accrued`。
  - 调 `useWheelMeta(positionId)`。mount 时：`refresh()`（200 拿到行或 404
    → `meta = null`）。
  - `meta === null` 时：内联表单预填默认（`funding_source = 'cash'`，其余
    空），底部 "Create wheel meta" 提交按钮。调 `createOrUpdate(payload)`
    走 POST。
  - `meta !== null` 时：表单预填，配 "Save" + "Delete meta" 按钮。"Save"
    走 PATCH；"Delete meta" 走 DELETE（带 `<n-popconfirm>`）。
- **`pmcc`** —— `<PmccMetaForm :positionId>`：
  - 单字段：`leap_instrument_id`，走 `<InstrumentPicker kind="option">`
    （**不**开 `allowCreate` —— LEAP 必须是既存 option；缺则用户先去
    `/instruments` 建好再回来）。
  - **校验提示：** 只读 note：*"LEAP must be an option on the same
    underlying as this position's primary instrument. The backend
    enforces this — pickers don't filter for it in V1."*
  - 与 `WheelMetaForm` 同样的 create-vs-edit 分支。
- **`iron_condor` / `spot_stock` / `spot_forex`** —— 空状态：
  `<n-empty>` *"No metadata for {strategy} positions in V1."*

按 strategy-type 分派的逻辑在 `PositionDetailView` 模板里 `v-if` 完成；
表单组件本身不知道其他策略。

#### 5.7.3 Plan tab

`<TradePlanList :positionId>` + `<TradePlanForm :positionId>` 垂直堆叠。

- **`<TradePlanList>`** —— mount 时调 `useTradePlans(positionId).refresh()`。
  渲染 `<n-timeline>` 或 `<n-list>`，oldest-first。每条：修订号、
  `effective_at`（相对 + tooltip）、`planned_entry`、`planned_stop_loss`、
  `planned_take_profit`、`target_rr`、`thesis`（截断；点击展开）。最后一
  条带 "Current" badge（`revisions[revisions.length - 1]`）。
- **`<TradePlanForm>`** —— `+ Append revision` 按钮 → 下方展开表单：
  `effective_at`（datetime picker，默认 now）、`planned_entry` /
  `planned_stop_loss` / `planned_take_profit`（`<n-input-number>` 小数）、
  `target_rr`（`<n-input-number>`，可选）、`thesis`（`<n-input
  type="textarea">`，最大 8000 字符）。提交：`useTradePlans.append(payload)`
  → 列表自动刷新（composable 的 `append()` 内会触发 `refresh()`）。

空状态（零修订）：`<n-empty>` *"No plan revisions yet"* + 同一个 append
表单预展开。

#### 5.7.4 Trades tab（F3 占位）

`<PositionTradesPlaceholder :positionId>`：

- mount 时拉 `/api/trades?position_id={positionId}`（P9）。`<n-data-table>`
  列：`executed_at`、`action` badge、`instrument`（关联 symbol）、
  `quantity`、`price`、`cash_flow`。**只读** —— 无编辑、删除、录入操作。
- 表上方：`<n-alert type="info">` *"Trade entry — including multi-leg
  flows — will land in F4. For now, trades created via the API or the
  Position-create flow's first-Trade subsection appear here read-only."*
- 零 trade 时：`<n-empty>` *"No trades yet on this position."*

F4 会把整个组件替换为 `PositionTradesTab.vue`，加上录入 modal、pattern
badge、软删 UX 和 `order_group_id` 视觉分组。**`PositionDetailView` 的
文件不需要变** —— import target 不变，只是组件实现换；所以 F3 里文件名
`PositionTradesPlaceholder.vue`（描述性的），F4 在旁边加
`PositionTradesTab.vue`；`PositionDetailView` 的 v-if 按 F4 规则切换。
当然 F4 直接原地改名也行；两种都可以。

### 5.8 路由变更

```ts
// src/router/index.ts（节选）
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

`props: true` 让 `PositionDetailView` 把 `id` 作为 prop 收，避免
`useRoute()` 模板代码。

### 5.9 `AuthenticatedLayout.vue` + `DashboardView.vue` 更新

**`AuthenticatedLayout.vue`** —— 在 `Instruments` 与 `Settings` 之间加
`Positions`。最终导航顺序：

```
Dashboard | Accounts | Positions | Instruments | Settings
```

**`DashboardView.vue`** —— 把 `Positions` 占位卡翻活：

| 卡 | 内容 | 链接 |
|---|---|---|
| Your accounts | 来自 `useAccounts` 的计数 | `/accounts` |
| Instruments | 来自 `useInstruments` 的计数 | `/instruments` |
| **Positions** | 来自 `usePositions`（status=`open`）的计数 | `/positions` |
| Strategy caps | 来自 `useStrategyConfigs` 的计数 | `/settings/strategies` |
| Trades (Phase F4) | disabled | none |
| Dashboards (Phase F5) | disabled | none |

Positions 卡展示 open-position 计数，与列表默认过滤一致。

## 6. Codegen 工作流

与 [F2 §6](./frontend-implementation-plan-f2.zh.md#6-codegen-workflow) 同一
工艺。

F3 特定提示：

- P12 后 `schema.d.ts` 已新鲜。若 P8/P10/P11/P12 在 F3 期间收到任何补丁
  修复，再跑 `npm run codegen` 并 commit diff。
- F3 **不引入新后端端点**，所以正常的 F3 PR 不应改 `schema.d.ts`。如果
  改了，是某处动了后端的信号 —— 仔细审。
- CI codegen gate：仍建议与 F3 一起出货（如果没和 F2 一起出）。

## 7. 测试策略

与 F0 / F1 / F2 同 —— **F3 不写自动化前端测试**。后端 pytest 是回归门槛；
`npm run build`（`vue-tsc`）做前端类型检查。

**前端回归点。** F3 改了 `InstrumentPicker`（加 `allowCreate`）。F2 既有
调用方（`InstrumentsView` 搜索框）必须行为不变 —— `allowCreate` 默认
false，保留 select-only。手动验证 §8 第 10 步覆盖。

后端回归仍是硬门槛，每段 F3 工作后保持绿。

## 8. 手动验证 recipe

跑端到端验证：`uvicorn` + `npm run dev`，F3 全表面建好后。前提：后端
P8/P9/P10/P11/P12 全部部署 + 迁移到 `127.0.0.1:8000`；前端
`localhost:5173`；SSH tunnel 转双端口；新建 DB。

> **关于 Trade-led 接缝的说明。** 下面创建 Position 的步骤走 F3 拐杖路径
> （§5.5）—— 首笔 Trade 用 API 直接造。F4 落地后，Position 创建 modal
> 会原子完成此事。

1. 注册 `alice@example.com` / `correct horse battery` → 跳 `/` →
   Dashboard 6 张卡（Your accounts、Instruments、**Positions**、Strategy
   caps、Trades [F4] disabled、Dashboards [F5] disabled），全部计数 0。
2. 导航：Dashboard | Accounts | Positions | Instruments | Settings。
3. 建前置：Accounts → `+ New account` → Cash USD 账户。
   Instruments → `+ New instrument` → Stock `AAPL` USD NASDAQ。
4. 点 `Positions` → `/positions`；空状态可见。Status 过滤默认 `Open`。
5. 点 `+ New position`：
   - Account 下拉显示 Cash USD。
   - 点 `primary_instrument_id` picker —— typeahead `AAPL`，选中。
     **Currency badge** 显示 `USD` 在 picker 旁。
   - Strategy 下拉 —— 选 `Spot Stock`。
   - opened_at —— 选 now（datetime）。
   - capital_used —— 1000。
   - max_risk_at_open / max_reward_at_open / notes —— 留空。
   - **First Trade 子区域** 展示占位文字：*"First Trade entry will be
     wired in F4."*
   - 提交 → toast *"Position created — attach first Trade via Trades
     tab (F4)"*；跳到 `/positions/{id}`。
6. 详情页页头：AAPL Spot Stock badge=Open opened_at USD。Edit / Close /
   Delete 按钮可见。
7. Overview tab 激活。手填卡：`capital_used: USD 1000.00`，其余 "—"。
   派生卡：`days_open: 0`、`net_cash_flow: USD 0.00`、`pnl_total: USD
   0.00`、`roi_on_capital: 0.00%`、`result` 隐藏。
8. 点 **Edit** → 以 edit 态打开 modal。Account / Instrument / Strategy /
   opened_at / status 全 disabled。改 `notes` 为 "test note" → save →
   toast → Overview 卡里 notes 出现。
9. 切到 **Meta** tab → `spot_stock` 显示空状态 *"No metadata for
   spot_stock positions in V1"*。
10. 切到 **Plan** tab → 空状态加预展开 append 表单。填 `effective_at` now、
    `planned_entry: 170`、`planned_stop_loss: 160`、`planned_take_profit:
    200`、`target_rr: 3.0`、`thesis: "earnings catalyst Q2"` → 提交 → 修订
    1 出现并带 "Current" badge。
11. 再 append 一条（`effective_at` +1 小时，`planned_stop_loss` 改为 165）
    → 修订 2 出现在修订 1 下方（oldest-first）；"Current" badge 移到
    修订 2。
12. 切到 **Trades** tab → 信息 alert 可见，空表。
13. 在 `/instruments` 建一个 Option AAPL P 220 expiry+30d。用 curl 一次
    给 position 挂 Trade：
    ```bash
    curl -fsSi http://localhost:8000/api/trades -b cookies.txt \
      -H 'Content-Type: application/json' \
      -d '{"position_id":"<pid>","instrument_id":"<stock_iid>",
           "action":"buy","quantity":"10","price":"170.50",
           "executed_at":"<opened_at>"}'
    ```
    回 Trades tab → 行只读可见。
14. 刷新 `/positions` 列表 → AAPL Spot Stock 行可见。`net_cash_flow` 列
    显示 `-USD 1705.00`（买入 → 负现金流），红色。Status 列 = Open badge。
15. **验证 `allowCreate` 就地新建。** 点 `+ New position` → 在
    `primary_instrument_id` picker 里输 `TSLA`（未入库）。下拉末行
    *"+ Create new instrument matching 'TSLA'"* → 点 → InstrumentForm 以
    Stock 标签打开，symbol 预填 `TSLA`。填 USD NASDAQ → 提交 → toast
    `Created TSLA` → InstrumentForm 关；picker 自动选中 TSLA。取消
    position-create modal（这次测试不留 TSLA 仓位）。
16. **验证 `allowCreate` 不破坏 F2 调用方。** 去 `/instruments` → 搜索
    框（也是 F2 的 `InstrumentPicker` 实例）必须仍 select-only —— 无结果
    时下拉**不**出 `+ Create` 末行。（F2 调用方没传 `allowCreate`。）
17. **关仓。** 回 AAPL 详情。点 **Close** → popconfirm 确认 → toast →
    状态 badge 翻 Closed，closed_at 出现，Overview 的 `result` 行出现
    （`pnl_realized < 0` 显示 "Loss" —— 单边买入产生负现金流）。该仓位
    在列表过滤为 Closed 时金额列的标签会变为 "Realized P/L"。
18. **验证 status 过滤。** 回 `/positions`。Status 过滤 → `Closed` →
    AAPL 行可见，金额列标签是 "Realized P/L"。`Open` → 空。`All` →
    AAPL 行可见。
19. **删除保护。** AAPL 详情 → **Delete** → popconfirm → 确认 → 预期错误
    *"This position has attached trades and cannot be deleted."*（后端
    因 13 步的 trade 返回 409。）
20. 通过 F3 modal 重新建一个无 trade 的 Position（跳过 13 步 curl）。
    现在 **Delete** 成功 → 回 `/positions`，行不见。
21. **Wheel meta。** 在 AAPL stock 上建 `strategy_type=wheel` 的 Position。
    去 Meta tab → 空 wheel 表单（默认 `funding_source=cash`）。
    `funding_source` 换 `loan`，`loan_amount: 5000`、`interest_rate_apr:
    7.5`、`interest_accrued: 20` → "Create wheel meta" → 成功 → 表单切
    edit 态，配 "Save" + "Delete meta"。刷页 → 数值持久化。
22. **PMCC meta。** 在 AAPL stock 上建 `strategy_type=pmcc` 的 Position。
    Meta tab → 表单单字段 `leap_instrument_id` picker（option-kind）。
    选 13 步的 AAPL P 220 → "Create pmcc meta" → 成功。（后端会拒绝
    underlying 不是 AAPL 的；本测试 underlying 是 AAPL，所以成功。）
23. **跨用户隔离（可选）。** 注册 `bob@example.com`，登 Bob，访
    `/positions` → 空。直接访 Alice 的 position URL → 404 页（后端按 P8
    返 404）。验证无泄漏。
24. 后端日志：只出预期请求；无 500、无 IntegrityError。每步后
    `pytest -q` 仍绿。

## 9. F3 之后

F3 落地后，下一迭代是
[F4 — Trade 录入](./frontend-expansion-plan.zh.md#f4--trade-entry)，消费
后端 P9（已交付）。F4 会：

- 把 F3 中 `usePosition` 里内联的 `Trade` 类型提取出来，构建正式的
  `src/api/trades.ts`。
- 构建 `TradeEntryModal`，Custom multi-leg 表单（V1 决策 2 —— V1 不做
  named flows）。
- 把 `TradeEntryModal` 接入 `PositionFormModal` 的 **First Trade 子区域**，
  让 Position+Trade 创建原子化，遵循 Trade-led 模型。拆掉 F3 拐杖路径
  （§5.5 第 2 条）。
- 把 `PositionTradesPlaceholder` 替换为 `PositionTradesTab`：pattern
  badge（Assignment / Exercise / Expiration / IC-open）、`order_group_id`
  视觉分组、软删 UX（P9 `archived_at`）。
- Position 详情页 Trades tab 和 Overview 卡加 "+ New trade" 按钮（V1
  决策：Add Trade 只在 Position 详情）。

如果 **CI codegen gate** 没和 F2 一起出货，F3 也是合适的位置。F3 不改
schema，但测试覆盖（注册、positions、plan、meta）冲洗大多数表面 ——
F3 后 codegen job 过则 F4 从干净基线起。

值得跟踪的小后续：在 F3 期间把 §5.7.1 的日期工具（`computeDaysOpen` 等）
抽到 `src/utils/positionDerived.ts` —— F5 会 import 用于 dashboard 每行
派生展示。

---

## 变更日志

- **v0.1（2026-05-28）** —— F3 plan 初版。三条结构性决策在 2026-05-28
  与用户对齐：
  1. **Position 详情页形态：** 独立页面 `/positions/:id`，四 tab 条
     （Overview / Meta / Plan / Trades），按 V1 release plan §6.2 原方案。
  2. **"Add Trade" 入口：** 只在 Position 详情；新 Position 通过 F3 的
     `+ New position` 流程出生，**首笔 Trade 子区域** 由 F4 接驳。
  3. **F4 named-flow 短名单：** 零 —— V1 只 Custom multi-leg（决策落在
     F4 plan，此处仅为上下文记录）。
  Plan 覆盖：5 个新 API 客户端（positions / tradePlans / strategyMeta，
  后者含 wheel + pmcc）、5 个新 composable、`InstrumentPicker.allowCreate`
  扩展、`PositionFormModal` + 4 个配套表单/列表组件、`PositionsView` +
  `PositionDetailView`（四 tab）。TradeEntryModal **是有意接缝**，§5.5
  记录 —— F3 出槽位、F4 填实。Trade-led 原子 Position+Trade 创建落在
  F4。无新依赖；无内部子阶段。
