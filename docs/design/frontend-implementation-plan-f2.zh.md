# Frontend Phase F2 — Instrument 与 StrategyConfig 前端

**语言：** [English](./frontend-implementation-plan-f2.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-24）。配套文档：
> [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md)（宏观路线图）、
> [frontend-implementation-plan-f1.zh.md](./frontend-implementation-plan-f1.zh.md)（F1
> 模式参考）、[data-model.zh.md](./data-model.zh.md)，以及后端 plans
> [backend-expansion-plan-p6.zh.md](./backend-expansion-plan-p6.zh.md)（P6，已完成）+
> [backend-expansion-plan.zh.md §P7](./backend-expansion-plan.zh.md#p7--strategyconfig)
> （P7，预计为下一步）。先在此迭代再写代码。

## 1. 目的

F2 建立在后端 **P6**（Instrument CRUD，✅ 已完成）和 **P7**（StrategyConfig CRUD，
预计下一步）之上。交付：

- 一个可浏览的 instrument catalog 页面 `/instruments`（用户能列出、过滤、搜索、
  创建 stock/option/forex 三类 instrument）。
- 一个可复用的 `InstrumentPicker` typeahead 组件 — **对 F3 Position 创建与 F4
  Trade 创建均为承重组件**。
- 一个策略曝光上限设置页 `/settings/strategies`（用户级；MVP 之后接入券商 API
  时强制执行）。

这是同时完成 P6 与 P7 的最小连贯 UI 迭代 — 它们各自都撑不起一个独立 F-phase，
但合在一起就是"用户在开 Position 之前接触的全部界面"。

F2 完全建在 F1 模式之上（codegen → 资源 API 模块 → composable → form modal →
view + AuthenticatedLayout slot）。没有引入根本性的新模式。

> **执行说明。** 本规划假设 P7 的 API shape 与
> [backend-expansion-plan.zh.md §P7](./backend-expansion-plan.zh.md#p7--strategyconfig)
> 一致（`POST /strategy-configs`、`GET`、`PATCH /{strategy_type}`）。P7 落地后
> 请对照实际 OpenAPI 文档校验；相应调整 `src/api/strategyConfigs.ts`。

## 2. 范围

### 在范围内（本规划）

- **`src/api/instruments.ts`** — 对 3 个 P6 端点（`list`、`get`、`create`）的
  typed 封装，把 200-vs-201 的区分返还给调用方，方便显示 "Selected existing" vs
  "Created" 提示。
- **`useInstruments()` composable** — 列表状态，支持 `kind` + `q` 过滤与防抖
  自动刷新。
- **`InstrumentForm.vue`** — 按 kind 判别的创建 modal，覆盖 stock / option /
  forex 三类（按
  [P6 schemas](./backend-expansion-plan-p6.zh.md#4-schema-shapes-target)）。
- **`InstrumentPicker.vue`** — 绑定到 `useInstruments` 的可复用 typeahead select，
  可选 `kind` 约束。**F2 内仅 select-only** — 当 F3 Position 创建需要时再加 inline-
  create。
- **`InstrumentsView.vue`**（`/instruments`） — 含 kind 过滤 + symbol 搜索 + 行
  点击展开（显示 option/forex 扩展块）+ "+ New instrument" 按钮的列表页。
- **`src/api/strategyConfigs.ts`** — P7 的 typed 封装（具体形态待 P7 落地确认）。
- **`useStrategyConfigs()` composable** — 列表状态 + `upsert(payload)`。
- **`SettingsStrategiesView.vue`**（`/settings/strategies`） — 表格按
  `strategy_type` 一行（5 行：`wheel`、`iron_condor`、`pmcc`、`spot_stock`、
  `spot_forex`），inline 编辑 `max_exposure` + `exposure_currency` + `notes`。
- **`AuthenticatedLayout.vue`** — header nav 增加 `Instruments` 与 `Settings`。
- **`DashboardView.vue`** — 占位卡片更新：新增 "Instruments" 与 "Strategy caps"
  卡片；"Positions / Trades / Dashboards" 占位推迟到 F3/F4/F5。
- **codegen** — P6（已完成）与 P7 落地**各跑一次** `npm run codegen`；提交重新
  生成的 `schema.d.ts`。
- **后端回归** — 保持 ≥92 后端测试 + N P7 测试通过；ruff + mypy strict 干净。
- **CI codegen gate（横向，可选打包）** — 见
  [扩展规划 §5](./frontend-expansion-plan.zh.md#5-cross-cutting--deferred-deliverables-tracked)。

### 明确不在范围内（推迟）

- **`InstrumentPicker` 的 inline-create** — 推迟到 F3（自然时机是 Position 创建
  流程需要"输入新 symbol → 创建并选中"且不离开表单时）。
- **外部 instrument lookup**（[P6.x](./backend-expansion-plan.zh.md#p6x--external-instrument-validation-first-external-api-integration-optional-non-blocking)）
  — 独立推迟；准备好后作为对 picker 的小增强落地。
- **Position UI / Trade UI / Dashboards / Docker** — F3 / F4 / F5 / F6。
- **Instrument 的 PATCH/DELETE UI** — 后端无 instrument PATCH/DELETE（全局共享，
  被其他人的 position 引用）；UI 对齐。
- **Instrument 或 strategy config 的 Pinia store** — 与 F1 一样使用页面局部
  composable；只有 ≥2 个组件需要共享响应式时再升级为 store。
- 两种资源上的**批量操作**。
- `/instruments` 的**分页** — 后端 `limit=200` 已够 MVP 规模。
- **前端单元测试（Vitest）** — 仍无值得测的逻辑；后端 pytest + `vue-tsc` + 手动
  点击足够。

## 3. 技术新增

**无。** 与 F1 同栈。

若 typeahead 搜索需要防抖，inline 写一个 10 行的 `useDebouncedRef` 即可，无需引入
`@vueuse/core` — 保持运行时依赖最少。

## 4. 目录结构变更

```
frontend/src/
├── api/
│   ├── schema.d.ts                  ← P6（已完成）+ P7 后重新生成
│   ├── instruments.ts               ← NEW
│   ├── strategyConfigs.ts           ← NEW
│   ├── accounts.ts                  ← 不变
│   ├── http.ts                      ← 不变
│   └── types.ts                     ← 不变
├── composables/
│   ├── useAccounts.ts               ← 不变
│   ├── useInstruments.ts            ← NEW
│   └── useStrategyConfigs.ts        ← NEW
├── components/
│   ├── AuthenticatedLayout.vue      ← 改：增加 Instruments + Settings 导航
│   ├── AccountFormModal.vue         ← 不变
│   ├── InstrumentForm.vue           ← NEW
│   └── InstrumentPicker.vue         ← NEW
├── router/
│   └── index.ts                     ← 改：增加 /instruments + /settings/strategies 路由
└── views/
    ├── LoginView.vue                ← 不变
    ├── RegisterView.vue             ← 不变
    ├── DashboardView.vue            ← 改：占位卡片更新
    ├── AccountsView.vue             ← 不变
    ├── InstrumentsView.vue          ← NEW
    └── SettingsStrategiesView.vue   ← NEW
```

## 5. 构建交付物

agent / 实现者可自行排序；唯一硬顺序是 **`schema.d.ts` 重新生成 → API 客户端 →
composable → 组件 → 视图 → 导航接线**。下面是建议顺序，保证每段后
`npm run build` 仍绿。

### 5.1 API 客户端

**`src/api/instruments.ts`** — 对 3 个 P6 端点的 typed 封装。

```ts
import type { components } from './schema'
import { http } from './http'

export type Instrument        = components['schemas']['InstrumentRead']
export type StockCreate       = components['schemas']['StockCreate']
export type OptionCreate      = components['schemas']['OptionCreate']
export type ForexCreate       = components['schemas']['ForexCreate']
export type InstrumentCreate  = StockCreate | OptionCreate | ForexCreate
export type InstrumentKind    = components['schemas']['InstrumentKind']

export interface InstrumentCreateResult {
  instrument: Instrument
  existed: boolean   // 后端返回 200（catalog 已有）则为 true
}

export const instrumentsApi = {
  list:   (params?: { kind?: InstrumentKind; q?: string; limit?: number }) =>
            http.get(`/instruments${buildQuery(params)}`) as Promise<Instrument[]>,
  get:    (id: string) => http.get(`/instruments/${id}`) as Promise<Instrument>,
  create: async (payload: InstrumentCreate): Promise<InstrumentCreateResult> => {
    const { data, status } = await http.postWithStatus('/instruments', payload)
    return { instrument: data as Instrument, existed: status === 200 }
  },
}
```

`http.ts` 若尚未暴露状态码，加一个 `postWithStatus` 辅助（当前 `http.post` 可能
只返回 parsed body — 扩展或封装一下）。

**`src/api/strategyConfigs.ts`** — P7 typed 封装。

```ts
import type { components } from './schema'
import { http } from './http'

export type StrategyConfig       = components['schemas']['StrategyConfigRead']
export type StrategyConfigCreate = components['schemas']['StrategyConfigCreate']
export type StrategyConfigUpdate = components['schemas']['StrategyConfigUpdate']
export type StrategyType         = components['schemas']['StrategyType']

export const strategyConfigsApi = {
  list:   ()                                        => http.get('/strategy-configs') as Promise<StrategyConfig[]>,
  get:    (type: StrategyType)                      => http.get(`/strategy-configs/${type}`) as Promise<StrategyConfig>,
  upsert: (payload: StrategyConfigCreate)           => http.post('/strategy-configs', payload) as Promise<StrategyConfig>,
  update: (type: StrategyType, payload: StrategyConfigUpdate) =>
                                                       http.patch(`/strategy-configs/${type}`, payload) as Promise<StrategyConfig>,
  remove: (type: StrategyType)                      => http.delete(`/strategy-configs/${type}`) as Promise<null>,
}
```

P7 落地后对照其 `schema.d.ts` 校验端点形态。

### 5.2 Composables

**`useInstruments()`** — 与 `useAccounts` 同形。状态：`instruments`、`loading`、
`error`、`kindFilter`、`query`。监听两个过滤器；对 `query` 变更防抖（300 ms）；
watcher 触发后调 `refresh()`。暴露 `refresh()` 供显式重取（创建后）。

**`useStrategyConfigs()`** — `configs`、`loading`、`error`、`refresh()`、
`upsert(payload)`（调 `strategyConfigsApi.upsert`，然后 `refresh()`）。

### 5.3 `InstrumentForm.vue`（创建 modal）

单个 modal，顶部有 kind 选择器（`<n-segmented>` 或 `<n-radio-group>`：Stock /
Option / Forex）。表单字段按 kind 条件显示，对应
[P6 schemas](./backend-expansion-plan-p6.zh.md#4-schema-shapes-target)：

- **stock**：`symbol`（必填，最长 64）、`exchange`（可选，最长 64）、`currency`
  （必填，`^[A-Z]{3}$`）。
- **option**：`underlying_symbol`（必填）、`underlying_exchange`（可选）、
  `currency`（必填 `^[A-Z]{3}$`）、`opt_type`（call / put）、`strike`（decimal >
  0）、`expiry`（`<n-date-picker>`）、`multiplier`（int > 0，默认 100）、
  `style`（american / european，默认 american）。
- **forex**：`symbol`（如 `EURUSD`）、`base_currency`（`^[A-Z]{3}$`）、
  `quote_currency`（`^[A-Z]{3}$`）、`pip_size`（decimal > 0）、
  `contract_size`（可选 decimal > 0）。**无 `currency` 字段 — 后端从
  `quote_currency` 派生。**

校验：与 F1 同（提交时通过 `formRef.value?.validate()`）。

提交处理：

```ts
const { instrument, existed } = await instrumentsApi.create(payload)
if (existed) message.info(`Instrument ${instrument.symbol} already exists — selected`)
else        message.success(`Created ${instrument.symbol}`)
emit('saved', instrument)
```

Props：`:show`（v-model），无 `mode`（永远创建 — instruments 无 edit 契约）。
Emits：`@saved` 带 `Instrument`。

### 5.4 `InstrumentPicker.vue`（可复用 typeahead）

```vue
<script setup lang="ts">
defineProps<{
  modelValue: string | null     // 选中的 instrument UUID
  kind?: InstrumentKind          // 限制 picker 到一个 kind
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: string | null): void
}>()
</script>
```

内部：`<n-select remote filterable :options :loading>` 绑到本地的
`useInstruments()` 实例，把 `kind` 过滤透传。用户输入时防抖（300 ms）取数。选项
渲染为 `symbol` + 小 `kind` badge + `exchange?` 后缀。

**F2 内仅 select-only。** 尚无 `allowCreate` prop；F3 在 Position 创建需要时加。

**F2 内的手动验证**（无生产消费者）：
- 临时在 `DashboardView` 上以小卡片 "(debug, removed in F3)" 引入并渲染
  `<InstrumentPicker v-model="debugId" />`。确认 typeahead + 选择行为正常。提交
  前可移除 debug 实例；至少组件必须能编译（`npm run build` 下的 `vue-tsc`）。
- 或者：在 `InstrumentsView` 上把它用作搜索输入（替代普通 `<n-input>` 过滤）。
  更干净，并在已有界面里验证 picker。

### 5.5 `InstrumentsView.vue`（`/instruments`）

布局（在 `<AuthenticatedLayout>` 内）：

- **页头** — 标题 "Instruments"，右对齐 "+ New instrument" 按钮（打开
  `InstrumentForm` 创建模式）。
- **过滤条** — `<n-select>` 选 kind（All / Stock / Option / Forex），绑到
  `useInstruments().kindFilter`；**`InstrumentPicker`**（或普通的
  `<n-input placeholder="Search by symbol">`）绑到 `useInstruments().query`。
  *建议：在此用 `InstrumentPicker` 作搜索 widget，给 F2 一个真实消费者。*
- **`<n-data-table>`** — 列：kind badge、symbol、exchange、currency、created_at。
- **行点击 → 展开**显示该行 kind 的扩展块：
  - `option`：`opt_type`、`strike`、`expiry`、`multiplier`、`style`（渲染为小型
    键值网格）。
  - `forex`：`base_currency`、`quote_currency`、`pip_size`、`contract_size`。
  - `stock`：无额外字段（基础字段已在行内）。
- **空状态** — `<n-empty>` "No instruments yet — create one to get started"，
  按钮同样打开表单。
- **无 actions 列** — 后端无 PATCH/DELETE。

`InstrumentForm @saved` 后：调 `refresh()` 并关闭 modal。

### 5.6 `SettingsStrategiesView.vue`（`/settings/strategies`）

布局：

- **页头** — 标题 "Strategy exposure caps"，简短帮助说明："给每个策略设一个
  `max_risk_at_open` 总上限。MVP 内仅人工记录 — 接入券商 API 后会在下单时强制
  执行。"
- **`<n-data-table>`** — 按已知 `strategy_type` 一行（5 行，顺序：`wheel`、
  `iron_condor`、`pmcc`、`spot_stock`、`spot_forex`）。从 `schema.d.ts` 读 enum
  值，避免手工维护清单。列：策略标签、max_exposure、exposure_currency、notes、
  updated_at、actions。
- **行数据** — 合并默认（空上限）行与 `useStrategyConfigs()` 返回的已保存配置。
  无配置的行 cap 列显示 "—"，有 "Edit" 操作打开预填 strategy_type 的编辑 modal。
- **小 modal inline 编辑** — `StrategyConfigForm` 风格字段（`max_exposure`
  decimal、`exposure_currency` `^[A-Z]{3}$`、`notes` textarea）；提交调
  `useStrategyConfigs().upsert(payload)`；成功/失败 toast 同 F1。

（如果 P7 落地的 API 形态与 §1 假设差距较大，相应调整表单 payload。视图结构应
不受影响。）

### 5.7 `AuthenticatedLayout.vue` + `DashboardView.vue` 更新

**`AuthenticatedLayout.vue`** — 在 Accounts 与右侧 email/logout 之间增加两个
导航项：

```
Dashboard | Accounts | Instruments | Settings
```

F2 内 `Settings` 可以是直接指向 `/settings/strategies` 的链接（设置页面只有这
一个）。后续 settings 多了再升级为下拉菜单。

**`DashboardView.vue`** — 更新占位卡片。新的 `<n-grid :cols="3">`：

| 卡片 | 内容 | 链接 |
|---|---|---|
| Your accounts | `useAccounts` 计数 | `/accounts` |
| Instruments | `useInstruments` 计数 | `/instruments` |
| Strategy caps | "5 strategies tracked" 或 `useStrategyConfigs` 计数 | `/settings/strategies` |
| Positions (Phase F3) | disabled / depth=3 | 无 |
| Trades (Phase F4) | disabled / depth=3 | 无 |
| Dashboards (Phase F5) | disabled / depth=3 | 无 |

## 6. Codegen 工作流

与 [F1 §6](./frontend-implementation-plan-f1.zh.md#6-codegen-workflow) 同操作。

F2 特别提醒：
- `npm run codegen` 必须在 **P6 落地后跑一次**（P6 内已跑 — 见
  [P6 提交历史](./backend-expansion-plan-p6.zh.md)）**和 P7 落地后跑一次**。
- P7 跑完后的 git diff 应该很小（一个 `StrategyConfigRead`、
  `StrategyConfigCreate`、`StrategyConfigUpdate`、`StrategyType` enum，加上
  3–5 条路径条目）。
- 如果 CI codegen gate（横向）随 F2 落地，F2 之后第一个改后端 schema 的 PR 就
  是 gate 第一次触发的时刻。

## 7. 测试方式

与 F0 / F1 同 — **F2 不引入自动化前端测试**。后端 pytest 是回归 gate。
`npm run build`（`vue-tsc`）类型检查前端。

后端回归仍是硬 gate。F2 每段工作后必须保持绿。

## 8. 手动验证 recipe

F2 全部界面建好后，在 `uvicorn` + `npm run dev` 下端到端走。前置：后端
`127.0.0.1:8000` **同时部署并迁移 P6 与 P7**；前端 `localhost:5173`；SSH 隧道
转发两个端口；空库。

1. 注册 `alice@example.com` / `correct horse battery` → 落到 `/` →
   Dashboard 显示 6 卡片（Your accounts、Instruments、Strategy caps、
   Positions [F3] disabled、Trades [F4] disabled、Dashboards [F5] disabled），
   计数全为 0。
2. 顶部导航显示：Dashboard | Accounts | Instruments | Settings。
3. 点 "Instruments" → `/instruments`；显示空状态。
4. 点 "+ New instrument"：
   - 默认 tab "Stock"。填 `aapl` / `NASDAQ` / `USD` → 提交 → toast
     "Created AAPL"（symbol 被后端自动大写）；行出现。
   - 再点一次，切到 "Option"。填 underlying `AAPL` / exchange `NASDAQ` /
     currency `USD` / put / strike `220` / expiry `2026-05-28` → 提交 → toast
     "Created AAPL"（或 "Created option"）；新 option 行出现。
   - 点 option 行 → 展开显示 opt_type、strike、expiry、multiplier=100、
     style=american。
   - 再点一次，切到 "Forex"。填 `EURUSD` / EUR / USD / pip_size `0.0001` →
     提交 → "Created EURUSD"；行的 currency 列显示 `USD`（从 quote 派生）。
5. 点 "+ New instrument" → Stock tab，再填 `AAPL` / `NASDAQ` / `USD` →
   提交 → toast "Instrument AAPL already exists — selected"（200 来自
   get-or-create）；行数不变。
6. 过滤条：选 kind = Option → 只剩 AAPL put 行；清除 → 3 行全显示。
7. 搜索框：输入 `aa` → 2 行（AAPL stock + AAPL option），后端前缀搜索；
   清除 → 3 行。
8. 顶部 → Settings → `/settings/strategies`。见 5 行（wheel、iron_condor、
   pmcc、spot_stock、spot_forex），cap 全显示 "—"。
9. 点 `iron_condor` 的 Edit：设 max_exposure `3000`、exposure_currency
   `USD`、notes "MVP cap" → 保存 → 行更新；updated_at 出现。
10. 刷新 `/settings/strategies` → cap 持久。
11. 再编辑 `iron_condor`，清空 notes → 保存 → notes 列变空，updated_at 前进。
12. 顶部 → Dashboard → Strategy caps 卡链接可用；Instruments 卡显示计数 3
    （或实际创建数）；Your accounts 卡仍为 0。
13. 全程后端日志：只见预期请求；无 500，无 IntegrityError。
14. （跨用户，可选）注册 `bob@example.com`，登录 bob，访问 `/instruments` →
    见同样 3 行（instruments 是**全局的**，
    [P6 已 settle](./backend-expansion-plan.zh.md#6-open-design-decisions)）。
    `/settings/strategies` → 空（配置是用户级的）。
15. （可选合理性）DB 检查：
    ```bash
    sqlite3 backend/dev.db "SELECT kind, symbol FROM instruments ORDER BY symbol"
    # 预期：AAPL stock、AAPL option、EURUSD forex
    sqlite3 backend/dev.db "SELECT strategy_type, max_exposure FROM strategy_configs WHERE user_id IN (SELECT id FROM users WHERE email='alice@example.com')"
    # 预期：iron_condor | 3000.0000
    ```

## 9. F2 之后

F2 落地后，下一轮是
[F3 — Position CRUD + 详情页](./frontend-expansion-plan.zh.md#f3--position-crud--detail-page-with-strategy-meta-tabs--plan-tab)，
消费后端 P8 + P10 + P11。F3 会：

- 给 `InstrumentPicker` 加 `allowCreate`，让 Position 创建可在不离开表单的情况
  下 inline 创建底层 instrument。
- 用 picker 选 `primary_instrument_id` 构建 `PositionFormModal`。
- 构建 `PositionDetailView`，含 Overview / Meta / Plan tab 条；Trades tab 在
  F4 前是占位。
- 加 wheel/PMCC strategy-meta 子表单（按 `strategy_type` 条件渲染）。
- 加 TradePlan revision 追加表单 + 历史表。

如果 CI codegen gate 未随 F2 一起落地，作为 F3 的第一项任务落地。

---

## Changelog

- **v0.1（2026-05-24）** — v0.2 扩展规划重切下的首份 F2 plan。覆盖 P6（已完成）
  + P7（下一步） — Instrument 浏览 + 可复用 picker + 策略曝光上限设置页，加上
  导航 + dashboard 更新。Picker 的 inline-create 明确推迟到 F3。无新依赖；无
  内部子 phase。
