# 前端扩展规划 — 横向 UI（Phase F2+）

**语言：** [English](./frontend-expansion-plan.md) | 中文

> 状态：**DRAFT v0.2**（2026-05-24）。F0（认证脚手架）和 F1（Account CRUD UI）
> 之后的前端扩展宏观路线图。与
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md)（Phase P6+）配套，
> 把每个 F-phase 折合到**一小批连续的后端 phase**上，使每个 F-phase 都能被独立
> 端到端执行（"一把梭"）。配套文档：
> [data-model.zh.md](./data-model.zh.md)、
> [mvp-implementation-plan.zh.md](./mvp-implementation-plan.zh.md)、
> [frontend-implementation-plan.zh.md](./frontend-implementation-plan.zh.md)（F0 详细）、
> [frontend-implementation-plan-f1.zh.md](./frontend-implementation-plan-f1.zh.md)（F1 详细）、
> [frontend-implementation-plan-f2.zh.md](./frontend-implementation-plan-f2.zh.md)
> （F2 详细 — 本次重订下的首份）。各 F-phase 的详细文档以
> `frontend-implementation-plan-fN.zh.md` 形式落地（每 phase 一份）。
>
> **V1 release plan：** 本路线图中属于 V1 范围的切片整合在
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星文档）。V1 范围或
> 横切决策变更时，本宏观文档与 V1 plan 应在同一次变更里一起更新。

## 1. 当前状态

前端 F0（认证脚手架）、F1（Account CRUD UI）、F2（Instrument + StrategyConfig UI）
均已在 `refactoring/rebuild` 上交付。**后端达到 V1 完整切片** —— P6 到 P12 全部
出货（后端 406 条测试全绿；`ruff` + `mypy --strict` clean）；详见
[backend-expansion-plan.zh.md §4](./backend-expansion-plan.zh.md#4-phase-roadmap)。
剩余 V1 工作**全部在前端**：F3 → F4 → F5 → F6。

**顺序决策（v0.2 修订）：** 后端先行，前端在同迭代跟上 — **但 F-phase 粒度已
粗化**，每个 F-phase 配对*一小批连续后端 phase*，作为一次原子 UI 迭代交付。
结果：每个 F-phase 文档都是一份 agent 能端到端跑完的自包含规划。v0.1 中的子 phase
方案（F2.1、F2.2…）废弃。

为什么修订：F1 的模式（codegen、AuthenticatedLayout、资源 API 模块、composable、
modal 表单、确认对话框）每加一个实体的边际成本已经很低，而底层一些后端模块
（如 Instrument + StrategyConfig）单独并不撑起一个完整页面 — 打包成一个 F-phase
比微步式切分更连贯。

## 2. 指导原则

- **沿用 F1 的模式。** 大多数新实体就是 F1 配方换个资源。
- **codegen 是 API 契约。** 每次后端 schema 变动后用 `openapi-typescript` 重新生成
  `src/api/schema.d.ts`；OpenAPI 文档中已有的实体不手写类型。
- **每个 F-phase 是一次原子迭代。** 规模刚好让 agent（或专注的人类会话）能端到端
  跑完文档、交付并验证。不设内部子 phase。
- **复用组件优于复制页面。** F2 的 `InstrumentPicker` 被 F3（Position 创建）和
  F4（Trade 创建）共用 — 不为每个页面重新实现 typeahead。
- **F5 之前不引图表库。** F2/F3/F4 只有表单 + 表格；Naive UI 单独够用。ECharts
  （或替代品）在 F5 dashboards 引入。
- **手动点击是测试，直到出现值得测的逻辑。** 与
  [F0 §7](./frontend-implementation-plan.zh.md#7-testing-architecture) /
  [F1 §7](./frontend-implementation-plan-f1.zh.md#7-testing-approach) 同理。
  Vitest + Playwright 后续再上 — 见 §5。

## 3. Backend ↔ Frontend 映射

| F-phase | 后端 gate | UI 交付 | 状态 |
|---|---|---|---|
| **F2** | [P6](./backend-expansion-plan.zh.md#p6--instrument-base--extensions) ✅ + [P7](./backend-expansion-plan.zh.md#p7--strategyconfig) ✅ | `InstrumentPicker` 组件 + `/instruments` 浏览页 + `/settings/strategies` 页 | ✅ 已完成（2026-05-26） |
| **F3** | [P8](./backend-expansion-plan.zh.md#p8--position) ✅ + [P10](./backend-expansion-plan.zh.md#p10--strategy-meta-extensions) ✅ + [P11](./backend-expansion-plan.zh.md#p11--tradeplan-event-stream) ✅ + [P12.1](./backend-expansion-plan.zh.md#p12--derived-read-layer) ✅（列表上的 `net_cash_flow`） | Position 列表 + 创建/编辑 + 详情页（含 strategy-meta tabs 与 Plan tab） | ⏳ 下一步（gate 已就绪） |
| **F4** | [P9](./backend-expansion-plan.zh.md#p9--trade) ✅ | Trade 录入（多腿 `order_group_id` UX）+ Position 详情 trade log | —（gate 已就绪） |
| **F5** | [P12.2](./backend-expansion-plan.zh.md#p12--derived-read-layer) ✅（`/api/dashboard/summary`） | Dashboards：分币种 PnL + 开仓/平仓表 + 按月 PnL 图 | —（gate 已就绪） |
| **F6** | [后端 Phase 5](./mvp-implementation-plan.zh.md#phase-5--docker-single-container-deployment) | 单容器 Docker 生产构建接线（FastAPI 托管 `frontend/dist`） | — |

[P6.x — 外部 Instrument 验证](./backend-expansion-plan.zh.md#p6x--external-instrument-validation-first-external-api-integration-optional-non-blocking)
**推迟、非阻塞**；落地时作为小增强滑入 F2（typeahead 自动补全 + "did you mean
AAPL?"）。不影响 F-phase 顺序。

执行节奏：`P6→P7→F2 / P8→P10→P11→F3 / P9→F4 / P12→F5 / Phase 5→F6`。

## 4. Phase 路线图

每个 F-phase 各有一份 `frontend-implementation-plan-fN.zh.md` 详细文档。下面是范围
摘要。

### F2 — Instrument 与 StrategyConfig 前端 ✅ 已完成（2026-05-26）

**详细 plan：** [frontend-implementation-plan-f2.md](./frontend-implementation-plan-f2.md)
（+ [中文](./frontend-implementation-plan-f2.zh.md)）。

**目标。** 端到端覆盖两个后端资源 — 它们各自撑不起一个独立招牌页面，但对下游
所有 F-phase 都是承重的：共享的全局 Instrument 字典，以及用户级策略曝光上限。

**头号交付物。**
- `src/api/instruments.ts` + `useInstruments` + `InstrumentForm`（创建 modal）+
  `InstrumentPicker`（可复用 typeahead）+ `InstrumentsView`（`/instruments`
  浏览页）。
- `src/api/strategyConfigs.ts` + `useStrategyConfigs` + `SettingsStrategiesView`
  （`/settings/strategies` 页）。
- `AuthenticatedLayout` 新增 `Instruments` 和 `Settings` 导航项；`DashboardView`
  占位卡片更新。

**为什么这是合适的"一口"。** `InstrumentPicker` 对 F3 + F4 是承重的 — Position
和 Trade 页面消费它前必须稳。`/instruments` 浏览页本身规模不大，但给 picker 提供
了第一个真实消费者（同时充当 catalog 管理面，因为 instruments 无 PATCH/DELETE 后端）。
StrategyConfig 对其他 phase 顺序灵活且很小；并入这里能让 F3 专注于 Position。

### F3 — Position CRUD + 详情页（含 strategy-meta tabs + Plan tab）

**目标。** 用户的主工作区 — 列表、创建、编辑、归档 Position；打开详情页查看/编辑
策略相关 snapshot 与交易计划。

**头号交付物。**
- `/positions` 列表视图（按 `strategy_type` 与 `status` 过滤）+ 创建/编辑 modal，
  通过 F2 的 `InstrumentPicker` 选 `primary_instrument_id`。
- Position 详情页含 tab 条：**Overview**（汇总卡片 + `max_risk_at_open` 等）/
  **Meta**（按 `strategy_type` 条件显示：wheel funding/loan/interest 或 PMCC LEAP
  picker）/ **Plan**（追加 revision + 历史表，主要服务 forex）/ **Trades**（F4
  之前是占位）。
- 归档流程同 F1；具体取决于
  [§6② 决策](./backend-expansion-plan.zh.md#6-open-design-decisions)。

**开放依赖。** `Position.currency` 按
[data-model §6](./data-model.zh.md#currency-placement) 从
`primary_instrument.currency` 派生；表单以只读 badge 展示。

### F4 — Trade 录入

**目标。** journal 的数据录入主力。多腿 `order_group_id` UX 是设计核心 — 见 §6②。

**头号交付物。**
- `TradeEntryModal` — 按 `action`（`buy` / `sell` / `bto` / `sto` / `btc` /
  `stc`）判别；字段对应
  [data-model §4.5](./data-model.zh.md#45-trade-atomic-event)。
- 多腿 helper 流程，覆盖
  [data-model §4.5.2](./data-model.zh.md#452-notion-event--atomic-trade-mapping)
  中的合成事件：开 iron condor（4 行）、assignment（2 行）、exercise（2 行）、
  expire（1 行）。
- Position 详情页 **Trades** tab — 时间序列列表按 `order_group_id` 视觉分组，
  按模式打 badge（Assignment / Exercise / IC-open / Expire）。
- `src/api/trades.ts` 接受单条 payload 或数组（原子提交一组）。

**验收。** 通过 UI 能录入
[data-model §4.5.2](./data-model.zh.md#452-notion-event--atomic-trade-mapping) 全部
12 种流程，无需 curl。

### F5 — Dashboards 与图表

**目标。** 让 journal 真正有用的数字终于显示出来。

**头号交付物。**
- `/dashboard` 重写：分币种 PnL 汇总卡（MVP 不做 FX 换算，按
  [data-model §6](./data-model.zh.md#currency-placement)）+ 开仓 position 表 +
  平仓 position 历史表。
- 第一个图：分币种月度已实现 PnL 柱状图。图表库在此引入 — 见 §6③。
- `src/api/stats.ts`（或 `derived.ts`）封装 P12 端点。

### F6 — 单容器 Docker 生产接线

**目标。** 可部署交付物。

**头号交付物。**
- 多阶段 Dockerfile：builder 阶段跑 `npm run build`；runtime 阶段把
  `frontend/dist/` 拷进 FastAPI 镜像。
- `main.py` 增加 `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`，
  SPA 回退让客户端路由路径返回 `index.html`（API 路径继续在 `/api/*` 下）。
- 冒烟测试 recipe：起容器 + 通过端口映射隧道从全新浏览器跑完 F1+F2+F3+F4+F5
  点击流程。

## 5. 横向与推迟交付物（跟踪）

- **CI codegen gate。** 见
  [backend-expansion-plan.zh.md §5](./backend-expansion-plan.zh.md#5-cross-cutting--deferred-deliverables-tracked)。
  **建议时机：与 F2 一起交付** — F2 引入两个新后端 schema（Instrument +
  StrategyConfig），是 gate 抓住第一次 stale-codegen 隐患的合适时机。具体形态：
  1. CI 任务跑后端 migrations + 启动 uvicorn。
  2. 对运行中的后端跑 `npm run codegen`。
  3. `git diff --exit-code src/api/schema.d.ts`，过期则任务失败。
- **前端测试。**
  - **Vitest** 当 `useAccounts` / `useInstruments` / `usePositions` 中任何一个
    出现非平凡逻辑（乐观更新、请求取消、F4 的分组模式识别）时引入。大概率 F4
    时间窗。
  - **Playwright** ≥3 个用户旅程：注册 + Account CRUD + Position CRUD；Trade
    录入 happy path；dashboard 合理性。大概率 F4 与 F5 之间。
- **暗色模式开关。** Naive UI 的 `darkTheme` 一个 prop 即可
  （[frontend-implementation-plan.zh.md §2 不在范围内](./frontend-implementation-plan.zh.md#explicitly-not-in-scope-deferred)）。
  方便时再上 — 无依赖。
- **i18n。** 按
  [F0 §2](./frontend-implementation-plan.zh.md#explicitly-not-in-scope-deferred)
  不在 MVP 范围内。双语文档（本文等）并不意味着双语 UI。
- **Account "Unarchive" 按钮。** 见
  [F1 §9 第 1 项](./frontend-implementation-plan-f1.zh.md#9-after-f1)；后端开放
  端点后即可补上。机会主义插入。

## 6. 开放设计决策

每项都是 **OPEN** 待批准。下面是我的倾向。

1. **InstrumentPicker 在 option 场景下的 UX。** option 通过 5 元组
   `(underlying, opt_type, strike, expiry, multiplier)` 标识。*倾向：* option 场景
   下 picker 拆两步 — 先 typeahead 选标的，再用专门输入控件选合约属性；picker
   的"选已有或创建"调用因 get-or-create 语义而免费。F2 内 settle。
2. **Trade 录入多腿人体工学。** 两种设计：
   (a) 一个主"加 trade" modal 带"加一条 leg"按钮，行数生长，共享一个
   `order_group_id`；或
   (b) 预制流程（"开 iron condor"、"记 assignment"）自动发射正确的行。
   *倾向：* 上 (b) 并保留"自定义多腿"逃生口指向 (a) — 命名流程覆盖
   [data-model §4.5.2](./data-model.zh.md#452-notion-event--atomic-trade-mapping)
   90% 的映射，逃生口处理长尾。F4 内 settle。
3. **Dashboard 图表库。** ECharts（覆盖最广）、Plotly（数据科学熟悉）、Chart.js
   （最小）。*倾向：* **ECharts** — Vue 3 wrapper `vue-echarts` 成熟；最终想要
   的组合图区间（柱 + 线 + 分币种堆叠）覆盖良好。F5 内 settle。

## 7. 路线图之后

1. **券商 API 集成。** MVP 范围外；落地后 Trade 录入变成 import 驱动，F4 手动
   录入沦为后备路径。
2. **FX 汇率提供方 + 可选换算视图。** 见
   [data-model §6](./data-model.zh.md#currency-placement) 与
   [§7 未来扩展](./data-model.zh.md#future-extensions-deferred-schema-not-committed-yet)。
   等 `FxRate` 表与 provider 存在后，F5 dashboards 加"换算到基础币种"开关。
3. **移动端适配 pass。** Naive UI 是 desktop-first；F5 落地、主用户旅程稳定后
   做一次响应式 audit 合适。
4. **PWA / 离线支持、暗色模式、i18n** — 机会主义。

---

## Changelog

- **v0.4（2026-05-28）** — F3 + F4 + F5 的全部后端 gate 已就绪（P8/P10/P11 ✅、P9 ✅、P12 ✅；后端 406 条测试全绿）。§1「当前状态」改写为「V1 后端切片完整，剩余工作全部在前端」。§3 映射表把 F3/F4/F5 行从「—」翻为「gate 已就绪」。详细 plan `frontend-implementation-plan-f3.md` / `-f4.md` / `-f5.md`（及各自 `.zh.md`）在同一轮迭代里起草。开放决策③（图表库）在 V1 层已敲定为 `vue-echarts`；F5 detail plan 仍会做并排对照的最终记录。
- **v0.3（2026-05-26）** — F2 标为已完成。交付 `InstrumentPicker`（typeahead，
  F3/F4 复用）、`InstrumentForm`（stock/option/forex 分页签 + get-or-create UX）、
  `/instruments` 浏览页、`/settings/strategies` 设置页（支持 PATCH 与硬删除），
  以及 `AuthenticatedLayout` 导航项。决策①（option picker UX）暂缓——
  `InstrumentPicker` 先以 select-only typeahead 形式交付；两步式"先选标的 + 再
  选合约属性"的流程留到 F3 内 Position 创建启用 `allowCreate` 时再落地。前端：
  `vue-tsc` 无报错 + `vite build` 通过 + `schema.d.ts` 与运行中的 OpenAPI 一致。
- **v0.2（2026-05-24）** — F-phase 重切为更粗、"一把梭"的粒度。F2 折叠前
  F2.1/F2.2（Instrument + StrategyConfig）；前 F2.3/F2.4/F2.5（Position + meta
  + Plan）变成 F3；前 F3（Trade 录入）变成 F4；前 F4（Dashboards）变成 F5；
  新增 F6 = Docker 生产接线（之前是悬尾）。开放决策从 4 项减到 3 项（删除"F2
  内部顺序"— 已不再相关）。CI codegen gate 移到"与 F2 一起交付"。
- **v0.1（2026-05-24）** — 初版宏观路线图（含子 phase F2.1–F2.5）。见 git
  历史。
