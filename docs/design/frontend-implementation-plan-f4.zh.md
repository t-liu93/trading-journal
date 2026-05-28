# 前端 Phase F4 — Trade 录入 UI

**Language:** [English](./frontend-implementation-plan-f4.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-28）。配套
> [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md)（macro 路线图）、
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星）、
> [frontend-implementation-plan-f3.zh.md](./frontend-implementation-plan-f3.zh.md)
> （F3 模式参考 + F4 要填的接缝）、[data-model.zh.md](./data-model.zh.md)
> （尤其
> [§4.5 Trade](./data-model.zh.md#45-trade-atomic-event) 与
> [§4.5.2 Notion 事件 ↔ 原子 trade 映射](./data-model.zh.md#452-notion-event--atomic-trade-mapping)）、
> 以及后端
> [backend-expansion-plan-p9.zh.md](./backend-expansion-plan-p9.zh.md)（Trade）。
> 先在这里迭代，再动手写代码。

## 1. 目的

F4 建立在后端 **P9**（Trade CRUD）和 F3 留下的接缝之上。它出货 journal 的
数据录入主力：

- 类型化 `src/api/trades.ts` 客户端（替换 F3 内联在 `usePosition.ts` 里的
  `Trade` 类型）。
- 可复用 `TradeEntryModal.vue` —— Custom multi-leg 表单，按
  [V1 release plan 决策 2](./v1-release-plan.zh.md#决策-2--f4-trade-录入custom-multi-leg-为主)。
  增删 leg 行；同一次提交所有行共享一个服务端分配的 `order_group_id`
  （P9 多腿 POST）。
- 把 `TradeEntryModal` 接入 **两个**消费点：
  1. **F3 `PositionFormModal` 首笔 Trade 子区域** —— 兑现 Trade-led 模型
     （Position 与首笔 Trade 同生）。替换
     [F3 §5.5](./frontend-implementation-plan-f3.zh.md#55-positionformmodalvue创建--编辑)
     里的 F3 拐杖路径。
  2. **`PositionDetailView` Trades tab + Overview** —— 后续 Trade 的
     `+ New trade` 按钮。
- `PositionTradesTab.vue` —— 把 F3 的 `PositionTradesPlaceholder` 替换为
  活的 Trades 视图：按 `order_group_id` 视觉分组、pattern badge
  （Assignment / Exercise / Expiration / IC-open）、软删 UX（P9
  `archived_at`）。

F4 落地后，**手动数据录入完整**。F5 读聚合、F6 出制品。V1 不再需要别的
录入流。

F4 沿用 F1/F2/F3 模式；唯一新模式是**单个表单内的多腿行动态**，规模太小
不值得抽共享层。

### Named flows —— 已定

V1 release plan §4 决策 2 把 named-flow 短名单留给本 plan。**2026-05-28
已定：V1 零 named flows。** Custom multi-leg 是唯一录入模式。理由：

- Trades tab 仍按提交行形态展示 pattern badge，所以*显示*会带出策略形态，
  即使*录入*不强制。
- 未来 V1.x 可叠加 helper（如 "Expire worthless" → 一行 qty 0 / price 0 /
  fees 0），等真实使用数据告诉我们哪些 pattern 最频繁。在 Custom
  multi-leg 之上加 helper 是叠加性的 —— 数据形态不变。
- 零 named flows 把 F4 范围卡死：一个 modal、一份表单、一组校验规则。UX
  bug 与 broker-style 仿冒风险最小化。

## 2. 范围

### 在本计划范围内

- **`src/api/trades.ts`** —— P9 的 4 个端点（`list`、`create` —— 单条或
  数组、`update` —— 仅 notes、`remove` —— 软删）的类型化包装。替换 F3
  塞进 `usePosition.ts` 的内联 `Trade` 类型。
- **`useTrades(positionId)` composable** —— 单仓位 trade 列表状态，带
  `includeArchived` 开关；`refresh()`、`createMany(rows)`、`archive(id)`、
  `unarchive(id)`（V1 仅 archive 按钮；unarchive 通过 include-archived 开关
  + 行操作暴露）。
- **`TradeEntryModal.vue`** —— Custom multi-leg 表单（V1 决策 2）。内部
  渲染 leg 行列表，每行携带 Trade-create 全字段。增删行；提交把数组
  （或单条单对象）POST 到 `/api/trades`。**两种使用模式：**
  - **standalone**（Trades tab + Overview `+ New trade`）—— `positionId`
    固定，modal 直接 POST。
  - **inline-in-PositionFormModal**（首笔 Trade 子区域）—— modal *暴露*
    行状态给父，由 `PositionFormModal` 编排 §5.4 的原子 "POST /positions
    然后 POST /trades" 序列。
- **`PositionTradesTab.vue`** —— 替换 F3 占位的活 Trades tab 实现。把
  position 的 trade 在 `<n-list>` 里按 `order_group_id` 视觉分组；每个组
  附 pattern badge（见 §5.5）；`+ New trade` 以 standalone 模式开
  `TradeEntryModal`；行级 archive / unarchive；archive 开关。
- **`PositionFormModal.vue`（修改）** —— 把 F3 的占位槽替换为内嵌
  `TradeEntryModal` 的内联表单（**不是嵌套 modal** —— 行就生活在
  `PositionFormModal` 里）。原子 submit handler：
  1. POST `/api/positions`，`opened_at` 取自 `firstTrade.executed_at`。
  2. POST `/api/trades`，把首笔 Trade 行数组里的 `position_id` 填为 step
     1 的返回。
  3. (1) 与 (2) 之间任何失败：可恢复错误浮 toast，用户留在表单上。
     step 1 创建的 Position 留作孤儿（无 trade）—— 用户可以重试 Trade
     submit，也可以去 `/positions` 删除孤儿。详见 §5.4 "Failure recovery"。
  完全拆掉 F3 的 `?legacy=true` 拐杖路径。
- **`PositionDetailView.vue`（修改）** —— 替换 import：
  `PositionTradesPlaceholder` → `PositionTradesTab`。Overview 卡右侧加小
  `+ Add trade` 操作（次级按钮），以 standalone 模式开
  `TradeEntryModal`。Overview 的派生计算卡在 trade 落地后自动刷新
  （经 `usePosition.refresh()`）。
- **`DashboardView.vue`** —— 把 Trades 占位卡翻活（计数取自
  `useTradesTotalCount` —— 见 §5.7 —— 或一个跨 position 派生 computed；
  倾向最简：dashboard 能直接拿到的聚合是 F5 路径，F4 阶段卡只贴
  "Trades" 标签不带计数即可）。
- **Codegen** —— `schema.d.ts` 已含 Trade schema；F4 不引新端点（P9 已
  交付）。仅当 P9 收到补丁时再跑。
- **后端回归** —— ≥406 条后端测试全绿；`ruff` + `mypy --strict` clean。

### 显式不在范围内（延后）

- **Named-flow helper**（Expire、Assignment、Exercise、IC-open 模板）——
  V1.x。V1 唯一录入面是 Custom multi-leg。
- **批量导入 / CSV** —— V1.x。
- **Broker API 摄入** —— V1.x；需要 V1 没有的 `BrokerCredential` 与
  auth-and-security 层。
- **Trade 除 `notes` 外的字段就地编辑** —— P9 明确除 `notes` 外不可变
  （审计完整性）。UI 与之一致：Trade 行唯一编辑操作是 "Edit notes"。其他
  修正须 archive 后重录。
- **跨 position trade 视图**（全局 `/trades` 页）—— V1 不需要；F5
  dashboard 跨 position 汇总。
- **跨 group pattern badge** —— badge 范围只在单个 `order_group_id` 内。
  没有 "我们注意到你的股票是上周卖出 option 被指派的"这种跨组推断；
  assignment 识别只在双腿同 group 时生效。
- **前端单测（Vitest）** —— 按
  [V1 release plan §3](./v1-release-plan.zh.md#v1-必含) 的 F4 两个候选
  （`action↔kind` 校验、pattern badge 识别），**除非 badge 识别长出非平凡
  分支否则 Vitest 延后** —— V1 规模下两个函数都是 ~30 行纯 helper，手动
  recipe 覆盖即可。badge / cash-flow 任一长出分支时，加 Vitest 是干净的
  V1.x follow-up。
- **`order_group_id` 提交后编辑** —— 服务端不暴露；范围外。
- **从其他 archived_at 端点的 Trade-create** —— 范围外。

## 3. 技术新增

**无。** 与 F1 + F2 + F3 同栈。

如果每输一击就算行级 cash-flow 预览过慢，可复用 ~10 行 `useDebouncedRef`；
否则跳过。

## 4. 目录结构变更

```
frontend/src/
├── api/
│   ├── trades.ts                       ← NEW（替换 F3 内联类型）
│   ├── positions.ts                    ← 不变
│   ├── tradePlans.ts                   ← 不变
│   ├── strategyMeta.ts                 ← 不变
│   ├── instruments.ts                  ← 不变
│   ├── strategyConfigs.ts              ← 不变
│   ├── accounts.ts                     ← 不变
│   ├── http.ts                         ← 不变
│   └── types.ts                        ← 不变
├── composables/
│   ├── useTrades.ts                    ← NEW
│   ├── usePosition.ts                  ← CHANGED：去掉内联 Trade 类型，从 trades.ts import
│   └── （其他不变）
├── components/
│   ├── TradeEntryModal.vue             ← NEW
│   ├── TradeLegRow.vue                 ← NEW（TradeEntryModal 内单可编辑行）
│   ├── TradeActionBadge.vue            ← NEW（极小展示，像 PositionStatusBadge）
│   ├── PositionTradesTab.vue           ← NEW（接替 PositionTradesPlaceholder 的位）
│   ├── PositionTradesPlaceholder.vue   ← 保留一段，仅给 …；见 §5.5 "Deletion path"
│   ├── PositionFormModal.vue           ← CHANGED：把首笔 Trade 占位替换为 inline TradeEntryModal
│   ├── InstrumentPicker.vue            ← 不变（F3 已加 allowCreate）
│   └── （其他不变）
├── utils/
│   ├── tradeCashFlow.ts                ← NEW（客户端 cash-flow 预览）
│   └── tradePatternBadge.ts            ← NEW（按 group 识别 pattern）
├── router/
│   └── index.ts                        ← 不变
└── views/
    ├── PositionDetailView.vue          ← CHANGED：import PositionTradesTab；Overview 加 "+ Add trade"
    ├── DashboardView.vue               ← CHANGED：Trades 卡标签（可选计数）
    └── （其他不变）
```

如果 F3 之后还没有 `utils/` 顶层（F3 §9 建议 `positionDerived.ts` 住那里），
F4 顺便建上并加两个搭档 helper。

## 5. 构建交付物

推荐顺序：**API 客户端 → composable → helper → 展示组件 → TradeEntryModal
→ PositionTradesTab → 接进既有 view**。原子 Position+Trade 接线（§5.4）
放最后，因为它需要 `TradeEntryModal` 已可被 inline 模式 import。

### 5.1 API 客户端

**`src/api/trades.ts`** —— P9 4 端点的类型化包装。

```ts
import type { components } from './schema'
import { http } from './http'

export type Trade        = components['schemas']['TradeRead']
export type TradeCreate  = components['schemas']['TradeCreate']
export type TradeUpdate  = components['schemas']['TradeUpdate']  // 仅 notes
export type TradeAction  = components['schemas']['TradeAction']

export const tradesApi = {
  list: (params?: {
    position_id?: string
    order_group_id?: string
    include_archived?: boolean
  }) => http.get(`/api/trades${buildQuery(params)}`) as Promise<Trade[]>,

  /** 单条 create。后端把 order_group_id 留 NULL。 */
  create: (payload: TradeCreate) =>
    http.post('/api/trades', payload) as Promise<Trade>,

  /** 多腿 create。后端跨所有行分配一个共享 order_group_id。 */
  createMany: (payloads: TradeCreate[]) =>
    http.post('/api/trades', payloads) as Promise<Trade[]>,

  update: (id: string, payload: TradeUpdate) =>
    http.patch(`/api/trades/${id}`, payload) as Promise<Trade>,

  /** 软删（设置 archived_at）。 */
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

关键：**同一个 `/api/trades` POST** 接受对象或数组两种形态，按
[P9 已定决策](./backend-expansion-plan-p9.zh.md)。`create` 对单行只是
工效别名。

### 5.2 Composable

**`useTrades(positionId)`** —— 单仓位 trade 列表。

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

### 5.3 Helper 函数

**`src/utils/tradeCashFlow.ts`** —— 客户端 cash-flow 预览（仅展示；服务端
是唯一真理源，按
[P9 §6④](./backend-expansion-plan.zh.md#6-设计决策)）。

```ts
import type { TradeAction, TradeCreate } from '../api/trades'
import type { Instrument } from '../api/instruments'

const SIGN: Record<TradeAction, -1 | 1> = {
  buy: -1, bto: -1, btc: -1,
  sell: 1, sto: 1, stc: 1,
}

/**
 * 镜像 P9 §6④ 的后端公式。仅展示 —— 永不发给服务端
 * （P9 Create schema 拒绝客户端传入的 cash_flow）。
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
  // bto/sto/btc/stc 仅 option
  return kind === 'option'
}
```

**`src/utils/tradePatternBadge.ts`** —— 对共享 `order_group_id` 的 trade
组做 pattern 识别。镜像
[data-model.zh.md §4.5.2](./data-model.zh.md#452-notion-event--atomic-trade-mapping)。

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

  // IC-open：一个 group 4 个 option 腿、无 stock
  if (
    group.length === 4 &&
    enriched.every(e => e.instrument?.kind === 'option') &&
    enriched.every(e => e.trade.action === 'sto' || e.trade.action === 'bto')
  ) {
    return 'ic-open'
  }

  const options = enriched.filter(e => e.instrument?.kind === 'option')
  const stocks = enriched.filter(e => e.instrument?.kind === 'stock')

  // Expiration：单 option 腿、price=0
  if (group.length === 1 && options.length === 1 && Number(group[0].price) === 0) {
    return 'expiration'
  }

  // Assignment / Exercise：1 个 option 平仓 + 1 个 stock fill
  if (group.length === 2 && options.length === 1 && stocks.length === 1) {
    const optTrade = options[0].trade
    const isOptClose = optTrade.action === 'btc' || optTrade.action === 'stc'
    if (isOptClose && Number(optTrade.price) === 0) {
      // 'assignment'：short option（stc/btc）被指派变 stock；
      // 'exercise'：long option（btc）被行权。
      // V1 简单规则：short-side 平仓 → assignment；long-side → exercise。
      return optTrade.action === 'btc' ? 'exercise' : 'assignment'
    }
  }

  return null
}
```

两个 helper 都是纯函数；将来要 Vitest 时它们是干净的单测候选。

### 5.4 `TradeEntryModal.vue` + `PositionFormModal` 原子流

Custom multi-leg 表单（V1 决策 2）。两种使用模式：

**Standalone 模式**（Trades tab `+ New trade`、Overview `+ Add trade`）：
- Props：`:show`（v-model）、`:positionId`（必填）、`:accountId`（必填，
  从父 Position 取）。
- 默认 1 行 leg；`+ Add leg` 追加；每行 `Remove`（仅 >1 行时可见；最后一
  行不可删）。
- 提交：收集行，给每行填 `position_id` + （服务端派生），1 行调
  `tradesApi.create()`，≥2 行调 `createMany()`。
- 成功：emit `@saved`，父关 modal + 刷新。

**Inline 模式**（`PositionFormModal` 首笔 Trade 子区域内）：
- Props：`:show=false`（此模式不作为 modal 显示）、`:inline=true`、
  `:accountId` 取自父的 `account_id` 字段。
- 渲染行但**不自行提交**。通过 `defineExpose({ rows, validate })` 暴露，
  让 `PositionFormModal` 在原子 submit 时读行。
- 父（`PositionFormModal`）的接线：
  ```ts
  async function submitCreate() {
    const rows = tradeEntryRef.value?.rows ?? []
    if (rows.length === 0) {
      message.error('At least one Trade is required to create a Position.')
      return
    }
    if (!(await tradeEntryRef.value?.validate())) return

    // 1. opened_at 取最早行的 executed_at
    const opened_at = rows
      .map(r => r.executed_at)
      .sort()[0]

    // 2. 建 position
    const position = await positionsApi.create({
      ...positionPayload.value,
      opened_at,
    })

    // 3. 建 trade —— ≥2 行时后端自动共享 order_group_id
    const tradesPayload = rows.map(r => ({ ...r, position_id: position.id }))
    try {
      await tradesApi.createMany(tradesPayload)
    } catch (e) {
      message.error(
        `Position created (id=${position.id}) but Trade(s) failed: ` +
        `${e instanceof ApiError ? e.message : 'unknown error'}. ` +
        `Retry trade entry, or delete the orphan position from /positions.`,
      )
      return  // 让用户留在表单上，position 已创建
    }

    message.success('Position and Trade(s) created')
    emit('saved', position)
  }
  ```

**逐行字段**（两种模式同）：

| 字段             | 组件                                | 必填 | 校验 |
|---|---|---|---|
| `instrument_id`  | `<InstrumentPicker allowCreate>`    | ✅ | 沿用 picker 契约；kind 不限制（multi-leg 允许混合 stock + option） |
| `action`         | `<n-select>` 跑 `TradeAction`       | ✅ | 通过 `isValidActionForKind` 按 instrument kind 限制 —— UI 在选定 instrument 后禁用不兼容选项 |
| `quantity`       | `<n-input-number>`                  | ✅ | `> 0`；**option 必整数**（选定 instrument `kind === 'option'` 时 `step=1` + `precision=0`）；stock/forex 允许小数 |
| `price`          | `<n-input-number>`                  | ✅ | `>= 0`（按 data-model §4.5.2 worthless-expire/assignment 合法用 0） |
| `commission`     | `<n-input-number>`                  | 可选 | `>= 0`，默认 0 |
| `fees`           | `<n-input-number>`                  | 可选 | `>= 0`，默认 0 |
| `executed_at`    | `<n-date-picker type="datetime">`   | ✅ | 默认 now |
| `notes`          | `<n-input type="textarea" size="small">` | 可选 | 最大 4000 字符 |
| （预览）         | computed cash_flow                  | — | `previewCashFlow(...)`，行右只读，按 currency 加前缀；表单底部带"server 是真理源"免责说明 |

**行级校验**提交时按行跑；表单级也强制：
- ≥1 行。
- 所有行 `executed_at` 是否一致？**否** —— 行可以有不同 `executed_at`
  （比如腿到位有延时），按
  [P9 §6④](./backend-expansion-plan.zh.md#6-设计决策)；inline 模式只取
  最早的作为 `opened_at`。
- 所有行同 `account_id` —— modal 取 `:accountId` prop，不逐行；自然保证。

**失败恢复（原子流，inline 模式）。**
两步 "建 Position 再建 Trade" 模式可能中途失败：

1. POST `/api/positions` 成功，POST `/api/trades` 失败 →
   **孤儿 Position 存在，modal 不关**。toast 浮出错信息携孤儿 position
   id，提示重试 Trade 录入或去 `/positions` 删除。用户**不必**重填
   Position 级字段（已创建）。他们**可以**从同一个 modal 重发 Trade
   POST（行还在内存中）。
2. POST `/api/positions` 失败 → 无孤儿；modal 不关，数据不丢。
3. POST 前校验失败 → 无网络调用；modal 不关。

未来 V1.x 可以加服务端原子端点，一次事务建两者；V1 接受孤儿路径，
因为：
- 竞争窗口是单用户单标签页。
- 用户有干净的恢复路径（删孤儿）。
- 后端已有 `DELETE /positions/{id}` 处理空 position。

### 5.5 `PositionTradesTab.vue`

替换 F3 的 `PositionTradesPlaceholder.vue`。`PositionDetailView.vue` 里
import target 同名 —— 只翻 import 行。

布局：

- **顶部带：**
  - 左：`<n-switch v-model:value="includeArchived">` *"Show archived"* ——
    绑定 `useTrades(positionId).includeArchived`。
  - 右：`+ New trade` 按钮 → 以 standalone 模式开 `TradeEntryModal`。
- **组列表。** 按 `order_group_id` 分组（NULL 组当作单行组）。
  `<n-list>` 一组一条。
  - 组头：pattern badge（`detectPattern(group, instrumentMap)`）；组里
    最早行的 `executed_at`（相对 + tooltip）；行数 >1 时带 count badge。
  - 组行：小内嵌表，列 `action` badge、`instrument` symbol、`quantity`、
    `price`、`cash_flow`、`commission+fees`、操作。
  - 行级操作：
    - **Edit notes** —— `<n-popconfirm>` 风格的内联编辑，仅改 `notes`
      （P9 只允许 `notes` PATCH）。
    - **Archive** —— popconfirm → `useTrades.archive(id)`。
      `includeArchived === true` 时归档行视觉变暗；默认隐藏。
- **空状态** —— `<n-empty>` *"No trades yet on this position."* CTA
  `+ New trade` 打开 modal。

**Pattern badge 渲染。** 小组件 `<TradePatternBadge :badge>` 用不同颜色
渲染四种 pattern：

| Badge        | 颜色    | tooltip 文案 |
|---|---|---|
| `ic-open`    | info    | "Iron Condor opened (4 option legs in one order)" |
| `assignment` | warning | "Assignment: short option closed, stock leg created" |
| `exercise`   | warning | "Exercise: long option closed, stock leg created" |
| `expiration` | default | "Option expired worthless (price=0)" |
| `null`       | （无）  | 无 badge —— 通用组 |

badge 是**按行形态推断的，不是用户声明的**。这意味着用户只录了 3 腿的
iron condor 不会显 `ic-open` —— 那是正确行为（其实它不是 IC）。pattern
识别纯为显示糖。

**删除路径。** F3 commit 历史里保留 `PositionTradesPlaceholder.vue`；
F4 末尾删文件。F4 手动 recipe 验证替换。

### 5.6 `PositionDetailView.vue` 改动

两处修改：

1. 改 import 与组件引用：
   ```ts
   // import PositionTradesPlaceholder from '../components/PositionTradesPlaceholder.vue'
   import PositionTradesTab from '../components/PositionTradesTab.vue'
   ```
   `<template>` 里：
   ```vue
   <n-tab-pane name="trades" tab="Trades">
     <PositionTradesTab :positionId="position.id" />
   </n-tab-pane>
   ```
2. Overview 卡右侧加小 `+ Add trade` 按钮（与 Edit 同行，secondary 类）。
   以 standalone 模式开 `TradeEntryModal`。`@saved` 后：刷
   `usePosition` + （在 Trades tab 时）tab 的 `useTrades`，可以用小事件
   总线，或直接调 `position.refresh()`（页面级 `usePosition` 已会触发
   `net_cash_flow` 重读；tab 的 `useTrades` mount 时也刷）。最干净：
   `PositionDetailView` emit `@trade-saved`，`usePosition` 和 tab 都订阅。

### 5.7 `DashboardView.vue` 更新

把 Trades 占位卡从 disabled 翻活。卡的计数**对 F4 可选** —— 接
`useTradesGlobalCount` 要么需要 `/api/trades?limit=…` 全局调用，要么需要
新端点。V1 阶段卡只贴 `Trades` 标签（不带计数），链接到 `/positions`
（trade 看 in-position）。Dashboard 真正长数字在 F5。

| 卡 | 内容 | 链接 |
|---|---|---|
| Your accounts | 来自 `useAccounts` 的计数 | `/accounts` |
| Instruments | 来自 `useInstruments` 的计数 | `/instruments` |
| Positions | 来自 `usePositions`（status=`open`）的计数 | `/positions` |
| Strategy caps | 来自 `useStrategyConfigs` 的计数 | `/settings/strategies` |
| **Trades** | 仅标签（无计数） | `/positions` |
| Dashboards (Phase F5) | disabled | none |

## 6. Codegen 工作流

F4 不引新后端端点 —— codegen 与 F3 同。如果 F4 期间 P9 有任何补丁落地，
重跑 `npm run codegen` 并 commit。

## 7. 测试策略

- **F4 不写自动化前端测试。** 手动 recipe（§8）是门槛。两个纯 helper
  （`previewCashFlow`、`detectPattern`）是干净的 Vitest 候选，但延后到
  V1.x，除非任一长出非平凡分支（如复杂 pattern lookup）。
- **后端回归** —— 每段 F4 工作后保持绿。
- **F3 回归** —— `PositionFormModal` 的原子流替换 F3 拐杖路径；确认
  `?legacy=true` 被拆除（手动 recipe 第 23 步验证）。
- **`previewCashFlow` ↔ 后端公式一致性约束**
  （[V1 决策 5](./v1-release-plan.zh.md#决策-5--派生值单仓位前端算列表与聚合后端算)）
  靠手动跨核：任何 trade 提交后，对比表单显示的预览 cash_flow 与服务端
  返回的 cash_flow。不一致是回归。

## 8. 手动验证 recipe

前提：后端 P9 部署在 `127.0.0.1:8000`；前端 `localhost:5173`；新建 DB；
Alice 登录；Cash USD 账户 + AAPL stock instrument 已建好（参 F3 §8 第 1-3
步）。

> F3 §8 用 `?legacy=true` 拐杖建 Position；F4 走通过 `TradeEntryModal`
> inline 的真原子路径。`?legacy=true` query string 在 F4 移除。

1. 访 `/positions` → 空。
2. 点 `+ New position` → modal 开。Account = Cash USD、Instrument =
   AAPL、Strategy = Spot Stock、opened_at =（将从首笔 Trade
   `executed_at` 派生；字段仍展示但自动同步 —— 尝试编辑会警告
   "opened_at 派生自首笔 Trade executed_at"）。
3. **首笔 Trade 子区域** —— F4 inline 表单渲染默认 1 行。填行：
   action=buy、quantity=10、price=170.50、executed_at=now → cash_flow
   预览 `-USD 1705.00`（红色，带 "preview" tag）。
4. 提交 → toast "Position and Trade(s) created" → 跳 `/positions/{id}`。
   Overview 显示 `net_cash_flow: -USD 1705.00`；Trades tab 现在用
   `PositionTradesTab`；一行未分组 trade 行可见，无 pattern badge（单
   非 option）。
5. 点 Trades tab `+ New trade` → standalone modal。加一行 buy：
   action=buy、quantity=5、price=172.00、executed_at=now → 预览
   `-USD 860.00` → 提交 → 行数 2；net_cash_flow 更新到 `-USD 2565.00`。
6. **多腿测试（Iron Condor 开仓）。** 再建一个 strategy=Iron Condor 的
   AAPL Position。首笔 Trade 子区域加 4 行：
   - sto AAPL P 170 expiry+30d qty=1 price=2.50
   - bto AAPL P 165 expiry+30d qty=1 price=1.50
   - sto AAPL C 200 expiry+30d qty=1 price=3.00
   - bto AAPL C 205 expiry+30d qty=1 price=2.00
   每个 option 腿：picker 需要 option contract。用 `allowCreate` 现场建
   underlying 没有的 option。提交 → Position + 4 Trades 建好 → 跳详情；
   Trades tab 显示一组 4 行配 **IC-open** badge（info 色）。
7. 验证 `cash_flow` 预览一致：每行预览要与服务端保存后的 cash_flow 完全
   一致（假设 multiplier=100，4 腿分别 `+250.00`、`-150.00`、`+300.00`、
   `-200.00`；合计 `+200.00` 净 credit）。
8. **Expiration pattern。** 在第 6 步的 IC 上再建一组：单 option `btc`
   腿 @ price=0、quantity=1（平仓到期作废的短 put）。新组应显
   **Expiration** badge。
9. **Assignment pattern。** 建一组：
   - stc AAPL P 170 expiry @ price=0、quantity=1
   - buy AAPL @ price=170、quantity=100
   两条同一次提交 → 一组 2 行 → **Assignment** badge（warning 色）。
10. **Exercise pattern。** 镜像：btc AAPL C 200 @ price=0、quantity=1
    + buy AAPL @ price=200、quantity=100 → **Exercise** badge。
11. **Action↔kind 校验。** 在 Spot Stock 仓位 `+ New trade`。挑 stock
    AAPL → `action` 下拉禁用 `bto / sto / btc / stc`（option-only）。
    挑 option AAPL P 170 → `buy / sell` 禁用。
12. **option 仅整数 quantity。** 选 option instrument 时，`quantity` 输入
    `precision=0`、按 1 滚轮。输 `2.5` → blur 后按 `<n-input-number>`
    精度配置归 `2` 或拒绝；后端无论如何对 `2.5` 422 拒绝（验证前后
    一致）。
13. **cash flow 预览 = 服务端 cash flow。** 任何 submit 后打开保存的
    行，对比表单内行的预览与表格 `cash_flow` 列。**精确到分**必须一致。
    不一致即回归（V1 一致性约束）。
14. **归档一条 trade。** Trades tab → 行 → Archive → popconfirm 确认 →
    行从默认视图消失。开 "Show archived" → 行变暗回来。
    `position.net_cash_flow` 应按归档行的 cash_flow 减少（按 P12
    archived-trade 排除）。Overview 派生卡刷新后更新。
15. **仅编辑 notes。** Trade 行 "Edit notes" → 当前 notes 内联编辑器 →
    改为 "broker assigned manually" → 保存 → notes 更新。试着用 curl
    PATCH 其他字段：后端按 P9 不变性返回 422。
16. **软删 trade 不可改。** 归档一条 trade。开 Show archived 后再点
    "Edit notes"：行应禁用该操作 —— 归档 trade 前端只读（后端允许，
    但前端选择）。Unarchive 通过新的 "Unarchive" 操作或联系支持 ——
    V1 简化为：重录。
17. **关仓后。** 详情 → Close → 确认。`pnl_realized` 冻结 = 关仓时的
    `net_cash_flow`。之后归档该 closed 仓位的 trade 应**不**改冻结
    `pnl_realized`（P9 审计不变性）；验证：归档已平仓位的 trade，
    详情显示 `pnl_realized` 不变。
18. **DashboardView 回归。** 访 `/` → Trades 卡可见（无计数），链接到
    `/positions`。Positions 卡显示更新后的 open-position 计数。
19. **原子流失败恢复。** 模拟：试图提交一个首笔 Trade `instrument_id`
    为随机 UUID 的 Position（手改 DOM 状态）。Position POST 成功 →
    Trade POST 422 → toast 浮出孤儿 position id 与恢复提示 → 去
    `/positions` 看到孤儿 → 删除（无 trade 挂着，409 不会触发）。
20. **多行原子。** 提交 4 腿的 Custom multi-leg Position，但第 3 腿数据
    无效。提交**不应**先 POST 3 腿再跳过第 4 腿 —— 后端按 P9 原子语义
    拒绝整数组。前端 toast 浮校验错误；同时 Position **不**会被建（我们
    先 POST Position；服务端校验在 Trade POST 时；这里 Trade POST 失败，
    Position 已建）。验证：列表无新 Position（孤儿路径只在 Position POST
    成功但 Trade POST 失败时跑；本场景 Trade POST 在 array 上失败，所以
    孤儿存在 —— 仍留给用户删除）。文档记为正常行为；未来 V1.x 考虑
    rollback。
21. **F3 拐杖已除。** 访 `/positions/new?legacy=true`（F3 query 字符串）
    → 行为与 `/positions/new` 完全相同（即**没有**拐杖路径）。表单强制
    要求 First Trade。
22. **F3 回归 —— Plan / Meta 仍工作。** 详情 Plan tab → append 一个修订
    （如 F3 §8 第 10 步）。功能不变。Meta tab → wheel 仓位创建 wheel
    meta。功能不变。
23. 后端日志：无 500、无 IntegrityError。所有步骤后 `pytest -q` 仍绿。

## 9. F4 之后

F4 落地后，下一迭代是
[F5 — Dashboard](./frontend-expansion-plan.zh.md#f5--dashboards--charts)，
消费后端 P12.2（`GET /api/dashboard/summary`）。F5 会：

- 构建 `src/api/dashboard.ts` 包装 P12.2 端点。
- 重做 `/dashboard`：per-currency PnL 卡、open + closed 仓位表、`vue-echarts`
  画的按月 PnL 图
  （[V1 决策 3](./v1-release-plan.zh.md#决策-3--图表vue-echarts)）。
- 复用 F3 §9 的 `src/utils/positionDerived.ts` 做 open-positions 表的逐行
  派生展示（按 V1 决策 5 的一致性约束）。

F6（Docker）在 F5 之后。

F4 期间种下的 V1.x 候选：

- **Vitest** 给 `previewCashFlow` 和 `detectPattern`，任一长出分支时。
- **Named-flow helper**（Expire / Assignment / Exercise / IC-open 模板）
  —— 在 Custom multi-leg 上叠加，不破坏现有数据。
- **服务端原子 Position+Trade 端点** —— 消除孤儿 Position 恢复路径；
  干净的 V1.x cleanup。
- **Trade 就地编辑** —— `notes` 之外 —— 需要改 P9 不变性约束；需要
  `Trade.archived_at` 审计故事。

---

## 变更日志

- **v0.1（2026-05-28）** —— F4 plan 初版。V1 release plan §4 决策 2 的 TBD
  （"V1 的 named-flow 短名单 —— 由 F4 detail plan 定"）在此 settle：
  **V1 零 named flows；Custom multi-leg 是唯一录入模式。** 理由：出货
  最小面、显示侧仍有 pattern badge、helper 是叠加性 V1.x 工作。
  Plan 覆盖：`src/api/trades.ts`（替换 F3 内联类型）、`useTrades`
  composable、`TradeEntryModal` 双模式（standalone 给 Position 详情录入、
  inline 给 `PositionFormModal` 的 Trade-led 原子 Position+Trade 流）、
  `PositionTradesTab` 替换 F3 占位附带 pattern-badge 分组 + 软删 UX、
  两个纯 helper（`previewCashFlow`、`detectPattern`）。原子 Position+Trade
  失败恢复路径（孤儿 Position + 重试提示）已记录但标为 V1.x 服务端原子
  端点候选。F3 的 `?legacy=true` 拐杖已移除。
