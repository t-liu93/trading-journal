# 后端 Phase P12 — 派生读取层（实施计划）

**Language:** [English](./backend-expansion-plan-p12.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-27）。宏观路线图 [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md)
> 中 **P12** 的详细建设计划。自洽 —— 实现者可直接执行。配套：
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 切片 + 横切决策）、
> [data-model.zh.md §4.4 / §6](./data-model.zh.md#44-position-universal-strategy-instance)
> （币种放置、"派生 — 不存盘" 划分），以及 P12 在其之上扩展的 P8/P9 service
> 层模块（[services/positions.py](../../backend/src/trading_journal/services/positions.py)、
> [services/trades.py](../../backend/src/trading_journal/services/trades.py)）。

## 1. 目的与上下文

把已有的存盘数据（`Position.pnl_realized` 关仓时冻结 + P9 中算出的每笔
`Trade.cash_flow`）转化为**读时聚合**，让日志真正有用：

- **单仓位 `net_cash_flow`** 在 `GET /positions` 与 `GET /positions/{id}`
  响应里 —— 每仓位的 `SUM(trade.cash_flow)`，始终有值，让 UI 能对 open
  仓位呈现一个有意义的滚动数字（例如对 Wheel / PMCC，每股的有效成本基础
  会影响 covered-call 行权价的选择）。
- **`GET /dashboard/summary`** —— 单端点 owner-scoped，返回 F5 仪表盘所
  需的数据：closed 仓位按币种的 Realized P/L、open 仓位按币种的 net cash
  flow 快照、胜率、按月 Realized P/L bucket、计数。

P12 是**纯 Pydantic + service 层 SQL + router + 测试**。**无 DB 迁移** ——
所有值均派生，不存盘。P12 给现有 schema 加一个新字段、加一个新端点家族；
线上兼容面很小但测试面不平凡（跨用户隔离、币种拆分、archived trade 排除、
胜率边界、按月 bucket）。

P12 解锁 **F5**（仪表盘），并启发 **F3**（Position 列表 / 详情页展示
`net_cash_flow` 以辅助交易决策）。F3/F4 不严格需要 P12 —— 单仓位
`net_cash_flow` 可在前端算 —— 但后端在 list 响应里一并返回避免了 N 个仓位
N+1 次 trade 查询。

### 已定决策（不再讨论）

5 条子决策于 2026-05-27 与用户敲定，加上从 P8/P9 沿用的若干默认选择：

- **两个语义不同的分开字段，不合并。** `Position.pnl_realized`
  （存盘、关仓时冻结、open 时 NULL）维持原样 —— 它表达的是「已完整关闭仓位的
  Realized P/L」。新派生字段 `net_cash_flow`（API 始终有值，从不存盘）表达
  的是「至今为止流入/流出该仓位的现金流总和」。closed 仓位上两者数学相等；
  语义上回答不同的问题。前端按 status 选展示哪个；后端只暴露两者。
- **`net_cash_flow` 仅 API 层、读时派生、不存盘。** `positions` 表不加列。
  不迁移。用 `SUM(trade.cash_flow) GROUP BY position_id` 算，`Trade.archived_at
  IS NULL` 排除软删 trade。
- **list / detail 响应里始终包含，无 opt-in flag。** V1 数据量小，
  SUM-GROUP-BY 很便宜；query-string flag 只会给前端每个调用点多一份耦合负担。
- **Dashboard 路径前缀 `/dashboard/*`。** 直白对应 UI 消费者，胜过过早泛化
  (`/stats/*`)。当前端点家族唯一消费者就是 F5 dashboard；若以后有第二个视图
  也需要这套聚合，再回来重新评估。
- **V1 dashboard 是单端点 `GET /dashboard/summary`。** 一次返回 closed
  仓位聚合 + open 仓位快照。拆 `/per-currency`、`/monthly-pnl`、`/win-rate`、
  `/counts` 是 V1.x 的事（若以后某视图需要部分读取）。
- **一份 P12 detail plan、两个子阶段。** P12.1 = list/detail 的 `net_cash_flow`；
  P12.2 = dashboard summary。两个子阶段共享 `SUM(trade.cash_flow)` helper，
  一次写完比拆开效率更高。

沿用以前 phase 的默认（确认但不重新辩论）：

- **全程 owner-scoped。** Dashboard 查询按 `position.user_id == current_user.id`
  过滤；跨用户数据不可见。单仓位派生字段沿用 P8 在 `api/positions.py` 里
  已有的 owner-scoping。
- **聚合排除 archived trades。** `net_cash_flow` 与 dashboard 聚合都加
  `WHERE trades.archived_at IS NULL`。对应 P9 的审计友好软删契约：
  archived 行保留但不再贡献到活数字。
- **不加迁移。** 已确认 —— 所有值都从已有表派生。
- **币种聚合只按仓位币种、不换算。** 无 FX 换算。对应
  [data-model.zh.md §6](./data-model.zh.md#currency-placement)（"组合报告
  按币种汇总，不合并为单一换算总额"）和 V1 release plan 把 FX 推迟到 V1.x
  的设定。
- **胜率分母是否排除 `pnl_realized = 0` 的仓位？** **不排除** —— 把它们计
  入「亏损」侧（即胜率 = `count(pnl_realized > 0) / count(*)` 在 closed 上）。
  Breakeven 是四舍五入产物，V1 不值得开第三档；若日后真要分，前端拿到的
  `pnl_realized` 自己算即可。
- **空数据边界。** 没有 closed 仓位 → `win_rate` 为 `null`（JSON）、计数
  为 0、per-currency 数组为空。没有 open 仓位 → open 块的 per-currency
  数组为空、计数 0。不抛错。

## 2. 范围

### 在本 plan 范围内

- `schemas/position.py` —— 给 `PositionRead` 加 `net_cash_flow: Decimal`。
- `services/positions.py` —— 加 `compute_net_cash_flows(session, position_ids)`
  helper。单条 SQL、批处理、返回 mapping。
- `api/positions.py` —— `GET /positions` 与 `GET /positions/{id}` 都填
  `net_cash_flow`。list 端点通过 helper 批查避免 N+1。
- `schemas/dashboard.py` —— `DashboardSummary` 响应模型（嵌套 `open` +
  `closed` 两块，字段形如 §4）。
- `services/dashboard.py` —— `compute_summary(session, user)`。一两条 SQL
  聚合 + Python 重组生成响应。
- `api/dashboard.py` —— 单端点 `GET /dashboard/summary`。
- 在 `main.py` 里挂接 dashboard 路由（最终 URL 前缀
  `/api/dashboard/summary`）。
- 测试：
  - `tests/test_positions.py` —— 在已有模块上扩展 `net_cash_flow` 字段在
    list/detail 响应里的测试（happy / archived trades / 多 trade 求和 /
    与 closed `pnl_realized` 一致 / 无 trade 时为 0）。
  - `tests/test_dashboard.py` —— 新文件，全面覆盖 owner-scoped + 币种 +
    bucket。
- 后端绿之后：重生成 `frontend/src/api/schema.d.ts` 并提交。

### 不在本 plan 范围

- **不加 DB 迁移。** 所有值派生。
- **不改 `pnl_realized` 写入语义。** P8 的「关仓冻结」保持不动；本 plan
  只读。
- **不加 `days_open` / `roi_on_capital` / `result` 后端端点。** 按 V1
  release plan 决策 5 保留为前端算。详情页本来就为 Trades tab 拉了该仓位
  所有 trade，可从 Position 字段 + `net_cash_flow` 算这些。
- **不算 `pnl_unrealized` / `pnl_total`（mark-to-market）。** V1.x ——
  需要 V1 没有的行情源。
- **不做 FX 换算。** V1.x —— 需要 `FxRate` 表。
- **不拆 `/per-currency` / `/monthly-pnl` / `/win-rate` / `/counts`
  这些粒度更细的端点。** 全部塞进单 summary 端点。等以后真有按需获取的
  消费者再拆。
- **summary 上不做日期范围过滤**（例 `?from=2026-01-01`）。永远返回「全部
  时间」。等到 F5 长出时间范围选择器再加。
- **summary 上不做策略类型过滤。** 永远返回全部策略。F5 的 drill-down 是
  V1.x。
- **不加缓存层。** 每次请求重新计算 —— V1 数据量令缓存为时过早；正确性
  > 延迟。
- **F3/F5 前端实现。** 独立 phase。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/position.py             ← 修改：给 PositionRead 加 net_cash_flow
├── schemas/dashboard.py            ← 新增
├── services/positions.py           ← 修改：加 compute_net_cash_flows helper
├── services/dashboard.py           ← 新增
├── api/positions.py                ← 修改：list/detail 里填 net_cash_flow
├── api/dashboard.py                ← 新增
└── main.py                         ← 修改：include dashboard.router
backend/tests/
├── test_positions.py               ← 修改：加 net_cash_flow 覆盖
└── test_dashboard.py               ← 新增
frontend/src/api/schema.d.ts        ← 末尾重生成
```

模块命名沿用前例：schemas 单数（`position`、`dashboard`）；services / api
复数（`positions`；`dashboard` 这里保持单数 —— 因为 dashboard 概念上是一个
单一表面，不是集合）。

## 4. Schema 形态（目标）

### 4.1 `PositionRead` —— 新增字段

P8 现有 schema 加一个始终有值的派生字段。已有字段不动。

```python
class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # ... 所有 P8 既有字段不变 ...
    pnl_realized: Decimal | None  # 现有：open 时 NULL，关仓时冻结

    # P12 新增 —— API 层始终填值（绝不为 None）。
    # open 仓位：未 archived 的 trade 的 SUM(cash_flow)。
    # closed 仓位：等于 pnl_realized（数学等同）。
    net_cash_flow: Decimal
```

`net_cash_flow` **绝不为 `None`** —— 没有 trade 的仓位返回 `Decimal("0.0000")`。

> **API 工效注**：`net_cash_flow` 由 router（通过 service helper）在返回
> Pydantic 模型前填好，而**不是**靠 SQLAlchemy ORM 端默认值。最简模式
> 是 ORM 模型不动，router 里算 mapping，然后构造 `PositionRead` 时显式把
> `net_cash_flow` 传进去（Pydantic v2 的 `model_validate(obj,
> from_attributes=True)` 后接 `.model_copy(update={"net_cash_flow": ...})`，
> 或写个小 helper）。

### 4.2 `DashboardSummary` —— 响应形态

```python
class CurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    currency: str  # ISO 4217，大写
    amount: Decimal  # numeric(18, 4) 精度


class MonthCurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    month: str  # "YYYY-MM" —— closed_at 的 UTC 月份 bucket
    currency: str
    amount: Decimal


class ClosedSummary(BaseModel):
    count: int
    win_rate: Decimal | None  # count == 0 时为 null；否则 [0, 1] 的小数
    per_currency_pnl: list[CurrencyAmount]
    monthly_pnl: list[MonthCurrencyAmount]


class OpenSummary(BaseModel):
    count: int
    per_currency_net_cash_flow: list[CurrencyAmount]


class DashboardSummary(BaseModel):
    closed: ClosedSummary
    open: OpenSummary
```

**形态注。**

- 用扁平 `list[CurrencyAmount]` 和 `list[MonthCurrencyAmount]`，不嵌字典。
  ECharts（F5 图表库）直接消费扁平元组；嵌字典反正前端还要扁平化。
- `month` 是字符串 `"YYYY-MM"`（ISO 月标识），不是 date —— bucket 才是
  抽象，不是某一天。按 UTC bucketed。
- per-currency 数组按 currency 字母序排（渲染稳定）。
- monthly 数组按 `(month ASC, currency ASC)` 排。
- `win_rate` 是 `Decimal | None`。比率用六位小数过头了，但 `Decimal`
  与所有金额字段保持一致。前端按百分比格式化。

## 5. Service 层接口

### 5.1 `services/positions.py` —— 新增

```python
import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.trade import Trade


async def compute_net_cash_flows(
    session: AsyncSession,
    position_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, Decimal]:
    """返回 {position_id: SUM(trade.cash_flow)}，排除 archived trade。
    没有未-archived trade 的 position **不**出现在返回字典中 —— 调用方应把
    缺失项默认为 Decimal("0.0000")。

    单条 SQL：SELECT position_id, SUM(cash_flow) FROM trades
    WHERE position_id IN (...) AND archived_at IS NULL GROUP BY position_id。

    传入前调用方应物化 iterable 成 list/set —— 函数不重复 iterate。空输入
    直接返回 {}，不打 DB。
    """
    ids = list(position_ids)
    if not ids:
        return {}

    stmt = (
        select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
        .where(Trade.position_id.in_(ids), Trade.archived_at.is_(None))
        .group_by(Trade.position_id)
    )
    rows = (await session.execute(stmt)).all()
    return {row.position_id: row.total for row in rows}
```

单个批查函数同时覆盖 list 端点（`compute_net_cash_flows(session, [p.id for p
in positions])`）和 detail 端点（`compute_net_cash_flows(session,
[position.id])`）。

### 5.2 `services/dashboard.py` —— 完整接口

```python
import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.position import Position, PositionStatus
from trading_journal.models.trade import Trade
from trading_journal.schemas.dashboard import (
    ClosedSummary,
    CurrencyAmount,
    DashboardSummary,
    MonthCurrencyAmount,
    OpenSummary,
)


async def compute_summary(
    session: AsyncSession, user_id: uuid.UUID
) -> DashboardSummary:
    """为指定用户返回 V1 dashboard summary。

    所有查询按 `Position.user_id == user_id` scope。开仓侧 net_cash_flow
    rollup 排除 archived trade（关仓侧用 Position.pnl_realized，已在关仓
    时按当时的 trade 集合冻结）。
    """
    # closed：count + win_rate + per_currency_pnl + monthly_pnl
    closed_stmt = (
        select(
            Position.currency,
            Position.pnl_realized,
            Position.closed_at,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.CLOSED,
        )
    )
    closed_rows = (await session.execute(closed_stmt)).all()

    closed_count = len(closed_rows)
    wins = sum(1 for r in closed_rows if (r.pnl_realized or 0) > 0)
    win_rate = (
        Decimal(wins) / Decimal(closed_count) if closed_count > 0 else None
    )

    per_currency_pnl: dict[str, Decimal] = {}
    monthly_pnl: dict[tuple[str, str], Decimal] = {}
    for r in closed_rows:
        amt = r.pnl_realized or Decimal("0")
        per_currency_pnl[r.currency] = per_currency_pnl.get(r.currency, Decimal("0")) + amt
        month_key = r.closed_at.strftime("%Y-%m")  # UTC；closed_at 是 timestamptz
        monthly_pnl[(month_key, r.currency)] = (
            monthly_pnl.get((month_key, r.currency), Decimal("0")) + amt
        )

    # open：count + per_currency_net_cash_flow
    open_stmt = (
        select(
            Position.id,
            Position.currency,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
        )
    )
    open_rows = (await session.execute(open_stmt)).all()
    open_count = len(open_rows)
    open_position_ids = [r.id for r in open_rows]
    currency_by_position = {r.id: r.currency for r in open_rows}

    # 单条 SQL 批查所有 open 仓位的 SUM(cash_flow)
    open_ncf_map: dict[uuid.UUID, Decimal] = {}
    if open_position_ids:
        ncf_stmt = (
            select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
            .where(
                Trade.position_id.in_(open_position_ids),
                Trade.archived_at.is_(None),
            )
            .group_by(Trade.position_id)
        )
        open_ncf_map = {
            row.position_id: row.total
            for row in (await session.execute(ncf_stmt)).all()
        }

    open_per_currency: dict[str, Decimal] = {}
    for pid, currency in currency_by_position.items():
        amt = open_ncf_map.get(pid, Decimal("0"))
        open_per_currency[currency] = open_per_currency.get(currency, Decimal("0")) + amt

    return DashboardSummary(
        closed=ClosedSummary(
            count=closed_count,
            win_rate=win_rate,
            per_currency_pnl=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(per_currency_pnl.items())
            ],
            monthly_pnl=[
                MonthCurrencyAmount(month=m, currency=c, amount=a)
                for (m, c), a in sorted(monthly_pnl.items())
            ],
        ),
        open=OpenSummary(
            count=open_count,
            per_currency_net_cash_flow=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(open_per_currency.items())
            ],
        ),
    )
```

一个函数搞定。关仓侧聚合在 Python 里对已查回的行做；开仓侧用一条批查 SQL
聚合。两者都 O(N)，N 是该用户的仓位数 —— V1 单用户最多几百个仓位完全够用。
如果将来真上规模了，关仓侧的 Python 重组可以下推到 SQL（`SUM ... GROUP BY
currency, strftime('%Y-%m', closed_at)`）。

> **SQLite vs Postgres 注意**：`closed_at.strftime("%Y-%m")` 是在行查回之后
> 在 Python 里做的，所以两个后端表现一致。如果以后真要把月份 GROUP BY 下推
> 到 SQL：**SQLite 用 `func.strftime("%Y-%m", Position.closed_at)`**，
> **Postgres 用 `func.to_char(Position.closed_at, "YYYY-MM")`** —— 它们写
> 法不同。Python 路径可移植；V1 用这个。

## 6. 阶段计划

两个子阶段。每个之后跑：`uv run pytest -q && uv run ruff check . &&
uv run mypy src`。**P11 后的基线：347 tests pass**。

### P12.1 —— Position 响应加 `net_cash_flow`

**目标。** `GET /positions` 与 `GET /positions/{id}` 始终包含
`net_cash_flow`。前端（之后的 F3）可以在 list 视图与详情页 Overview tab
渲染它。

**任务。**

1. `schemas/position.py` —— 给 `PositionRead` 加 `net_cash_flow: Decimal`。
2. `services/positions.py` —— 加 `compute_net_cash_flows` helper（§5.1）。
3. `api/positions.py` ——
   - `list_positions`：取回仓位后，调一次
     `compute_net_cash_flows(session, [p.id for p in positions])`；然后
     构造每个 `PositionRead` 时从 map 里取 `net_cash_flow`（缺失项默认
     `Decimal("0")`）。
   - `get_position`：调 `compute_net_cash_flows(session, [position.id])`；
     构造 `PositionRead` 时填 `net_cash_flow`。
4. Service 层单测在 `tests/test_positions.py`（扩展现有模块）：
   - `test_net_cash_flow_zero_when_no_trades` —— 新建仓位在 list + detail
     响应里 `net_cash_flow == Decimal("0")`。
   - `test_net_cash_flow_sums_non_archived_trades` —— 插入 3 笔 trade
     和已知值，断言 list + detail 都匹配。
   - `test_net_cash_flow_excludes_archived_trades` —— 通过 P9 的
     `DELETE /trades/{id}` 软删一笔；断言总和扣掉该笔 cash_flow。
   - `test_net_cash_flow_isolated_per_position` —— 同用户两个仓位各有
     trade；和不跨界。
   - `test_net_cash_flow_closed_matches_pnl_realized` —— 关一个仓位
     （PATCH `status=closed`）；断言响应里 `net_cash_flow == pnl_realized`。
   - `test_net_cash_flow_list_endpoint_does_one_query_per_request` ——
     装载 5 个仓位每个 3 笔 trade；断言一条批查 SUM-GROUP-BY，不是 5 条
     （用 SQLAlchemy event listener / 测试 fixture 的查询计数器）。
5. 确认跨用户隔离依然返回 404（已被 P8 现有测试覆盖；除非本次改动改变了
   行为，否则不加新测试）。

**验收。** 所有 P8 测试在新字段存在下通过。新测试绿。Codegen 在 P12 末尾
重跑。

### P12.2 —— `GET /dashboard/summary`

**目标。** 单端点 owner-scoped 返回 V1 dashboard 负载。

**任务。**

1. `schemas/dashboard.py` —— `CurrencyAmount`、`MonthCurrencyAmount`、
   `ClosedSummary`、`OpenSummary`、`DashboardSummary`（§4.2）。
2. `services/dashboard.py` —— `compute_summary(session, user_id)`（§5.2）。
3. `api/dashboard.py` —— 单端点 `GET /api/dashboard/summary`，依赖
   `current_active_user` 和 `get_session`，调
   `compute_summary(session, user.id)`，返回 `DashboardSummary`。
4. 在 `main.py` 里把 `dashboard.router` 挂到 `/api` 下。
5. `tests/test_dashboard.py`：
   - **空用户（无仓位）：** 所有 count 为 0、win_rate 为 `null`、两个
     per-currency 数组为空、monthly 数组为空。
   - **仅开仓、单币种：** closed 块为空，open 块填一个币种、count
     匹配。
   - **仅关仓、单币种：** `per_currency_pnl` 一行、`monthly_pnl` 行匹配
     closed_at 月份、`win_rate` 正确。
   - **跨两个币种（USD + EUR）混合开仓 + 关仓：**
     - closed.per_currency_pnl 两条、按字母序
     - open.per_currency_net_cash_flow 两条、按字母序
     - monthly_pnl 行按 (month, currency) 升序排
   - **胜率边界：**
     - 全部 closed 都是 win → `win_rate == Decimal("1.0")`
     - 全部 loss → `Decimal("0")`
     - `pnl_realized == 0` 计为亏损 → 不算赢
     - 没有 closed 仓位 → `win_rate is None`
   - **archived trade 排除在 open snapshot 之外：** 插入 open 仓位 2 笔
     trade、软删 1 笔；剩余 `net_cash_flow` 只反映未-archived 那笔。
     （closed 侧用关仓时已冻结的 `pnl_realized`，事后归档 trade 不应改变
     `pnl_realized` —— 验证 P8/P9 行为未变。）
   - **跨用户隔离：** 用户 A 的仓位在用户 B 的 dashboard 响应里不可见。
   - **鉴权：** 未认证 `GET /api/dashboard/summary` → 401。
   - **按 UTC 月 bucket：** `closed_at` 为 "2026-04-30 23:30:00 UTC" 的
     仓位 bucket 到 "2026-04"，不是 "2026-05"（健全性检查、不存在本地时区
     漂移）。

**验收。** 后端测试套件绿；`ruff` + `mypy --strict` clean；§7 的人工 curl
walkthrough 成功。

### Codegen —— 在 P12.2 之后

P12.2 出货且测试通过后：

```bash
cd backend && uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run codegen
git diff --exit-code src/api/schema.d.ts  # 预期：有 diff（Position +
                                          # DashboardSummary）
git add frontend/src/api/schema.d.ts
```

提交重生成的 `schema.d.ts` 与后端改动一起。

## 7. 人工验证（curl 配方）

P12.2 出货后，在已登录的 cookie jar 之上：

```bash
BASE=http://localhost:8000
JAR=cookies.txt  # 前次登录得到

# 1. 列表 —— 每行都有 net_cash_flow
curl -fsSi "$BASE/api/positions" -b "$JAR" | jq '.[0].net_cash_flow'
# 预期：Decimal 字符串，如 "12.5000"（或无 trade 仓位为 "0"）

# 2. 详情 —— 同字段存在
curl -fsSi "$BASE/api/positions/<pid>" -b "$JAR" | jq '.net_cash_flow'

# 3. Dashboard summary
curl -fsSi "$BASE/api/dashboard/summary" -b "$JAR"
# 预期：200，body 符合 DashboardSummary schema

# 4. 未鉴权 dashboard
curl -i "$BASE/api/dashboard/summary"
# 预期：401
```

## 8. P12 之后

- **F3** Position UI 在 list 行与详情 Overview 里消费 `net_cash_flow`。
  list 列头对 open 为 **"Net Cash Flow"** / 对 closed 为 **"Realized P/L"**
  （互斥标签 —— 同一列槽位、不同数据源）。
- **F4** Trade 录入不依赖 P12。
- **F5** Dashboard 直接消费 `GET /dashboard/summary`；按月 PnL 图来源
  `closed.monthly_pnl`。
- **PX** 外部集成仍是机会主义。

V1.x 扩展，需要时再做：

- 按策略 drill-down（`GET /dashboard/summary?strategy_type=wheel`）。
- 日期范围过滤（`?from=2026-01-01`）。
- 拆 `/per-currency`、`/monthly-pnl` 等粒度更细的端点（如果有按需读取
  的消费者）。
- 行情 provider 落地后做 `pnl_unrealized` / `pnl_total`。
- `FxRate` 表落地后做 FX 换算聚合。

## 9. 风险与权衡过的备选

- **list 端点 N+1 风险。** 缓解：用 `compute_net_cash_flows` 一条 SQL
  批查。P12.1 的测试断言只发一条查询、不是 N 条。
- **`win_rate` 用 Decimal 还是 float？** 选 Decimal —— 与其他金额 / 比率
  字段一致。六位精度过头但开销很小；前端格式化为 `%`。
- **月份 bucket：Python vs SQL。** 选 Python —— 兼容 SQLite / Postgres
  （见 §5.2 注意）。如果 V1 真出现单用户上千关仓的情形，再下推到 SQL ——
  但 breakeven 点远高于 V1 规模。
- **`net_cash_flow` list 上始终带 vs opt-in flag。** 选始终带 —— opt-in
  会给每个前端调用点加耦合负担，而成本本身很小。如果 V1.x 列表延迟成
  问题再回来评估。
- **单端点 vs 多个粒度端点。** 选单端点 —— V1 dashboard 是一个页面、
  一次拉取。前端 over-fetch 未用字段的开销很小（< 10 KB）。
- **后续若 Trade 修改语义变了**（例改成原地编辑而非软删 + 重插），
  `net_cash_flow` 会自动反映新值，但关仓冻结的 `pnl_realized` 可能与之
  分歧。超出本 plan 范围；标记在
  [data-model.zh.md §7](./data-model.zh.md#open-design-questions-still-need-a-decision-before-implementation)。

---

## 变更日志

- **v0.1（2026-05-27）** —— P12 详细 plan 初版。5 条子决策已定：
  (1) 两个分开字段（`pnl_realized` 关仓冻结 vs 派生 `net_cash_flow`）；
  (2) `net_cash_flow` 仅 API、不存盘；(3) list/detail 始终带（无 opt-in
  flag）；(4) `/dashboard/*` 路径前缀；(5) 单端点
  `GET /dashboard/summary`。两个子阶段：P12.1（Position 响应加字段）、
  P12.2（dashboard 端点）。
