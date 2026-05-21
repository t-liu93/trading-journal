# 后端横向扩展计划 — CRUD 铺开（Phase 6+）

**语言：** [English](./backend-expansion-plan.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-21）。`refactoring/rebuild` 分支上、在 Account
> tracer bullet 之后继续横向扩展后端的宏观路线图。配套文档：
> [mvp-implementation-plan.zh.md](./mvp-implementation-plan.zh.md)（后端 Phase 0–5）、
> [data-model.zh.md](./data-model.zh.md) 以及前端各计划。本文档**固定阶段顺序与范围**；
> 每个阶段的详细任务/测试拆分留到后续迭代（每阶段一节或一份短文档，体例参照
> [frontend-implementation-plan-f1.zh.md](./frontend-implementation-plan-f1.zh.md)）。

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

| 阶段 | 实体 / 范围 | 风险 | 解锁 |
|---|---|---|---|
| **P6** | `Instrument` + `OptionContract` + `ForexPair`（create / get / list / search；update/delete 受限——见 §6①） | ⭐⭐⭐ | 一切；前端 instrument 选择器 |
| **P7** | `StrategyConfig` CRUD（`(user_id, strategy_type)` 唯一，upsert 风格） | ⭐ | 策略设置 UI |
| **P8** | `Position` CRUD（owner-scoped；MVP 手填字段——见 §6②） | ⭐⭐ | 前端 F2 |
| **P9** | `Trade` CRUD（Position 下的原子成交；`order_group_id` 多腿） | ⭐⭐⭐ | 前端 F3 |
| **P10** | `WheelCycleMeta` + `PmccCycleMeta`（1:1 Position 扩展） | ⭐ | 策略专属视图 |
| **P11** | `TradePlan` 事件流（append revision / list / current） | ⭐⭐ | 外汇计划 UI |
| **P12** | 派生读取层（services）：`days_open`、close 时冻结 `pnl_realized`、`pnl_total`、`roi`；unrealized 延后 | ⭐⭐⭐ | 仪表盘 / 图表（F4） |

> 阶段编号延续 `mvp-implementation-plan` 谱系（Phase 0–5）。Phase 5（Docker）仍待办，
> 位置灵活——见 §5。

### P6 — Instrument（base + 扩展）

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
    枚举成员）。事实性校验（是不是真实代码）属于 P6.x 层。
- **未决决策。** 所有权与去重已定（§6①）。其余见 P6.x 子决策。

### P6.x — 外部 instrument 校验（项目首个外部 API 集成；可选、非阻塞）

- **超出 Instrument 的意义。** 这是项目*第一次*外部 API 集成，刻意当作 tracer bullet，
  立好后续每次集成（broker 成交、FX 汇率、行情）都要复用的两条接缝：
  - **① 外部 API 访问** —— 后端 `integrations/` 模块、key 进 `config.py`（`.env`）、异步
    `httpx` 客户端、超时 + 优雅降级；**绝不把异常抛进写入路径**。
  - **② 外部数据存储/缓存** —— 重复 lookup 不反复打第三方的持久化范式。*倾向：* DB 缓存表
    `(provider, query) → payload + fetched_at` 带 TTL（注意 data-model §6 不喜欢 JSON 重列
    → 优先结构化列，或接受一个仅缓存用的小 JSON 列）。备选：内存 TTL。
- **用户侧行为。** 后端 `GET /instruments/lookup?q=` 驱动前端 typeahead + "是不是想输
  AAPL?" 提示与创建时回填（exchange/currency）。手填 + 格式校验始终是 always-works 核心；
  provider 未配置/挂掉/查空时 lookup 层静默降级。**绝不阻塞** instrument 创建。
- **按类型范围。** 股票：经免费 provider 校验/回填。外汇：本地 seed 主流货币对（不走外部）。
  期权：跳过外部，仅经股票路径校验底层。
- **开放子决策。** (a) provider —— *倾向 OpenFIGI*（免费、偏官方、代码→证券/交易所映射）；
  Finnhub / FMP 备选。(b) 缓存机制 —— DB 表 vs 内存 TTL（*倾向 DB 表*，真正立起存储接缝）。
  (c) feature flag + key 进 `config.py`/`.env`。
- **排序。** 排在 **P6 核心之后**，使 provider 选型/不稳定永不阻塞 Instrument 地基。

### P7 — StrategyConfig

- **目标。** 每用户的策略级配置（敞口上限）。几乎是 `Account` 的复制，去掉软删除，
  加上 `(user_id, strategy_type)` 唯一约束。
- **范围。** create/upsert、按 strategy 查询、list、update、delete。顺序灵活——P6 之后
  任何时候都能做（甚至可作为热身提前做）。

### P8 — Position

- **目标。** 通用策略实例聚合，像 `Account` 一样 owner-scoped。
- **范围。** 用 `account_id` + `primary_instrument_id` + `strategy_type` 创建；`currency`
  从 instrument 派生（非用户提供，data-model §6）。按 `status` 和 `strategy_type` 列表/筛选。
  更新 notes / 手填快照。软删除还是硬删除？（随 §6② 定。）
- **未决决策。** `opened_at`/`status`/`closed_at` 手填 vs 从 trade 派生（§6②）。

### P9 — Trade

- **目标。** 在 Position 下记录原子的 broker 级成交；数据录入主力。
- **范围。** 创建（单条，以及共享一个 `order_group_id` 的多条，用于 IC / assignment 配对）；
  按 position 列表；update/delete。所有权经 `position.user_id` 传导；`account_id`
  反范式化以匹配 position。
- **未决决策。** 校验深度——action↔kind 一致性、期权 quantity 整数、`cash_flow`
  服务端计算 vs 客户端传入（§6④）。

### P10 — Strategy-meta 扩展

- **目标。** 1:1 Position 扩展，存放策略专属快照/配置（`WheelCycleMeta`：资金/借款/利息；
  `PmccCycleMeta`：`leap_instrument_id`）。
- **范围。** 绑定到某 Position 的 create/get/update；仅对匹配的 `strategy_type` 有意义。

### P11 — TradePlan 事件流

- **目标。** 每个 Position 的只追加计划修订；查询"当前计划"。
- **范围。** 追加修订（每 position 自增 `revision_no`）、列出历史、取当前
  （`MAX(revision_no)`）。历史修订不可 update/delete（data-model §4.6）。

### P12 — 派生读取层

- **目标。** 让日志真正有用的数字，读时从 `Trade` 行计算
  （data-model §4.4 "Derived — NOT stored"）。
- **范围（MVP 可行）。** `days_open`、已实现 PnL（对 `cash_flow` 求和），并在
  status→`closed` 转换时把 `pnl_realized` 冻结到行上；`roi_on_capital`。很可能用一个
  `services/` 模块保持路由精简。
- **延后。** `pnl_unrealized`、`pnl_total`、`annualized_return`——需要行情源（不在 MVP）。

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

## 6. 未决设计决策（在各自阶段动工前敲定）

承接规划讨论。已注明我的倾向，但每一项在拍板前都是**未决**。

1. **Instrument 所有权与去重**（卡 P6）。`Instrument` 无 `user_id` → 全局共享参考数据。
   待定：谁能创建；是否对股票按 `(kind, symbol, exchange, currency)`、对期权按
   `(underlying, opt_type, strike, expiry, multiplier)` 做 "get-or-create" / 去重；
   是否允许 update/delete 被全局引用的 instrument。**已定：** 对任意已认证用户开放
   create+get/search，按自然键 get-or-create 去重，无 update/delete（instrument 会被其他
   用户的 position 引用）。外部事实性校验/补全是非阻塞的 **P6.x** 切片（进 MVP），
   不是写入时的硬依赖。
2. **Position 创建语义**（卡 P8）。MVP 手填 `opened_at`/`status`/`closed_at`/`capital_used`
   并提供显式 "close" 动作，**还是**从该 position 的 trade 自动派生。*倾向：* MVP 手填；
   自动派生挪到 P12。
3. **MVP 算多少**（影响 P8/P9/P12）。把已实现 PnL / `days_open` 手存在行上，**还是**在
   P12 读时计算。*倾向：* 行只存诚实数据（用户/broker 提供的部分），派生值在 P12 计算；
   `pnl_realized` 仅在 close 转换时冻结。
4. **Trade 校验深度**（卡 P9）。是否强制 action↔instrument-kind 一致
   （`bto/sto/btc/stc` ⇒ 期权；`buy/sell` ⇒ 股票/外汇）？期权 quantity 整数？`cash_flow`
   由服务端从 `action+price+qty+commission+fees` 计算，还是信任客户端传入（data-model
   说 broker 直接报告它）？*倾向：* 强制 action↔kind + 期权整数 qty；接受客户端
   `cash_flow` 但校验其符号与 action 一致。

## 7. 路线图之后

1. **恢复前端 F2**（Position UI）——P6 + P8 落地后；F3（Trade 录入）在 P9 之后。
2. **F4 仪表盘/图表**消费 P12 派生层。
3. **Postgres 对齐与部署**——Phase 5 Docker + 在任何生产使用前对 Postgres 验证迁移
   （mvp-implementation-plan §9）。

---

## 变更日志

- **v0.1（2026-05-21）** — 初版宏观路线图。Phase 6–12 顺序 + 范围，从 Instrument 起步；
  横切 CI/Docker 追踪；四项未决设计决策。各阶段详细任务/测试拆分留待后续迭代。
