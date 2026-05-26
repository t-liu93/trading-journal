# 后端 Phase P8 — Position CRUD（实施 plan）

**语言：** [English](./backend-expansion-plan-p8.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-26）。来自宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 中 **P8** 的详细
> 实施 plan。自包含——实施者可直接执行。配套：
> [data-model.zh.md §4.4](./data-model.zh.md#44-position-universal-strategy-instance)、
> **Account 模板**（`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`）、刚交付的
> [backend-expansion-plan-p7.zh.md](./backend-expansion-plan-p7.zh.md)，以及
> [backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)
> 的已定决策汇总。

## 1. 目的与上下文

把已经迁移好的 `positions` 表变成带类型的 CRUD API：通用策略实例聚合，整本日志
都挂在它上面（每个 wheel cycle、IC、PMCC、spot trade、forex trade 都是这里一行）。
**无需 DB 迁移**——该表自 Phase 2 的 `0001_initial_schema` 起就存在。P8 纯粹是
Pydantic schema + router + tests，外加一个薄薄的 `services/positions.py` 接缝，
为未来的自动 close 检测预留位置。

### 已定决策（不要重新推导）

源于 [backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)，
这里以实施者友好的形式复述：

- **Owner-scoped。** 每行都有 `user_id`；每个端点按 `current_active_user.id` 过滤。
  跨用户访问 → **404**（不是 403），与 Account / StrategyConfig 一致。
- **Trade-led 模型（§6②）。** Position 一定与首笔 Trade 同时诞生（F4 内联创建
  流程）。`opened_at` 由客户端传入，**必须等于首笔 Trade 的 `executed_at`**。
  **不存在"等待首笔 Trade"的 NULL 中间态**。后端把 `opened_at` 当普通必填字段；
  后端在创建时**不会**去查 trade（F4 流程负责传对的值、并在同一次客户端事务里
  发布首笔 Trade —— Trade 端点由 P9 落地）。
- **手填快照字段。** `status`（默认 `"open"`）、`closed_at`、`capital_used`、
  `max_risk_at_open`、`max_reward_at_open`、`notes` 由用户填/管理。服务端管理：
  `currency`（从 `primary_instrument.currency` 派生）、`pnl_realized`（close 时冻结）、
  `created_at` / `updated_at`（时间戳）。
- **Close 转换冻结 `pnl_realized`。** 在 PATCH 中带 `status: "closed"` 时，
  服务端 (a) 要求 `closed_at`（payload 中或行上已有皆可），(b) 把该 position
  所有 Trade 的 `cash_flow` 求和写入 `pnl_realized`，(c) 一次提交。冻结后
  `pnl_realized` 不可变。反向转换（`closed → open`）在 MVP 中**拒绝**
  （会留下过时的 `pnl_realized`）；要改请走 `DELETE` + 重建。
- **没有 Trade 时才允许硬删除。** `DELETE /positions/{id}` 仅当该 position 下
  无 Trade 行时返回 204；否则 **409**，detail 为 `"position has attached trades;
  delete the trades first or archive via PATCH"`。（无软删除列；data-model §4.4
  没有 `archived_at`。）
- **本层校验仅做格式。** `account_id` 与 `primary_instrument_id` 必须存在
  （account 还要属于当前用户）；`strategy_type` 必须是合法枚举值（Pydantic
  enforce）；可数小数处 `> 0`；P8 不做跨字段业务校验
  （比如"primary_instrument.kind 与 strategy_type 匹配"刻意**不**强制——wheel
  可以挂股票、IC 也可以挂底层股票，由用户决定）。
- **不强制 `StrategyConfig.max_exposure` 上限。** 推后到 services 层，等下单
  UX 更清楚再做。

## 2. 范围

### 在本 plan 内

- `schemas/position.py` — `PositionCreate` / `PositionUpdate` / `PositionRead`
- `api/positions.py` — router，POST / GET（列表）/ GET（单条）/ PATCH / DELETE
- `services/positions.py` — **新模块**；含 `freeze_pnl_realized()`，为未来自动
  close 检测器预留位置。Router 调用 service；测试同时覆盖两层。
- 在 `main.py` 挂到 `/positions`（最终 URL：`/api/positions`）
- `tests/test_positions.py`
- 后端绿后：重新生成 `frontend/src/api/schema.d.ts`（`npm run codegen`）并提交

### 不在本 plan 内

- **自动 close 检测**（净 qty / 腿状态检测）。`services/` 模块预留接缝；P8 不实施。
- Position 创建时对 **`StrategyConfig.max_exposure` 的强制**。
- **软删除 / archive。** 仅硬删除，且必须无 trade。
- **派生读取字段**（`days_open`、`pnl_unrealized`、`pnl_total`、`roi_on_capital`）。
  随 P12 落地。
- **Wheel / PMCC 策略专属快照**（`WheelCycleMeta` / `PmccCycleMeta`）。随 P10 落地。
- **TradePlan**（P11）。
- **`pnl_realized` 重新计算辅助暴露成 API。** 内部使用——唯一公共表面是
  `status: open → closed` 的 PATCH。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/position.py                  ← 新增
├── api/positions.py                     ← 新增
├── services/                            ← 新增 package
│   ├── __init__.py                      ← 新增（空 marker）
│   └── positions.py                     ← 新增
└── main.py                              ← 改：include positions.router
backend/tests/test_positions.py          ← 新增
frontend/src/api/schema.d.ts             ← 末尾重新生成
```

> `services/` 是 `trading_journal/` 下的新顶层 package。Router 变成薄适配器；
> close 转换逻辑住在 service 里，将来插入自动 close 检测器无需改 router。

## 4. Schema 目标形状

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import PositionStatus, StrategyType


class PositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    opened_at: datetime  # 必须等于首笔 Trade 的 executed_at（F4 负责传）

    # 可选手填快照字段
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 不可变（被 extra="forbid" 拒绝）：
    #   account_id, primary_instrument_id, strategy_type, opened_at,
    #   currency, pnl_realized, created_at, updated_at

    status: PositionStatus | None = None  # 这里仅 "closed" 有意义
    closed_at: datetime | None = None
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    status: PositionStatus
    opened_at: datetime
    closed_at: datetime | None
    capital_used: Decimal | None
    max_risk_at_open: Decimal | None
    max_reward_at_open: Decimal | None
    pnl_realized: Decimal | None
    currency: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

**形状注释。**

- 两个写 schema 都用 `extra="forbid"`，PATCH 时任何尝试设置不可变字段都会拿到
  具体字段错误的 422 —— 不做静默忽略。
- `opened_at: datetime` 在创建时**必填**，没有 `default_factory=datetime.utcnow`。
  F4 客户端在 POST Position-then-Trade 之前从首笔 Trade payload 计算它。
- `closed_at` 在 `PositionUpdate` 中仅在以下两种情况之一被采纳：(a) 同一 PATCH
  同时带 `status: "closed"`，或 (b) `status` 已经是 `"closed"`，用户想 amend
  关闭时间戳。在 open 状态下不带 `status: "closed"` 设置 `closed_at` → 422。
- `currency` 在两个写 schema 中**缺席**；服务端从 `primary_instrument.currency`
  派生，读时返回。
- `pnl_realized` 在两个写 schema 中**缺席**；仅服务端管理。

## 5. Service 层接口（`services/positions.py`）

```python
async def freeze_pnl_realized(
    session: AsyncSession,
    position: Position,
) -> Decimal:
    """对该 position 的所有 Trade.cash_flow 求和；赋给 position.pnl_realized；
    返回该值。调用方负责 commit。"""
```

P8 阶段还没有 Trade 行（P9 才落地），所以真实数据上 `SUM(cash_flow)` 为 `0`。
这个函数仍被接到 close 转换里，使 P9 落地后无需改 router 就能正确关闭。冻结路径
的测试通过直接 `Trade.__table__.insert()`（绕过尚不存在的 P9 router）来 fixture
出 trade 行，证明端到端行为 —— 见 §6。

未来扩展槽（P8 不写代码，只放 docstring）：

```python
async def detect_auto_close(
    session: AsyncSession,
    position: Position,
) -> bool:
    """预留给未来的自动 close 检测器。P8 不实施。Router 尚未调用此函数。"""
```

## 6. 分子阶段 plan

三个子阶段。每个之后：`uv run pytest -q && uv run ruff check . && uv run mypy src`
—— 基线是当前 main / F2 codegen 后的 **127 条测试**。

### P8.1 — Schemas + service 骨架

**目标。** 所有带类型的表面就位；router 尚未挂载。

**任务。**

1. **`schemas/position.py`** —— 上面三个类。
2. **`services/__init__.py`** —— 空 marker。
3. **`services/positions.py`** —— `freeze_pnl_realized`（实现），
   `detect_auto_close`（仅 docstring 桩，`raise NotImplementedError`）。
4. `freeze_pnl_realized` 单元测试（不走 HTTP 层）：
   `tests/test_positions.py::test_freeze_pnl_realized_sums_cash_flow` 通过
   原始 SQL `INSERT` 插一个 position + 3 条 trade，调用函数，断言 position 的
   `pnl_realized` 等于 `sum(cash_flow)`。

**验收。** Schema 干净 import；service 单测绿；尚无 API 表面。

### P8.2 — Router + 增 / 读 / 列 / 改 / 删

**目标。** 全套 CRUD pipeline 在 HTTP 上跑通。

**任务。**

1. **`api/positions.py`** —— router 挂在 `/positions`。私有 helper：

   ```python
   async def _get_owned_position(
       session: AsyncSession, user: User, position_id: uuid.UUID
   ) -> Position:
       stmt = select(Position).where(
           Position.id == position_id, Position.user_id == user.id
       )
       pos = (await session.execute(stmt)).scalar_one_or_none()
       if pos is None:
           raise HTTPException(404, "Position not found")
       return pos

   async def _resolve_account(
       session: AsyncSession, user: User, account_id: uuid.UUID
   ) -> Account:
       stmt = select(Account).where(
           Account.id == account_id,
           Account.user_id == user.id,
           Account.archived_at.is_(None),
       )
       acct = (await session.execute(stmt)).scalar_one_or_none()
       if acct is None:
           raise HTTPException(422, "Account not found or archived")
       return acct

   async def _resolve_instrument(
       session: AsyncSession, instrument_id: uuid.UUID
   ) -> Instrument:
       inst = await session.get(Instrument, instrument_id)
       if inst is None:
           raise HTTPException(422, "Instrument not found")
       return inst
   ```

2. 端点：

   | 方法 | 路径 | 行为 |
   |---|---|---|
   | `POST` | `""` | 解析 account（owner + 未 archived）→ 422 if 不符。解析 instrument → 422 if 不符。插入 `Position`，服务端设置 `user_id`、`currency = instrument.currency`、`status = "open"`。返回 201。 |
   | `GET` | `""` | Owner-scoped。可选 query：`status=open\|closed`、`strategy_type=<enum>`。排序：`opened_at DESC, created_at DESC`。 |
   | `GET` | `"/{id}"` | 单条；跨用户或不存在返回 404。 |
   | `PATCH` | `"/{id}"` | `exclude_unset` 部分更新。**Close 转换分支**（见下）。返回 200 + 更新后的行。 |
   | `DELETE` | `"/{id}"` | 无 Trade 时 204；否则 409。 |

3. **PATCH close 转换分支。** 伪代码：

   ```python
   data = payload.model_dump(exclude_unset=True)

   # 没有 status 翻转 + 当前也不是 closed 时拒绝 closed_at。
   if "closed_at" in data and data.get("status") != PositionStatus.CLOSED \
           and position.status != PositionStatus.CLOSED:
       raise HTTPException(422, "closed_at can only be set on closed positions")

   # 拒绝 closed → open。
   if "status" in data and position.status == PositionStatus.CLOSED \
           and data["status"] == PositionStatus.OPEN:
       raise HTTPException(422, "reopening a closed position is not supported")

   transitioning_to_closed = (
       "status" in data
       and data["status"] == PositionStatus.CLOSED
       and position.status != PositionStatus.CLOSED
   )

   # 先把简单字段写进去。
   for field, value in data.items():
       setattr(position, field, value)

   if transitioning_to_closed:
       if position.closed_at is None:
           # 同一 PATCH 必须带 closed_at，或行上已存在
           raise HTTPException(422, "closed_at is required when closing")
       await freeze_pnl_realized(session, position)

   await session.commit()
   await session.refresh(position)
   ```

4. **`main.py`** —— 挂载 router（`api.include_router(positions.router)` + 一行
   注释），照搬 `instruments.router` 和 `strategy_configs.router` 的方式。

5. **`tests/test_positions.py`** —— §7 给出完整矩阵。

**验收。** 所有 P8 测试绿；后端绿。

### P8.3 — 回归 + codegen + brief

**目标。** 锁基线、把类型推到前端。

**任务。**

1. 后端：`uv run pytest -q && uv run ruff check . && uv run mypy src` 全绿。
   预期总数 ≈ **127 + ~30 条 P8 = ~157 条**。
2. 前端 codegen：后端起在 `:8000`，然后 `cd frontend && npm run codegen` →
   `git diff src/api/schema.d.ts` 应能看到新的 `PositionCreate / Update / Read`
   schema 与 `PositionStatus` 枚举。`npm run build` 通过；**提交重新生成的
   `schema.d.ts`**。
3. 走一遍 §8 的 curl 流程。
4. 在 `review-notes/p8_implementation_brief.md` 写实施 brief（对齐 P6 / P7 brief）。

**验收。** 全绿；`schema.d.ts` 已提交；recipe 通过；brief 在位。

## 7. 测试矩阵

`tests/test_positions.py`，复用 `auth_client`、`second_user_client` 与
`conftest.py` 的迁移过 tempfile fixture。新增一个小 helper 用于在新 DB 中
seed `Account` 与 `Instrument` 行（现有测试在 account 上已经这么做了；复用
该范式）。

### Service 层测试

| 测试 | 验证 |
|---|---|
| `test_freeze_pnl_realized_zero_trades` | 无 trade 的 position → `pnl_realized = 0` |
| `test_freeze_pnl_realized_sums_cash_flow` | 3 条混合符号的 trade → 总和精确 |

### POST `/positions`

| 测试 | 验证 |
|---|---|
| `test_create_201_with_required_fields` | 最小 payload（account / instrument / strategy_type / opened_at）→ 201 + `status="open"` + 派生 `currency` |
| `test_create_with_optional_fields` | 全部可选 snapshot round-trip |
| `test_create_rejects_unknown_field_422` | `extra="forbid"` 生效 |
| `test_create_rejects_missing_opened_at_422` | 必填字段检查 |
| `test_create_rejects_status_in_body_422` | `status` 创建时不可设置 —— 服务端来设 |
| `test_create_rejects_currency_in_body_422` | `currency` 派生 —— 服务端来设 |
| `test_create_rejects_pnl_realized_in_body_422` | 服务端管理 |
| `test_create_rejects_unknown_account_422` | 不存在的 account_id → 422 |
| `test_create_rejects_other_users_account_422` | 别人的 account → 422 |
| `test_create_rejects_archived_account_422` | 已 archived 的 account → 422 |
| `test_create_rejects_unknown_instrument_422` | 不存在的 instrument_id → 422 |
| `test_create_rejects_bad_strategy_type_422` | 非法枚举 → 422 |
| `test_create_rejects_nonpositive_capital_used_422` | `gt=0` 生效 |
| `test_create_derives_currency_from_instrument` | 股票 USD → position currency USD；forex EURUSD → position currency USD |

### GET `/positions`（列表）

| 测试 | 验证 |
|---|---|
| `test_list_returns_only_current_user_rows` | 跨用户隔离 |
| `test_list_orders_by_opened_at_desc` | 最近开的在前 |
| `test_list_filter_status_open` | `?status=open` 过滤 |
| `test_list_filter_status_closed` | `?status=closed` 过滤 |
| `test_list_filter_strategy_type` | `?strategy_type=wheel` 过滤 |
| `test_list_filter_combined` | 两个过滤合用 |
| `test_list_rejects_bad_filter_422` | `?status=cowabunga` → 422 |

### GET `/positions/{id}`

| 测试 | 验证 |
|---|---|
| `test_get_200` | 自己的行 → 200 |
| `test_get_404_unknown` | 随机 UUID → 404 |
| `test_get_404_cross_user` | 别人的 id → 404（不是 403） |

### PATCH `/positions/{id}`

| 测试 | 验证 |
|---|---|
| `test_patch_updates_notes` | 基本部分更新 |
| `test_patch_updates_snapshot_fields` | capital_used / max_risk / max_reward |
| `test_patch_rejects_account_id_change_422` | `extra="forbid"` |
| `test_patch_rejects_primary_instrument_id_change_422` | 不可变 |
| `test_patch_rejects_strategy_type_change_422` | 不可变 |
| `test_patch_rejects_opened_at_change_422` | 不可变 |
| `test_patch_rejects_currency_change_422` | 不可变 |
| `test_patch_rejects_pnl_realized_change_422` | 不可变 |
| `test_patch_close_transition_freezes_pnl_realized` | seed 3 条 trade，PATCH `{status: closed, closed_at: ...}` → 行的 `pnl_realized == sum(cash_flow)` |
| `test_patch_close_transition_with_zero_trades` | 关闭后 `pnl_realized = 0` |
| `test_patch_close_rejects_missing_closed_at_422` | 关闭时不带 `closed_at` → 422 |
| `test_patch_rejects_closed_at_on_open_position_422` | 在 open 状态不带 `status: closed` 设置 `closed_at` → 422 |
| `test_patch_allows_closed_at_amend_when_already_closed` | 已 closed → 可以 amend `closed_at` |
| `test_patch_rejects_reopen_422` | closed → open 转换 → 422 |
| `test_patch_pnl_realized_immutable_after_close` | 第二次 PATCH closed position 不会再改 `pnl_realized` |
| `test_patch_advances_updated_at` | `updated_at` 严格递增 |
| `test_patch_404_cross_user` | 别人的 id → 404 |

### DELETE `/positions/{id}`

| 测试 | 验证 |
|---|---|
| `test_delete_204_when_no_trades` | 硬删除成功；行消失 |
| `test_delete_409_when_trades_exist` | seed 一条 trade → 409 + 文档化的 detail |
| `test_delete_404_cross_user` | 别人的 id → 404 |

### 认证

| 测试 | 验证 |
|---|---|
| `test_requires_auth` | 参数化 POST/GET/PATCH/DELETE 无 cookie → 401 |

## 8. 手动验证流程（P8 完整 walkthrough）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# 注册 + 登录
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed：一个 account + 一个 instrument
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR Margin","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)

INSTR=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)

# 1. 创建 position → 201；currency 派生为 USD
curl -fsSi -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$INSTR\",\"strategy_type\":\"spot_stock\",\"opened_at\":\"2026-05-20T14:30:00Z\",\"capital_used\":\"5000\"}"

POS=$(curl -fsS "$BASE/api/positions" -b "$JAR" | jq -r '.[0].id')

# 2. PATCH notes
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"Initial 100 shares; target 220."}'

# 3. 尝试动不可变字段 → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel"}'

# 4. 关闭但不带 closed_at → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed"}'

# 5. 正确关闭 → 200；pnl_realized = 0（暂无 trade）；closed_at 已设置
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-15T20:00:00Z"}'

# 6. 尝试重开 → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"open"}'

# 7. 列表 + 过滤
curl -fsS "$BASE/api/positions" -b "$JAR"
curl -fsS "$BASE/api/positions?status=closed&strategy_type=spot_stock" -b "$JAR"

# 8. 删除（无 trade 挂载）→ 204
curl -fsSi -X DELETE "$BASE/api/positions/$POS" -b "$JAR"
curl -fsSi "$BASE/api/positions/$POS" -b "$JAR"   # → 404
```

## 9. 实施者 Quickstart

```bash
cd backend
# 按 P8.1 → P8.2 → P8.3 顺序构建；每步之后：
uv run pytest -q && uv run ruff check . && uv run mypy src

# 起 API 做手动检查：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

P8 落地后，下一批后端 gate 是 P10（strategy-meta 扩展）与 P11（TradePlan 事件流）
—— 两者都挂在 Position 上、共同解锁前端 F3。P9（Trade CRUD + 服务端算 `cash_flow`）
解锁 F4，也是首次真正端到端跑 P8 schema 的内联 Position 创建流程。

## 10. 防未来手脚（不实施，但别堵死）

- **自动 close 检测**接入 `services/positions.py::detect_auto_close`。P12
  （派生层）是开始调用它的自然位置 —— 例如后台 job、或 `Trade.create` 后挂的
  hook。
- **软删除 / archive** 后续可加：引入 `archived_at` 列 + list 过滤；router 改为
  扩展而非替换。
- **上限强制**（创建时 `sum(open.max_risk_at_open) + new ≥ StrategyConfig.max_exposure`
  即拒绝）应放在 `services/positions.py`，由 POST 调用。Router 保持薄，这种
  增加就是纯增量。

---

## 变更日志

- **v0.1（2026-05-26）** — 在已定 Trade-led 模型下的初版 P8 build plan：
  `opened_at` 客户端创建时传入、`status`/`closed_at` 手填、`pnl_realized`
  服务端在 close 时冻结、仅在零 trade 时硬删除。三个子阶段：P8.1
  schemas+service、P8.2 router+tests、P8.3 regression+codegen+brief。引入
  `services/positions.py` 作为未来自动 close 检测与上限强制的接缝。
