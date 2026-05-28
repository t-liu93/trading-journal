# 后端横向扩展计划 — CRUD 铺开（Phase 6+）

**语言：** [English](./backend-expansion-plan.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-21）。`refactoring/rebuild` 分支上、在 Account
> tracer bullet 之后继续横向扩展后端的宏观路线图。配套文档：
> [mvp-implementation-plan.zh.md](./mvp-implementation-plan.zh.md)（后端 Phase 0–5）、
> [data-model.zh.md](./data-model.zh.md) 以及前端各计划。本文档**固定阶段顺序与范围**；
> 每个阶段的详细任务/测试拆分留到后续迭代（每阶段一节或一份短文档，体例参照
> [frontend-implementation-plan-f1.zh.md](./frontend-implementation-plan-f1.zh.md)）。
>
> **V1 release plan：** 本路线图中属于 V1 范围的切片整合在
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星文档）。V1 范围或
> 横切决策变更时，本宏观文档与 V1 plan 应在同一次变更里一起更新。

## 1. 当前位置

后端 Phase 0–4 已交付（骨架、`/health`、**全部实体的 v0.2 ORM 模型**、FastAPI Users
认证、`Account` CRUD）。Phase 5（Docker）暂缓。前端 F0（认证）+ F1（Account CRUD UI，
含 `openapi-typescript` codegen）已交付。

**关键事实：** 每个实体的 SQLAlchemy 模型都已存在
（`instrument`、`position`、`trade`、`trade_plan`、`strategy_config`、`strategy_meta`），
但**只有 `Account` 拥有 Pydantic schema + API 端点**。通往可用日志的剩余工作就是
*横向 CRUD 铺开*——逐个实体地把现有模型变成带类型的请求/响应 schema 和路由。

**顺序决策（已定）：** 先把**后端**广度做完，小步推进，**之后**再回到前端（F2+）。
理由：前端纯粹是 API 消费；后端 API 面稳定后，前端页面便宜且改动灵活。无论如何，
前端 F2（Position UI）都被这些后端端点卡住。

## 2. 指导原则

- **沿用 Account 的范式。** `Account`（`schemas/account.py` + `api/accounts.py`）就是
  模板：owner-scoped 查询、跨用户访问返回 404 而非 403、写 schema 用 `extra="forbid"`、
  读 schema 用 `from_attributes`、适用处做软删除。多数新端点就是把这套配方套到新模型上。
- **表达力（可扩展性）是杀手级需求。** 多态 `Instrument`（类表继承）与通用 `Position`
  是两个表达力命脉。尽早把这两者的接口形状立对——它们是价值最高、风险最高的步骤。
- **小步、顺序、可验证。** 每个阶段在进入下一个之前保持后端全绿
  （`pytest` + `ruff` + `mypy --strict`）。任何阶段都不依赖更靠后的阶段。
- **延后需要行情数据的计算。** 已实现 PnL（对成交现金流求和）与 `days_open` 是纯算术，
  现在就能做；*未实现*（unrealized）PnL 需要我们尚不具备的实时行情源——延后。

## 3. 依赖关系图

```
User ─┬─> Account ─────────────┐
      │                        ├─> Position ─┬─> Trade
      └─> StrategyConfig        │            ├─> TradePlan（事件流）
                                │            └─> Wheel/PmccCycleMeta（1:1 扩展）
Instrument（无 user_id；全局 ───┘
 参考数据）+ OptionContract / ForexPair 扩展
                                            └─>（派生读取层：PnL、days_open、ROI）
```

- **`Instrument` 是根**，且**没有 `user_id`**——它是全局共享参考数据（见 §6 决策①），
  被 `Position.primary_instrument_id`、`Trade.instrument_id`、`OptionContract.underlying_id`、
  `PmccCycleMeta.leap_instrument_id` 引用。
- **`StrategyConfig`** 仅依赖 `User`——完全独立，顺序灵活。
- **`Position`** 需要 `Account` + `Instrument`。**`Trade`/`TradePlan`/strategy-meta** 需要
  `Position`。**派生读取层**跨 `Trade` 行聚合。

## 4. 阶段路线图

| 阶段 | 实体 / 范围 | 风险 | 解锁 | 状态 |
|---|---|---|---|---|
| **P6** | `Instrument` + `OptionContract` + `ForexPair`（create / get / list / search；update/delete 受限——见 §6①） | ⭐⭐⭐ | 一切；前端 instrument 选择器 | ✅ 已完成（2026-05-24） |
| **P7** | `StrategyConfig` CRUD（`(user_id, strategy_type)` 唯一，upsert 风格） | ⭐ | 策略设置 UI | ✅ 已完成（2026-05-24） |
| **P8** | `Position` CRUD（owner-scoped；Trade-led — 见 §6②；`status`/`closed_at`/`capital_used` 手填） | ⭐⭐ | 前端 F3 | ✅ 已完成（2026-05-26） |
| **P9** | `Trade` CRUD（原子成交；`order_group_id` 多腿；服务端算 `cash_flow`；action↔kind 校验 — 见 §6④） | ⭐⭐⭐ | 前端 F4 | ✅ 已完成（2026-05-26） |
| **P10** | `WheelCycleMeta` + `PmccCycleMeta`（1:1 Position 扩展） | ⭐ | 策略专属视图 | ✅ 已完成（2026-05-27） |
| **P11** | `TradePlan` 事件流（append revision / list / current） | ⭐⭐ | 外汇计划 UI | ✅ 已完成（2026-05-27） |
| **P12** | 派生读取层（services）：列表/详情中的 `net_cash_flow` + `GET /dashboard/summary`；unrealized 延后 | ⭐⭐⭐ | 仪表盘 / 图表（F5） | ✅ 已完成（2026-05-28） |
| **PX** | 外部集成 Tracer Bullet（股票走 OpenFIGI lookup、forex 本地 seed、DB 缓存表、feature flag、优雅降级）— 见 §4.PX | ⭐⭐ | F2/F3 的 typeahead + 回填；立外部集成接缝 | —（机会主义） |

> 阶段编号延续 `mvp-implementation-plan` 谱系（Phase 0–5）。Phase 5（Docker）仍待办，
> 位置灵活——见 §5。

### P6 — Instrument（base + 扩展）✅ 已完成（2026-05-24）

- **目标。** 提供带类型的 API，跨三种 MVP 工具类型（`stock`、`option`、`forex`）
  创建和查找可交易工具，把类表继承范式（base `Instrument` + 1:1 `OptionContract`
  / `ForexPair`）干净表达，使未来类型（`future`、`crypto`）只需追加。
- **范围。** `GET /instruments`（按 `symbol`/`kind` 列表/搜索）、`GET /instruments/{id}`
  （join 扩展）、`POST /instruments`（**get-or-create**，按 `kind` 分支）。无 update/delete
  （共享、被他人 position 引用）。
- **创建语义（已定）。**
  - **get-or-create + 按自然键去重**：股票 `(kind, symbol, exchange, currency)`，期权
    `(underlying, opt_type, strike, expiry, multiplier)`。已存在→200；新建→201。
  - **symbol 规范化**（`.upper().strip()`）后再查/插。
  - **股票**身份 = `symbol` + `currency`（必填），`exchange` 可选。
  - **期权**用 `underlying_symbol` 顺带建底层股票（`underlying_exchange` 可选）；`currency`
    共享继承（期权 currency == 底层 currency，data-model §4.3），不问两遍。
  - **外汇**由 `ForexPair.quote_currency` 派生 `Instrument.currency`，使 §4.3 不变量无法被
    违反；payload 带 `base_currency`/`quote_currency`/`pip_size`。
  - **核心只做格式校验**（currency `^[A-Z]{3}$`、symbol 非空、`strike>0`、合法 `expiry`、
    枚举成员）。事实性校验（是不是真实代码）属于 **PX** 层（见 §4.PX）。
- **已定决策。** 所有权与去重（§6①）。事实性校验/补全在 2026-05-26 从 P6 中拆出，
  改名 **PX — 外部集成 Tracer Bullet**（§4.PX），独立、机会主义、不阻塞任何 phase，
  也不被任何 phase 阻塞，所以不再打断 P8 → P12 的顺序。

### P7 — StrategyConfig ✅ 已完成（2026-05-24）

- **目标。** 每用户的策略级配置（敞口上限）。几乎是 `Account` 的复制，去掉软删除，
  加上 `(user_id, strategy_type)` 唯一约束。
- **范围。** create/upsert、按 strategy 查询、list、update、delete。顺序灵活——P6 之后
  任何时候都能做（甚至可作为热身提前做）。

### P8 — Position ✅ 已完成（2026-05-26）

- **目标。** 通用策略实例聚合，像 `Account` 一样 owner-scoped。
- **模型（§6② 已定）：** *Trade-led，混合派生。* 前端 F4 的流程是"先录一条 Trade
  → 选择挂到已有 Position 或内联新建一个"，所以 Position 一定与首笔 Trade 同时
  诞生。后端如下反映：
  - **`opened_at`** 在创建时必填，**且必须等于首笔 Trade 的 `executed_at`**
    （F4 的内联创建流程负责传）。后端把它当普通字段；不存在"等首笔 Trade"的
    NULL 中间态。
  - **`status`**、**`closed_at`**、**`capital_used`**、**`max_risk_at_open`**、
    **`max_reward_at_open`**、**`notes`** 由用户手填/管理。默认值：
    `status="open"`，其余 `NULL`。
  - **`pnl_realized`** 由服务端在 PATCH `open→closed` 转换时冻结为该 position
    的 `SUM(trade.cash_flow)`；保持 open 期间为 NULL。
  - **`currency`** 由 `primary_instrument.currency` 派生（data-model §6）；
    客户端不传。
  - 自动 close 检测（净 qty → 0 即视为关闭）**延后**。预留
    `services/positions.py` 接缝，未来检测器可加而不破 API。
- **范围。**
  - `POST /positions` — owner-scoped 创建。必填：`account_id`、
    `primary_instrument_id`、`strategy_type`、`opened_at`。可选手填：
    `capital_used`、`max_risk_at_open`、`max_reward_at_open`、`notes`。服务端
    设置 `status="open"`、从 instrument 派生 `currency`。
  - `GET /positions` — 列表，可按 `status` 与 `strategy_type` 过滤，按
    `opened_at DESC` 排序。
  - `GET /positions/{id}` — 取单条；跨用户 404。
  - `PATCH /positions/{id}` — 部分更新手填字段，**外加** `status` 的
    `open → closed` 转换（服务端在同一调用里冻结 `pnl_realized` + `closed_at`）。
    `account_id`、`primary_instrument_id`、`strategy_type`、`opened_at`、
    `currency`、`pnl_realized` 在 PATCH 中不可变。
  - `DELETE /positions/{id}` — **仅当该 position 下没有 Trade 时**才允许硬删除
    （否则会破坏历史）。已有 trade 则返回 409。刻意不引入软删除。
- **不在 P8 范围。** 对 `StrategyConfig.max_exposure` 的下单时强制（推后到 services
  层）；trade 聚合派生读取（`days_open`、`pnl_unrealized`）；自动 close 检测。

### P9 — Trade ✅ 已完成（2026-05-26）

- **目标。** 在 Position 下记录原子的 broker 级成交；数据录入主力。
- **范围。** 创建（单条，以及共享一个 `order_group_id` 的多条，用于 IC /
  assignment / exercise，对应 data-model §4.5.2）；按 position 列表；update / delete。
  所有权经 `position.user_id` 传导；`account_id` 反范式化以匹配 position
  （服务端强制，不接受客户端传入）。
- **校验（§6④ 已定）。**
  - `action ↔ instrument.kind` 一致 — `bto/sto/btc/stc` ⇒ option；`buy/sell` ⇒
    stock/forex。不一致返回 422。
  - `quantity > 0` 始终成立；**期权必须为正整数**；股票 / 外汇允许小数（覆盖
    fractional shares + 外汇 micro-lot）。
  - `price > 0` 始终成立（每单位成交价；符号交给 `cash_flow`/`action`）。
  - `commission >= 0`、`fees >= 0`。都是无符号成本；服务端在 `cash_flow`
    公式中扣除它们。
  - **`cash_flow` 由服务端计算**（不接受客户端传值）：
    ```
    cash_flow = sign(action) × price × quantity × multiplier
                − commission − fees
    其中 sign(action) = -1（buy/bto/btc）；
                       +1（sell/sto/stc）；
        multiplier   = option 取 OptionContract.multiplier，
                       其他 = 1。
    ```
    Trade 创建 schema 中**没有** `cash_flow` 字段。服务端单一真理源，避免
    客户端/服务端公式漂移，也防 broker-API spoofing。
- **`order_group_id` 语义。** 可选。给出时，同一 POST 的所有行一起校验、共用此
  UUID；未分组的 trade 为 NULL。端点同时接受单个对象或数组（原子多腿提交）。
  模式识别（Assignment / Exercise / IC-open）放在前端展示层（data-model §4.5.2）。

### P10 — Strategy-meta 扩展 ✅ 已完成（2026-05-27）

- **目标。** 1:1 Position 扩展，存放策略专属快照/配置（`WheelCycleMeta`：资金/借款/利息；
  `PmccCycleMeta`：`leap_instrument_id`）。
- **范围。** 绑定到某 Position 的 create/get/update；仅对匹配的 `strategy_type` 有意义。

### P11 — TradePlan 事件流 ✅ 已完成（2026-05-27）

- **目标。** 每个 Position 的只追加计划修订；查询"当前计划"。
- **范围。** 追加修订（每 position 自增 `revision_no`）、列出历史、取当前
  （`MAX(revision_no)`）。历史修订不可 update/delete（data-model §4.6）。

### P12 — 派生读取层 ✅ 已完成（2026-05-28）

- **目标。** 让日志真正有用的数字，读时从 `Trade` 行计算
  （data-model §4.4 "Derived — NOT stored"）。
- **已交付。** 在 `GET /positions` 与 `GET /positions/{id}` 响应中加入
  per-position `net_cash_flow` 字段（按 position_id `SUM(trade.cash_flow) GROUP BY`，
  排除 archived trade，永远存在 —— 无 trade 时返回 `Decimal("0")`）。新增
  `GET /api/dashboard/summary` 端点，返回 `ClosedSummary`（count、win_rate、
  per-currency PnL、按 (月, 货币) 的 monthly PnL）+ `OpenSummary`（count、
  per-currency net_cash_flow）。owner-scoped；无新 DB 迁移，全部派生。复用
  `services/positions.py` 加批量 `compute_net_cash_flows`；新增
  `services/dashboard.py`，含 `compute_summary(session, user_id)`。
- **延后。** `pnl_unrealized`、`pnl_total`、`annualized_return`——需要行情源（不在 MVP）。
  单仓位 `days_open` / `roi_on_capital` / `result` 按 V1 release plan 决策 5 在前端计算。
  FX 换算与更细分端点（`/per-currency`、`/monthly-pnl` 等）延后到 V1.x。

## 5. 横切 & 延后交付物（已登记追踪）

它们不在依赖链上，但绝不能丢：

- **Phase 5 — Docker 单容器部署。** 定义见
  [mvp-implementation-plan.zh.md §5 Phase 5](./mvp-implementation-plan.zh.md)。不阻塞；
  建议位置：回到前端之前，让可部署产物包住一个有意义的后端。
- **CI 流水线（MVP 交付物）。** 目前无 `.github/workflows`。最低限度：后端
  `ruff` + `mypy --strict` + `pytest`；前端 `npm run build`（`vue-tsc`）。
  **要包含 codegen 新鲜度门禁**：一个 job 对全新迁移后的后端跑 `npm run codegen` 再
  `git diff --exit-code src/api/schema.d.ts`——抓出"后端 schema 改了但 `schema.d.ts`
  没重新生成"的情况。随着 P6+ 引入大量新 schema，这会成为真实风险。（前端 F1 §6 已把
  它标为 post-F1 follow-up。）
- **Codegen 机制——已完成（F1.1）。** `openapi-typescript` devDep、`codegen` npm 脚本、
  已提交的 `frontend/src/api/schema.d.ts`、README 工作流都已就位。唯一缺口是上面的
  CI 门禁。每个改动 schema 的后端阶段之后，重跑 `npm run codegen` 并提交 diff。

## 6. 设计决策

四项跨阶段决策全部**已定**。记录在此让后续 phase 共享同一套词汇；具体落实在各 phase 详细 plan。

1. **Instrument 所有权与去重**（曾卡 P6）。**P6 内已定（2026-05-24）：**
   `Instrument` 无 `user_id` → 全局共享参考数据。任意已认证用户可 create + get +
   search。按自然键 **get-or-create 去重**（股票 `(kind, symbol, exchange, currency)`；
   期权 `(underlying, opt_type, strike, expiry, multiplier)`）。**无 update/delete** ——
   instrument 会跨用户被 position 引用。外部事实校验/补全是非阻塞的 **PX** phase
   （由原 P6.x 改名），不是写入时硬依赖。

2. **Position 创建语义**（曾卡 P8）。**2026-05-26 已定：** *Trade-led 混合派生。*
   Position 一定与首笔 Trade 同时诞生（F4 内联创建流程）。`opened_at` 在创建时由
   客户端传入，**必须等于首笔 Trade 的 `executed_at`**（无 NULL 中间态）。
   `status` / `closed_at` / `capital_used` / `max_risk_at_open` /
   `max_reward_at_open` / `notes` 由用户管理；服务端默认 `status="open"`，在显式
   PATCH `open→closed` 转换时冻结 `pnl_realized` + `closed_at`。自动 close 检测
   （净 qty → 0 ⇒ closed）延后；预留 `services/positions.py` 接缝供未来添加检测器。

3. **MVP 算多少**（影响 P8/P9/P12）。**2026-05-26 已定：**
   - **存盘**：`pnl_realized`（close 时冻结）、每条 Trade 的 `cash_flow`
     （Trade 创建时服务端计算 —— 见 §4 / §6④）。
   - **P12 读时派生**：`days_open`、`pnl_total`、`roi_on_capital`、`result`
     （win/loss）。不做"为速度反范式化"的重复存储。
   - **延后**：`pnl_unrealized`、`annualized_return` —— 需要行情源，不在 MVP。

4. **Trade 校验深度**（曾卡 P9）。**2026-05-26 已定：**
   - `action ↔ instrument.kind` 一致（不一致 422）。
   - `quantity > 0` 始终成立；期权必须正整数；股票 / 外汇允许小数。
   - `price >= 0` 始终成立（每单位成交价；符号完全由 `cash_flow` 中的 `action` 符号决定——参见 data-model §4.5.2 中合法使用 price=0 的 worthless-expire / assignment 场景）。
   - `commission >= 0`、`fees >= 0`（无符号成本）。
   - **`cash_flow` 服务端计算**：
     `sign(action) × price × quantity × multiplier − commission − fees`；
     创建 schema 不接受它。单一真理源 → 没有客户端 / 服务端公式漂移、不被
     broker-API spoofing。

## 4.PX — 外部集成 Tracer Bullet（独立阶段，机会主义）

> 原 "P6.x"。2026-05-26 提升为独立阶段 **PX** —— 它没有前序依赖、也不卡任何阶段，
> 所以数字流 P8 → P12 现在是严格顺序的。PX 什么时候有空什么时候插入。

- **超出 Instrument 的意义。** 这是项目*第一次*外部 API 集成，刻意当作 tracer
  bullet，立好后续每次集成（broker 成交、FX 汇率、行情）都要复用的两条接缝：
  - **① 外部 API 访问** —— 后端 `integrations/` 模块、key 进 `config.py`（`.env`）、
    异步 `httpx` 客户端、超时 + 优雅降级；**绝不把异常抛进写入路径**。
  - **② 外部数据存储/缓存** —— 重复 lookup 不反复打第三方的持久化范式。*倾向：*
    DB 缓存表 `(provider, query) → payload + fetched_at` 带 TTL。备选：内存 TTL。
- **用户侧行为。** 后端 `GET /instruments/lookup?q=` 驱动前端 typeahead + "是不是
  想输 AAPL?" 提示与创建时回填（exchange/currency）。手填 + 格式校验始终是
  always-works 核心；provider 未配置/挂掉/查空时 lookup 层静默降级。**绝不阻塞**
  instrument 创建。
- **按类型范围。** 股票：经免费 provider 校验/回填（lean **OpenFIGI**）。外汇：本地
  seed 主流货币对（不走外部）。期权：跳过外部，仅经股票路径校验底层。
- **排期 PX 时再敲的子决策。** (a) provider —— *lean OpenFIGI*（免费、偏官方、
  代码→证券/交易所映射）；Finnhub / FMP 备选。(b) 缓存机制 —— DB 表 vs 内存 TTL
  （*倾向 DB 表*，真正立起存储接缝）。(c) feature flag + key 在 `config.py`/`.env`
  里的布局。
- **排序。** 无任何 phase 被它阻塞；插入时机是机会主义。如果 PX 在 F3 或之后才
  落地，前端 `InstrumentPicker` 与 `InstrumentForm` 会在不改其他 phase 代码的情况
  下自动获得 typeahead + 回填（同一个 API 表面下行为升级）。

## 7. 路线图之后

1. **前端 F3**（Position 列表 / 详情 / 编辑 —— *没有* 内联创建入口，create
   按 Trade-led 模型移到 F4）—— P8 + P10 + P11 落地后。**F4**（Trade 录入 +
   内联 Position 创建）在 P9 之后。
2. **F5 仪表盘/图表**消费 P12 派生层。
3. **Postgres 对齐与部署**——后端 Phase 5 Docker（F6）+ 在任何生产使用前对
   Postgres 验证迁移（mvp-implementation-plan §9）。
4. **PX** 可在任意方便时机落地 —— typeahead + 回填会在后端 lookup 端点上线后
   自动在 F2/F3 中点亮。

---

## 变更日志

- **v0.6（2026-05-28）** — P12 派生读取层在 `refactoring/rebuild` 上交付。P12.1
  在 `PositionRead`（list + detail）加入 `net_cash_flow: Decimal`，由批量的
  `services/positions.compute_net_cash_flows` 驱动（单次请求一条 SUM-GROUP-BY，
  无 N+1）。P12.2 新增 `GET /api/dashboard/summary`，返回 per-currency 已平 P/L
  + 月度桶 + win_rate + per-currency 持仓 net_cash_flow 快照。新文件：
  `schemas/dashboard.py`、`services/dashboard.py`、`api/dashboard.py`、
  `tests/test_dashboard.py`（13 条）。`tests/test_positions.py` 扩充 `net_cash_flow`
  覆盖。`frontend/src/api/schema.d.ts` 已重新生成。后端测试套件：**406 条全绿**
  （之前 347）；`ruff` + `mypy --strict` clean。V1 后端切片至此全部完成；剩余
  V1 工作为前端 F3 → F4 → F5 → F6。PX 仍属机会主义。
- **v0.5（2026-05-27）** — P8 / P9 / P10 / P11 全部在 `refactoring/rebuild` 上交付。
  P8 引入 `services/positions.py`（Trade-led、手填 status、服务端冻结 `pnl_realized`）。
  P9 引入 `services/trades.py`（原子成交、服务端算 `cash_flow`、`order_group_id`
  多腿、`Trade.archived_at` 软删）。P10 引入 `services/strategy_meta.py`（嵌套
  `/positions/{pid}/wheel-meta` 与 `.../pmcc-meta` 共 8 个端点）。P11 引入
  `services/trade_plans.py`，严格 append-only 事件流（4 个端点、服务端分配
  `revision_no`、无 PATCH/DELETE）。状态表翻篇：P8 → P9 → P10 → P11 全部 ✅；
  **P12 现在是 ⏳ 下一步**。V1 release plan（[v1-release-plan.zh.md](./v1-release-plan.zh.md)）
  整合 V1 切片，并把 P12 范围细化为「单仓位派生前端算、后端 P12 只交付列表聚合 +
  dashboard 端点」。后端测试套件：**347 条全绿**；`ruff` + `mypy --strict` clean。
- **v0.4（2026-05-26）** — P9 Trade CRUD 交付。§6④ 修正：
  `price > 0` → `price >= 0`，以兼容 data-model §4.5.2 中合法使用
  `price=0` 的 worthless-expire / assignment 场景。后端测试套件：272 条全绿。
- **v0.3（2026-05-26）** — 决策②③④全部 settle。
  ② Position 改为 **Trade-led**：`opened_at` 在创建时由客户端传入（= 首笔 Trade
  的 `executed_at`）；`status`/`closed_at`/`capital_used` 手填；PATCH `open→closed`
  时服务端冻结 `pnl_realized`；自动 close 检测延后，预留 `services/` 接缝。
  ③ 存盘 = `pnl_realized` + `cash_flow`；P12 派生 = `days_open`、`pnl_total`、`roi`。
  ④ Trade 校验：action↔kind 强制、期权 qty 整数、stock/forex qty 小数、
  `price > 0`、`cash_flow` **仅服务端计算**（Create schema 不接受客户端值）。
  原 `P6.x` → 独立 **PX — 外部集成 Tracer Bullet**（§4.PX，机会主义、不阻塞任何
  phase）。P8/P9 叙述章节按已定规则重写。
- **v0.2（2026-05-26）** — 把 P6 和 P7 标为已完成（2026-05-24 交付）。决策①
  （Instrument 所有权/去重）在 P6 内 settle。后端测试套件：127 条全绿
  （`pytest` + `ruff` + `mypy --strict`）。
- **v0.1（2026-05-21）** — 初版宏观路线图。Phase 6–12 顺序 + 范围，从 Instrument 起步；
  横切 CI/Docker 追踪；四项未决设计决策。各阶段详细任务/测试拆分留待后续迭代。
