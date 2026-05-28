# V1 发布计划

**Language:** [English](./v1-release-plan.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-27）。`refactoring/rebuild` 分支上 trading journal 第一个可部署版本的总览范围文档。整合 [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 与 [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md) 中属于 V1 范围的内容。配套 [data-model.zh.md](./data-model.zh.md)。V1 上线后本文档保留作为 V1 记录，两份 macro 路线图归档。

## 1. 目的与维护约定

本文档是 **V1 的单一事实来源**：

- V1 必含什么、推迟到 V1.x 的是什么
- 2026-05-27 敲定的 5 条横切决策
- 剩余 phase（P12、F3–F6）的执行顺序与依赖图
- 指向各 phase detail plan 的入口（每个 phase 一份 EN+ZH 文档，子阶段作为其内部章节）

**维护纪律。** V1 期间三份文档同步推进：

- 本份 V1 release plan —— V1 切片 + V1 决策
- [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) —— 完整后端 macro 路线图，含 V1.x phase（如 PX）
- [frontend-expansion-plan.zh.md](./frontend-expansion-plan.zh.md) —— 完整前端 macro 路线图

V1 范围或决策变更时，三份文档在同一次改动里一起更新。Macro 文档承载长期视野，本份承载 V1 切片。V1 上线后 macro 归档，本份成为记录。

## 2. 当前状态（2026-05-28）

**Backend**（406 tests pass；`ruff` + `mypy --strict` 全 clean）—— V1 后端切片至此**全部完成**：

- 鉴权 —— FastAPI Users cookie + DB session
- Account CRUD（[mvp-implementation-plan.zh.md Phase 4](./mvp-implementation-plan.zh.md)）
- P6 Instrument（stock / option / forex + 类表继承扩展，get-or-create）
- P7 StrategyConfig
- P8 Position（Trade-led、手动 `status`、server-frozen `pnl_realized`）
- P9 Trade（server-computed `cash_flow`、多腿 `order_group_id`、`archived_at` 软删）
- P10 策略元数据（`/positions/{pid}/wheel-meta` 与 `.../pmcc-meta`）
- P11 TradePlan（append-only 事件流，server 分配 `revision_no`）
- P12 派生读层 —— Position 列表/详情中的 `net_cash_flow` + `GET /api/dashboard/summary`

**Frontend**（`vue-tsc` + `vite build` 全 clean；`schema.d.ts` 与后端对得上）：

- F0 鉴权脚手架 + `AuthenticatedLayout`
- F1 Account CRUD UI
- F2 `InstrumentPicker`（select-only typeahead）+ `InstrumentForm` + `/instruments` 浏览页 + `/settings/strategies`

**尚未实现：** F3（Position UI）、F4（Trade 录入 UI）、F5（Dashboard）、F6（单容器 Docker）。剩余 V1 工作**全部是前端**。

## 3. V1 切片

### V1 必含

| Phase | 交付内容 | Macro 引用 |
|---|---|---|
| **P12** ✅ | Position 列表 `net_cash_flow` + `GET /api/dashboard/summary`（per-currency PnL、月度桶、win_rate、open 快照） | [backend-expansion-plan.zh.md §P12](./backend-expansion-plan.zh.md) |
| **F3** | Position 列表 / 创建 / 编辑 / 详情页（Overview / Meta / Plan / Trades 四 tab）；`InstrumentPicker` 加上 `allowCreate` | [frontend-expansion-plan.zh.md §F3](./frontend-expansion-plan.zh.md) |
| **F4** | Trade 录入 UI（Custom multi-leg 为主）；Position 详情页 Trades tab 按 `order_group_id` 分组展示 | [frontend-expansion-plan.zh.md §F4](./frontend-expansion-plan.zh.md) |
| **F5** | Dashboard —— per-currency PnL 卡片 + open/closed 仓位表 + 1 张图（按月已实现 PnL 柱状） | [frontend-expansion-plan.zh.md §F5](./frontend-expansion-plan.zh.md) |
| **F6** | 单容器 Docker：FastAPI 挂 `frontend/dist`、SPA fallback、SQLite volume | [frontend-expansion-plan.zh.md §F6](./frontend-expansion-plan.zh.md) + [mvp-implementation-plan.zh.md §5 Phase 5](./mvp-implementation-plan.zh.md) |

### V1.x 推迟（显式不在 V1）

下列项目仍保留在 macro 路线图中，V1 上线之后再点亮，V1 工作不依赖它们。完整推迟清单见 §7。

- **PX** 外部 Instrument 校验/补全 —— [backend-expansion-plan.zh.md §4.PX](./backend-expansion-plan.zh.md)
- 未实现 PnL（需要 V1 没有的行情源）
- FX 换算视图 + `FxRate` 表 —— [data-model.zh.md §6](./data-model.zh.md)
- Broker API 接入 + `BrokerCredential`
- OAuth / MFA / AuditLog（未来 `auth-and-security.md`）
- Position `archived_at`（[data-model.zh.md §7 Q5](./data-model.zh.md)）
- Account「取消归档」按钮
- Vitest / Playwright 系统性覆盖
- 暗色模式 / i18n / 移动端适配

## 4. 横切决策（2026-05-27 敲定）

5 条 V1 形状的决策，叠加在各 phase 已在 macro 文档里记录的决策之上。

### 决策 1 —— `InstrumentPicker`：get-or-create + `allowCreate` prop

`InstrumentPicker`（F2 出货时是 select-only）增加 `allowCreate` prop，供 F3 Position 创建和 F4 Trade 创建场景使用。用户输入找不到现有 instrument 时：

- **股票**：picker 弹出「Create new」子表单，字段为格式校验过的 symbol / exchange / currency；POST `/instruments` 是 **get-or-create**，重复键无声返回已存在的行（200），不报错。
- **期权**：两步式 —— 先 typeahead 选 underlying，再单独填 `opt_type / strike / expiry / multiplier`；picker 调用期权的 get-or-create。这样规避了对 5 元组身份做 typeahead 的不现实做法。
- **外汇**：从已有列表选或填 base/quote（`ForexPair` 扩展字段）。

**后端影响：** 无 —— POST `/instruments` 已经在 P6 里实现了 get-or-create。

**前端影响：** F3 给 `InstrumentPicker` 加 `allowCreate` 和内嵌创建子表单；F4 直接复用，无需再改。

### 决策 2 —— F4 Trade 录入：Custom multi-leg 为主

多腿事件（[data-model.zh.md §4.5.2](./data-model.zh.md)）通过通用 **Custom multi-leg 表单** 录入：用户手动加行，表单为同一次提交里的所有行共享一个 server 分配的 `order_group_id`。这与用户在 Notion 里把铁鹰 4 行作为一个 encounter 录入的心智模型一致。

**Named flows**（如「开 IC」「记录指派」）**V1 不承诺**。若 F4 detail 规划阶段识别出高频且行生成纯机械的事件（如 expire = 1 行 price 0 / fees 0），那些可作为构建在 custom 表单之上的 opt-in 助手。短名单在 F4 detail plan 里定，不在这里。

**后端影响：** 无 —— POST `/trades` 已在 P9 里接受 array 共享一个 server 生成的 `order_group_id`。

### 决策 3 —— 图表：`vue-echarts`

Naive UI 没有图表组件原语。V1 用 `vue-echarts`（Apache ECharts 的官方 Vue 3 wrapper）实现 F5 按月 PnL 图。理由：Vue 原生、成熟、覆盖图表类型最广，V1.x 加图也方便。

**对比备选：** `@unovis/vue`（F5 公司开源的 D3 系可视化库 —— **不是** ECharts 的变体）。F5 detail plan 时做并排对比；`vue-echarts` 是当前 lean。

### 决策 4 —— Position：V1 不加 `archived_at`

V1 维持 [P8 现状](./backend-expansion-plan.zh.md)：

- `DELETE /positions/{id}` 是硬删除，**仅** 在没有 `Trade` 也没有 `TradePlan` 行时允许（否则 409）。
- 前端 Position 列表默认 `?status=open`；已平仓仓位通过 status filter 或 History tab 看。

加 `archived_at` 是一次干净的纯加字段迁移，需要时再做（[data-model.zh.md §7 Q5](./data-model.zh.md) 仍是 open question）。推迟到 V1.x。

### 决策 5 —— 派生值：单仓位前端算、列表与聚合后端算

按数据拉取形状和数据量切：

| 范围 | 算在哪 | 原因 |
|---|---|---|
| 单仓位详情页的 `days_open` / `pnl_total` / `roi_on_capital` / `result` | **前端** | 详情页本来就为 Trades tab 拉了该仓位所有 trade —— 顺手 reduce 一下即可。省一个后端端点。 |
| Position 列表的 PnL 列（跨 N 个仓位） | **后端 SQL** | 列表不应付 N 次 trade 拉取代价；一条 `SUM(cash_flow) GROUP BY position_id` 就够便宜。 |
| Dashboard 聚合（per-currency PnL、胜率、按月 bucket） | **后端 SQL** | 跨仓位聚合；只能在后端 SQL 算。 |

**一致性约束。** 前端和后端对单仓位已实现 PnL 的公式必须对得上。两边都算 `SUM(trade.cash_flow)`（open 仓位）；closed 仓位用行上冻结的 `pnl_realized`。极易保持同步。

## 5. 执行顺序与依赖图

```
后端已完成： P6 → P7 → P8 → P9 → P10 → P11 → P12 ✅
前端已完成： F0 → F1 → F2 ✅

V1 剩余（纯前端）：

F3 ──> F4 ──> F5 ──> F6
```

**推荐执行顺序：** **F3 → F4 → F5 → F6**。F3 出 Position 列表（消费 P12 的 `net_cash_flow`）+ 创建/编辑 + 详情页（Overview/Meta/Plan/Trades 四 tab；Trades tab 在 F4 落地前是占位）。F4 接上录入 modal，把 Trades tab 变可交互。F5 消费 `GET /api/dashboard/summary`。F6 把整套打成单容器。

**曾考虑的备选：** 先 F4 后 F3（Trade-led 模型下 Position 与首笔 Trade 同生，先做 F4 能让 F3 永远有真实仓位可显示）。2026-05-26 讨论后回退 —— F3 提供的 Position 列表/详情是 F4 录入 modal 的码头，所以自然顺序是 F3 在前（Trades tab 先以占位 + 只读形态出货），再 F4 让它可交互。

## 6. 各 phase 范围摘要

详细 plan 在各自的 `*-pN.md` / `*-fN.md` 文件里（每个 phase 一份 EN + 一份 ZH，子阶段作为同一份文档内的章节）。这里的摘要仅是 V1 切片 —— 是对 macro 的细化，不是替代。

### 6.1 P12 —— 后端派生读层 ✅ 已完成（2026-05-28）

- **Macro 引用：** [backend-expansion-plan.zh.md §P12](./backend-expansion-plan.zh.md)
- **Detail plan：** [backend-expansion-plan-p12.md](./backend-expansion-plan-p12.md)（+ [.zh.md](./backend-expansion-plan-p12.zh.md)）—— 已完成

**已交付 V1 范围。**

- **P12.1 —— Position 列表增强。** `GET /positions` 与 `GET /positions/{id}` 响应永远包含 `net_cash_flow: Decimal`（一次性批量 `SUM(trade.cash_flow) GROUP BY position_id`，排除 archived trade）。Open 仓位是滚动已实现 PnL 信号；closed 仓位等于行上冻结的 `pnl_realized`（数学上一致）。无 trade 时为零。
- **P12.2 —— Dashboard 聚合端点** `GET /api/dashboard/summary`，owner-scoped，返回：
  - `closed.count`、`closed.win_rate`（`Decimal | None`）、`closed.per_currency_pnl[]`、`closed.monthly_pnl[]`（按 `(month, currency)`）。
  - `open.count`、`open.per_currency_net_cash_flow[]`。
  - 所有 currency 数组按字母排序；monthly 数组按 `(month ASC, currency ASC)` 排。

**显式不在 V1 P12 范围（推迟到 V1.x）：**

- 单仓位派生端点 —— 前端算（决策 5）。
- 行情驱动的 `pnl_unrealized` / `pnl_total` —— V1 没行情源。
- FX 换算后的聚合 —— V1 没 `FxRate` 表。
- 更细分端点（`/per-currency`、`/monthly-pnl`、`/win-rate`、`/counts`）—— 已并入单个 summary 端点；将来有视图需要部分取数再拆。
- summary 端点上的日期范围 / 策略类型 filter。

### 6.2 F3 —— Position UI

- **Macro 引用：** [frontend-expansion-plan.zh.md §F3](./frontend-expansion-plan.zh.md)
- **Detail plan：** `frontend-implementation-plan-f3.md`（+ `.zh.md`）—— 待写

**V1 范围。**

- **`/positions` 列表视图。** 按 `strategy_type` 和 `status` 过滤；默认 `status=open`；按 `opened_at DESC` 排序。每行展示 symbol / strategy / opened_at / `current_pnl`（来自 P12.1）/ currency。
- **Position 创建/编辑 modal。** 使用带 `allowCreate` 的 `InstrumentPicker`（决策 1）。表单字段对应 [data-model.zh.md §4.4](./data-model.zh.md) 可写子集。
- **Position 详情页** 含 tab：
  - **Overview** —— 摘要卡 + 可写手填字段（`capital_used` / `max_risk_at_open` / `max_reward_at_open` / `notes`）+ 只读派生（`days_open` / `pnl_total` / `roi_on_capital` / `result`）由前端计算（决策 5）。
  - **Meta** —— 按 `strategy_type` 条件展示：`wheel` 显示 funding/loan/interest 表单；`pmcc` 显示 LEAP picker；其他类型空状态。背后是 P10 的 `/positions/{pid}/wheel-meta` 与 `.../pmcc-meta` 端点。
  - **Plan** —— TradePlan 事件流（P11）：按时间正序（oldest first）列 revision，append-new-revision 表单。除外汇外多数策略以读为主。
  - **Trades** —— 按 `order_group_id` 视觉分组的 trade 时间线列表。F4 落地前先是占位；读视图和分组逻辑在 F3 出货，录入 modal 留给 F4。
- **Position 删除** —— 当前 409-aware 流程；UI 内联展示「has attached trades / plans」错误（不加 `archived_at`，符合决策 4）。

### 6.3 F4 —— Trade 录入 UI

- **Macro 引用：** [frontend-expansion-plan.zh.md §F4](./frontend-expansion-plan.zh.md)
- **Detail plan：** `frontend-implementation-plan-f4.md`（+ `.zh.md`）—— 待写

**V1 范围。**

- **TradeEntryModal —— Custom multi-leg 表单**（决策 2）：
  - 增删 leg 行；每行携带 `action / instrument / quantity / price / commission / fees / executed_at / notes`。
  - 同一次提交的所有行共享 server 分配的 `order_group_id`（POST `/trades` 用 array body）。
  - 复用 F3 的 `InstrumentPicker` + `allowCreate`；`action ↔ instrument.kind` 校验和 P9 后端规则一致。
  - 每行 `cash_flow` 客户端预览（仅展示 —— 后端是 source of truth）。
- **Position 详情 Trades tab** 展示：
  - 时间线列表，按 `order_group_id` 视觉分组。
  - 根据行形态推断的 pattern badge：**Assignment**（option `btc/stc` @ 0 + 股票 fill @ strike，按 `order_group_id` 配对）、**Exercise**（同理）、**Expiration**（option `btc/stc` @ 0 且无配对股票）、**IC-open**（同一 `order_group_id` 4 条期权腿）。
  - 软删走 P9 的 `archived_at`（`DELETE /trades/{id}` 后用 `?include_archived=true` 查看）。
- **可选 named flows**。在 F4 detail plan 里定，不在这里。默认假设：V1 不做；只有 F4 规划阶段识别出明确收益的机械助手才加。

**显式不在 V1 F4 范围：**

- 视觉 badge 之外的自动策略识别。
- CSV 批量导入 / broker fill 摄入。
- 除非 badge 识别逻辑复杂到需要，否则不写 Vitest。

### 6.4 F5 —— Dashboard

- **Macro 引用：** [frontend-expansion-plan.zh.md §F5](./frontend-expansion-plan.zh.md)
- **Detail plan：** `frontend-implementation-plan-f5.md`（+ `.zh.md`）—— 待写

**V1 范围。**

- **`/dashboard` 重做**（当前是占位卡）：
  - Per-currency PnL 摘要卡（如「+$1,250 USD」「+€180 EUR」），来源 P12.2。
  - Open 仓位表 —— symbol / strategy / opened_at / `current_pnl` / currency。
  - Closed 仓位表 —— symbol / strategy / closed_at / `pnl_realized` / `result`。
  - **1 张图**：按月已实现 PnL 柱状图。Per-currency 堆叠 vs per-currency 切换器 —— detail plan 里定。底层 `vue-echarts`（决策 3）。
- **`src/api/dashboard.ts`**（或 `stats.ts`）包装 P12.2 端点，以 F1 模式提供 `useDashboard` composable。

**显式不在 V1 F5 范围：**

- 多种图表（V1 一张图就够）。
- 跨币种换算后的合计（V1 无 FX）。
- 按策略 drill-down 的仪表盘。
- 月 bucket 之外的日期范围选择器。

### 6.5 F6 —— 单容器 Docker 生产部署

- **Macro 引用：** [frontend-expansion-plan.zh.md §F6](./frontend-expansion-plan.zh.md) + [mvp-implementation-plan.zh.md §5 Phase 5](./mvp-implementation-plan.zh.md)
- **Detail plan：** `v1-implementation-plan-f6.md`（+ `.zh.md`）—— 待写；最终文件名在 F6 plan 开始时再敲定

**V1 范围。**

- **多阶段 Dockerfile：**
  - Stage 1（frontend builder）：`node` 基础镜像，`npm ci && npm run build` → 产出 `frontend/dist/`。
  - Stage 2（backend builder）：`python:3.12-slim`，`uv sync --no-dev --frozen`。
  - Stage 3（runtime）：拷入 backend venv + `frontend/dist`；`CMD uvicorn trading_journal.main:app --host 0.0.0.0 --port 8000`。
- **`main.py` 静态挂载：** `app.mount("/", StaticFiles(directory="frontend/dist", html=True))` 配 SPA fallback，让客户端路由路径返回 `index.html`。API 路由保持现有前缀。
- **入口脚本** 启动 uvicorn 前先 `alembic upgrade head`。
- **`docker-compose.yml`** 用于本地 dev 等价部署（具名 volume 存 SQLite、注入 `.env`）。

**显式不在 V1 F6 范围：**

- HTTPS 终止（由宿主反向代理处理，不在容器里）。
- 多实例 / 水平扩展。
- 容器内 Postgres（V1 保留 SQLite；Postgres 等价性线下验证 —— §8）。

## 7. V1.x 推迟 backlog（汇总）

明确不在 V1 的项目。每项标明触发条件与 macro 引用。

| 项目 | 重新评估的触发条件 | 引用 |
|---|---|---|
| **PX** 外部 Instrument 校验/补全 | 随时；方便时给 `InstrumentPicker` 点亮 typeahead / autofill | [backend-expansion-plan.zh.md §4.PX](./backend-expansion-plan.zh.md) |
| 未实现 PnL | 接入实时行情源后 | [data-model.zh.md §4.4](./data-model.zh.md) |
| FX 换算 + `FxRate` 表 | 用户要求跨币种合计视图 | [data-model.zh.md §6](./data-model.zh.md) / §7 |
| Broker API 接入 + `BrokerCredential` | 手填成为瓶颈时 | [data-model.zh.md §7](./data-model.zh.md) |
| OAuth / MFA / AuditLog | 接入任何超过密码的敏感动作之前 | `auth-and-security.md`（待写） |
| Position `archived_at` | 已平仓堆积成真实困扰时 | [data-model.zh.md §7 Q5](./data-model.zh.md) |
| Account「取消归档」按钮 | 用户真的要恢复归档时 | [frontend-implementation-plan-f1.zh.md §9](./frontend-implementation-plan-f1.zh.md) |
| Vitest / Playwright 系统性覆盖 | F4（或更后）引入非平凡逻辑时 | [frontend-expansion-plan.zh.md §5](./frontend-expansion-plan.zh.md) |
| 暗色模式切换 | 随时；`n-config-provider` 一个 prop 的事 | — |
| i18n | 多语言需求出现时 | — |
| 移动端适配 | V1 上线收到反馈之后 | — |
| `@unovis/vue` vs `vue-echarts` 重评 | V1.x 加第二张图且某一边长处明显时 | 上方决策 3 |
| Trade 上的 `delta_at_open` / 期权快照字段 | 用户开始记录期权 Greeks 时 | [data-model.zh.md §7 Q1](./data-model.zh.md) |
| Position 标签 / labels | 需要超出 `strategy_type` 的分类时 | [data-model.zh.md §7 Q4](./data-model.zh.md) |

## 8. V1 横切交付

### 8.1 CI codegen 新鲜度 gate

**推荐时间槽：** 和 P12 / F3 一起 —— 下一次后端 schema 抖动。

检查步骤：

1. 对一个干净 SQLite 执行 `alembic upgrade head`。
2. 启 uvicorn。
3. `npm run codegen` 跑一次。
4. `git diff --exit-code src/api/schema.d.ts` —— 有 diff 则失败。

捕捉「后端 schema 改了但 `schema.d.ts` 没重新生成」这种隐患 —— F3/F4/F5 扩前端消费面之后会更高发。

### 8.2 Postgres 等价性验证

V1 任何生产部署之前：

- 对 Postgres 跑现有迁移。
- 对 Postgres 跑完整后端测试套件。
- 修复不兼容（预计没有 —— schema 从第一天起就按 Postgres 兼容设计）。

作为 F6 附近的 checklist 项，不算独立 phase。

### 8.3 人工验收 walkthrough

**等 V1 接近完工时再补**（按 2026-05-27 用户指示）—— 等到 F6 是最后一个未打勾的 phase 时，在本文档展开为 §8.3。届时覆盖每条主流程：注册 → account → instrument（含 picker 内嵌创建）→ position（创建 / 编辑 / 详情各 tab）→ trade（单条 + Custom multi-leg）→ dashboard（卡 / 表 / 图）。

## 9. V1 之后

V1.x 候选粗略优先级排序：

1. **PX** 外部集成 —— 给 `InstrumentPicker` 点亮 typeahead / autofill。
2. **Position `archived_at`** + Account「取消归档」—— 已平仓堆积成真实困扰后。
3. **前端测试 runner**（Vitest 单测 + Playwright e2e）覆盖 F4 录入与 dashboard。
4. **图表库重评** —— F5 超过 V1 一张图切片时。
5. **Broker API 接入**（依赖 `auth-and-security.md` 与 `BrokerCredential`）。
6. **FX 换算视图**（依赖 `FxRate` 表 + provider）。
7. **移动端适配** + 暗色模式 + i18n —— 见缝插针。

---

## Changelog

- **v0.2（2026-05-28）** —— P12 后端派生读层交付（406 条测试全绿）。§2「当前状态」更新；§3 V1 切片表中 P12 行打勾；§5 执行顺序图压缩为剩余的纯前端段（F3 → F4 → F5 → F6）；§6.1 改写为已交付记录，字段名定稿（列表/详情上的 `net_cash_flow` + 单个 `GET /api/dashboard/summary`）。§6.1 中 detail plan 链接已可解析。同一轮迭代里起草的前端 detail plan（`frontend-implementation-plan-f3.md`、`-f4.md`、`-f5.md` 及各自 `.zh.md`）。
- **v0.1 (2026-05-27)** —— 初版 V1 release plan。整合 `backend-expansion-plan.md` 与 `frontend-expansion-plan.md` 在 V1 范围内的内容。5 条横切决策敲定：
  1. `InstrumentPicker` get-or-create + `allowCreate` prop；期权走两步式（先 underlying 再属性）。
  2. F4 Custom multi-leg 为主；named flows 推迟到 F4 detail plan 决定。
  3. F5 图表用 `vue-echarts`；`@unovis/vue` 对比推迟到 F5 plan。
  4. Position `archived_at` 推迟到 V1.x；V1 维持 hard-delete-when-empty + `?status=open` 过滤。
  5. 单仓位派生前端算；列表与 dashboard 聚合后端 SQL 算。
