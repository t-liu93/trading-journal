# 后端 Phase P11 — TradePlan 事件流（实施 plan）

**语言：** [English](./backend-expansion-plan-p11.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-26）。来自宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 中 **P11** 的
> 详细实施 plan。自包含——实施者可直接执行。配套：
> [data-model.zh.md §4.6](./data-model.zh.md#46-tradeplan-event-stream)
> （TradePlan 字段定义 + "TradePlan 只记录意图"vs. Trade 的边界划分）、
> 刚起草的 [backend-expansion-plan-p10.zh.md](./backend-expansion-plan-p10.zh.md)
> （嵌套 sub-resource URL 先例），以及
> [backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)
> 的已定决策汇总。

## 1. 目的与上下文

把已经迁移好的 `trade_plans` 表变成带类型的 API：每个 Position 的**事件流**
plan 修订记录。每一行是一次修订；最新修订（`MAX(revision_no)`）即当前
plan；旧行作为历史保留。最初的 Excel 灵感是 forex CFD 入场时带的预定 SL/TP，
但这张表本身策略无关——wheel 的 thesis、PMCC 的 plan、IC 的入场假设都能用。

P11 是**纯 Pydantic + router + 一个微型的 revision_no 分配 service + tests**。
**无需 DB migration**——表自 Phase 2 的 `0001_initial_schema` 就在（含
`UNIQUE (position_id, revision_no)` 约束，P11 直接靠它）。端点很少：一个写、
三个读，没有 PATCH，没有 DELETE。文档对应地紧凑。

P11 解锁 F3 Position 详情页的 Plan tab，把 F3 这一面的后端补齐
（P8 Position + P10 meta + P11 plan）。

### 已定决策（不要重新推导）

2026-05-26 与用户敲定的三个 P11 子决策，外加从 P7/P8/P9/P10 继承的
"按惯例"选项：

- **`revision_no` 由服务端分配。** `TradePlanCreate` **不**包含 `revision_no`；
  客户端塞这个字段 → 422 `extra_forbidden`。服务端按 `position_id` 计算
  `MAX(revision_no) + 1`（首条 = 1）。唯一约束冲突（并发 append）几乎不会出现
  在单用户 MVP；真冒出来就重试一次，第二次失败抛 503。
- **严格 append-only。** **无 PATCH 端点、无 DELETE 端点。** 一旦 POST，永久
  保留。要更正错误 → append 一条新 revision（通常在 `reason` 里标
  "corrects revision N"）。这是对 data-model §4.6 "event stream" 语义最干净
  的解读，也契合 F3 Plan tab 想要的呈现——一张真正的历史表，而不是
  "历史 + 中间夹着编辑"。
- **List 默认 oldest-first 排序。** `GET /positions/{pid}/trade-plans` 按
  `revision_no ASC` 返回（revision 1 → N），让 F3 Plan tab 从上读到下像看
  日志。这与 Position/Trade list（newest-first）有意不同；事件流按时间顺序读。
- **不限制 `strategy_type`。** 任意 Position 都可以挂 TradePlan，不论策略
  类型（data-model §5.5 说 `spot_forex` 是主用例，但没限制；wheel 写 thesis、
  PMCC 写 plan 都合法）。服务端不检查 strategy_type——用户自己选。
- **closed-position 对 TradePlan 写入**不**构成锁定。** 与 P10
  （strategy-meta）一致，TradePlan 是意图/日志数据，不是金融事件。用户
  常常希望在 position 关闭后补一条 post-mortem 修订。`pnl_realized` 不从
  TradePlan 派生，无过期风险。
- **Owner-scoped via Position。** TradePlan 无直接 `user_id`；归属经
  `position.user_id` 流通。跨用户 `position_id` → **404**（与
  P6/P7/P8/P9/P10 一致）。
- **嵌套 sub-resource URL。** `/positions/{pid}/trade-plans/...` ——
  沿用 P10 的 `/positions/{pid}/wheel-meta` 先例。无扁平 collection
  （MVP 没有 "跨 position 列出所有修订" 的用例）。
- **`effective_at` 客户端必传。** 对应 data-model §4.6 "When this revision
  became the active plan"——和服务端管理的 `created_at`（行被记录时间）
  语义上区分开。由客户端选；F3 UI 默认填 `now()` 只是前端便利。
- **格式校验为限。** 数字字段（`planned_entry`、`planned_stop_loss`、
  `planned_take_profit`、`target_rr`）全可选；若给值，必 `> 0`。不做
  跨字段校验（比如"做多 plan 应有 stop_loss < entry < take_profit"——
  **不**强制，方向取决于多/空，由用户自定）。
- **无新 migration。** 表自 `0001_initial_schema` 就在，含唯一约束。

## 2. 范围

### 本 plan 之内

- `schemas/trade_plan.py` —— `TradePlanCreate` / `TradePlanRead`。**无 Update
  schema**（无 PATCH 端点）。
- `services/trade_plans.py` —— `allocate_next_revision_no()`。单函数，方便单元
  测试覆盖 MAX+1 查询。
- `api/trade_plans.py` —— router，**4 个端点**：POST、GET list、GET current、
  GET by revision_no。
- 在 `main.py` 里挂载 `/positions`（最终 URL 前缀
  `/api/positions/{pid}/trade-plans`）。
- `tests/test_trade_plans.py`。
- 后端绿灯后，前端 `npm run codegen` → 重新生成 `frontend/src/api/schema.d.ts`
  并提交。

### 不在范围内

- **revision 上无 PATCH / DELETE。** 严格 append-only —— 见 §1。
- **`revision_no` 重排 / 压缩。** 序列就是历史本身，从不重排。
- **跨 position 查询**（如 "所有 forex position 的当前 plan"）。属于 F5
  dashboard / P12 派生层。
- **无扁平 `/trade-plans` collection。**
- **无 diff 端点**（"revision N 与 N+1 之间变化的字段"）。客户端可自算；
  不过度建设。
- **不限制 strategy_type。**
- **不做 plan 跨字段业务校验。**
- 前端 F3 实现。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/trade_plan.py                  ← 新增
├── services/trade_plans.py                ← 新增
├── api/trade_plans.py                     ← 新增
└── main.py                                ← 修改：include trade_plans.router
backend/tests/test_trade_plans.py          ← 新增
frontend/src/api/schema.d.ts               ← 末尾重新生成
```

命名约定：**schema** 模块单数（`trade_plan.py`，与 `schemas/account.py`、
`schemas/position.py`、`schemas/trade.py` 对齐）；**service** 模块复数
（`services/trade_plans.py`，与 `services/positions.py`、`services/trades.py`
对齐）。`api/` 也是复数。

## 4. Schema 形状（目标）

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TradePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_at: datetime  # 必填 —— 与 created_at 语义不同
    planned_entry: Decimal | None = Field(default=None, gt=0)
    planned_stop_loss: Decimal | None = Field(default=None, gt=0)
    planned_take_profit: Decimal | None = Field(default=None, gt=0)
    target_rr: Decimal | None = Field(default=None, gt=0)
    thesis: str | None = None
    reason: str | None = None
    # 不接受（被 extra="forbid" 拒绝）：
    #   position_id（URL 绑定）、revision_no（服务端分配）、
    #   id（服务端生成）、created_at（服务端管理）


class TradePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    revision_no: int
    effective_at: datetime
    planned_entry: Decimal | None
    planned_stop_loss: Decimal | None
    planned_take_profit: Decimal | None
    target_rr: Decimal | None
    thesis: str | None
    reason: str | None
    created_at: datetime
```

**形状要点。**

- 没有 `TradePlanUpdate`。没有 PATCH 端点，出 Update schema 是死代码。
- `TradePlanCreate` 上的 `extra="forbid"` 守住所有"不接受"字段。客户端塞
  `revision_no` 拿到的 422 报错就是"revision 由服务端编号"的用户态提醒。
- 4 个数字字段相互独立可选；用户可以只填 thesis、或只填 entry+SL ——
  schema 不绑定。
- `effective_at` 创建时**必填**。没有 `default_factory=datetime.utcnow` ——
  F3 UI 默认填 `now()` 只是便利，*合约*的语义是"告诉我这份 plan 何时生效"。

## 5. Service 层接口（`services/trade_plans.py`）

```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.trade_plan import TradePlan


async def allocate_next_revision_no(
    session: AsyncSession, position_id: uuid.UUID
) -> int:
    """返回该 position 的 MAX(revision_no) + 1；首条返回 1。调用方负责在同一
    session/transaction 中用这个 revision_no 插入行。

    并发：`trade_plans` 上的 `UNIQUE (position_id, revision_no)` 是权威的
    串行化器。两个并发 append 算出相同的 next number 时，第二条 INSERT
    会抛 IntegrityError；router 捕获后重试一次，仍失败则抛 503。单用户
    MVP 下这种路径几乎不可达。
    """
    stmt = select(func.max(TradePlan.revision_no)).where(
        TradePlan.position_id == position_id
    )
    current = (await session.execute(stmt)).scalar()
    return 1 if current is None else current + 1
```

整个 service 层面就这一个函数。其他 router 内逻辑（解析 position、归属
校验、按 revision_no 查单条）留在 `api/` 里，因为它们不通用。未来扩展
（比如 P12 用的"当前 plan delta"helper）可以加进这个模块而不动 router。

## 6. 分阶段 plan

三个 sub-phase。每个之后跑 `uv run pytest -q && uv run ruff check . &&
uv run mypy src` —— 基线视前序 phase 而定。**P9 + P10 先于 P11 完成**：
基线 ≈ 243 + 45 = ~288。**P11 紧跟 P8 之后**：基线 = 183。

### P11.1 — Schemas + service helper

**目标。** 类型表面和 revision 分配器就绪；尚无 HTTP。

**任务。**

1. `schemas/trade_plan.py` —— `TradePlanCreate`、`TradePlanRead`。
2. `services/trade_plans.py` —— `allocate_next_revision_no`。
3. service 层单元测试，`tests/test_trade_plans.py`：
   - `test_allocate_next_revision_no_empty_returns_1` —— position 上无
     既存 revision。
   - `test_allocate_next_revision_no_sequential` —— 用裸 INSERT 插 3 条，
     allocator 返回 4。
   - `test_allocate_next_revision_no_isolated_per_position` —— 两个
     position 都在 revision 3 时互不串扰。

**验收。** Schema 可 import；service 单测全绿；尚无 API。

### P11.2 — Router + 4 个端点

**目标。** 4 个端点 HTTP 走通。

**任务。**

1. `api/trade_plans.py` —— 单个 `APIRouter`，`prefix="/positions"`。私有
   helper：

   ```python
   async def _resolve_position(
       session: AsyncSession, user: User, position_id: uuid.UUID
   ) -> Position:
       stmt = select(Position).where(
           Position.id == position_id, Position.user_id == user.id
       )
       pos = (await session.execute(stmt)).scalar_one_or_none()
       if pos is None:
           raise HTTPException(404, "Position not found")
       return pos
   ```

2. **端点。**

   | Method | Path | 行为 |
   |---|---|---|
   | `POST` | `/{pid}/trade-plans` | 解析 position。`revision_no = await allocate_next_revision_no(session, pid)`。插入。如遇 IntegrityError（唯一约束冲突）：重新分配并重试一次；二次失败抛 503 `"concurrent revision allocation failed; please retry"`。返回 201 + `TradePlanRead`。 |
   | `GET` | `/{pid}/trade-plans` | 解析 position。列出该 position 全部修订，**按 `revision_no ASC`** 排序。返回 200 + `list[TradePlanRead]`（可空）。 |
   | `GET` | `/{pid}/trade-plans/current` | 解析 position。取最高 `revision_no` 的行。**无 revision 时返回 404**（"no current plan; append one first"）。返回 200 + `TradePlanRead`。 |
   | `GET` | `/{pid}/trade-plans/{revision_no}` | 解析 position。`revision_no` 是 `int` path 参数。按 `(position_id, revision_no)` 查。**缺失返回 404**。返回 200。 |

3. **路由顺序。** `/current` 一定要挂在 `/{revision_no:int}` **之前**，
   防止 FastAPI 把 `current` 解析成 int。声明 `revision_no: int` 后
   `"current"` 不会匹配，但显式顺序消除疑问。同理 `/current` 可作为定值
   path 路由声明。

4. **closed-position 故意不检查。** §7 用 `test_append_allowed_on_closed_position`
   防回归。

5. **`main.py`** —— 与 `strategy_meta.router` 并列挂载 `trade_plans.router`。
   两个 router 都用 `prefix="/positions"`，路由到不同子路径，FastAPI 合并
   router 树时无冲突。

6. `tests/test_trade_plans.py` —— §7 完整矩阵。

**验收。** 所有 P11 测试绿；完整套件 + ruff + mypy 干净。预期新增
**~30 tests**。

### P11.3 — 回归 + codegen + brief

**目标。** 锁基线；类型推给前端。

**任务。**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` —— 全绿。
2. 前端 codegen。后端跑在 `:8000`，`cd frontend && npm run codegen` →
   应看到 `TradePlanCreate`、`TradePlanRead`；`npm run build` 通过；提交
   `schema.d.ts`。
3. 端到端跑一遍 §8 curl recipe。
4. 写 `review-notes/p11_implementation_brief.md`。

**验收。** 全绿；recipe 通过；brief 入库。

## 7. 测试矩阵

`tests/test_trade_plans.py`，复用 `auth_client`、`second_user_client`、
migrate 过的 tempfile fixture。Helper 至少 seed 一个 open、一个 closed
Position，让 "closed-position-allowed" 类测试有目标可打。

### Service 层测试（无 HTTP）

| 测试 | 校验 |
|---|---|
| `test_allocate_next_revision_no_empty_returns_1` | 首条 revision 基础情形 |
| `test_allocate_next_revision_no_sequential` | 3 条已插入 → 返回 4 |
| `test_allocate_next_revision_no_isolated_per_position` | 另一个 position 的 revision 不会串入 |

### POST `/positions/{pid}/trade-plans`

| 测试 | 校验 |
|---|---|
| `test_create_first_revision_201_revision_no_is_1` | 最小 payload（仅 `effective_at`）→ 201，服务端写 revision_no=1，created_at 已填 |
| `test_create_with_all_fields` | 所有可选字段都回环 |
| `test_create_second_revision_revision_no_is_2` | 顺序分配 |
| `test_create_third_revision_revision_no_is_3` | 继续顺序 |
| `test_create_rejects_position_id_in_body_422` | URL 绑定 |
| `test_create_rejects_revision_no_in_body_422` | 服务端分配 |
| `test_create_rejects_id_in_body_422` | 服务端生成 |
| `test_create_rejects_created_at_in_body_422` | 服务端管理 |
| `test_create_rejects_missing_effective_at_422` | 必填 |
| `test_create_rejects_negative_planned_entry_422` | gt=0 |
| `test_create_rejects_zero_planned_entry_422` | 严格 gt（非 ge） |
| `test_create_rejects_negative_planned_stop_loss_422` | gt=0 |
| `test_create_rejects_negative_planned_take_profit_422` | gt=0 |
| `test_create_rejects_negative_target_rr_422` | gt=0 |
| `test_create_allows_thesis_only` | 只写思路 |
| `test_create_404_unknown_position` | 随机 pid |
| `test_create_404_cross_user` | 别人的 pid → 404（非 403） |
| `test_create_append_allowed_on_closed_position` | 已定 —— closed **不**锁 |
| `test_create_does_not_mutate_position` | 父 position 行不变（updated_at / status 等不动） |

### GET `/positions/{pid}/trade-plans`（list）

| 测试 | 校验 |
|---|---|
| `test_list_empty_returns_empty_array` | 无修订 → 200，[] |
| `test_list_oldest_first` | 按 revision_no ASC 返回 |
| `test_list_isolated_per_position` | 只返回该 position 的 revision |
| `test_list_404_unknown_position` | |
| `test_list_404_cross_user` | |

### GET `/positions/{pid}/trade-plans/current`

| 测试 | 校验 |
|---|---|
| `test_get_current_404_when_no_revisions` | "no current plan; append one first" |
| `test_get_current_returns_latest_after_one` | 返回 revision_no=1 |
| `test_get_current_returns_latest_after_multiple` | 3 次 append 后返回 revision_no=3 |
| `test_get_current_404_cross_user` | |

### GET `/positions/{pid}/trade-plans/{revision_no}`

| 测试 | 校验 |
|---|---|
| `test_get_specific_revision_200` | 按 revision_no path 参数取 |
| `test_get_specific_revision_404_unknown` | 仅有 3 条时请求 revision_no=99 |
| `test_get_specific_revision_404_cross_user` | |
| `test_get_specific_revision_route_does_not_clash_with_current` | `/{pid}/trade-plans/current` 是专属路由；`/{pid}/trade-plans/1` 返回 revision 1；"current" 永不被当作 int 解析 |
| `test_get_specific_revision_422_on_non_int` | `/{pid}/trade-plans/abc` → 422 |

### Append-only 不变量

| 测试 | 校验 |
|---|---|
| `test_no_patch_endpoint` | `client.patch(f".../trade-plans/1", json={...})` → 405 |
| `test_no_delete_endpoint` | `client.delete(f".../trade-plans/1")` → 405 |
| `test_no_root_delete_endpoint` | `client.delete(f".../trade-plans")` → 405 |
| `test_no_patch_on_current` | `client.patch(f".../trade-plans/current")` → 405 |

### Auth

| 测试 | 校验 |
|---|---|
| `test_requires_auth` | 参数化 POST/GET（×3）不带 cookie → 401 |

## 8. 手工验证 reference（完整 P11 走查）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# 注册 + 登录
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"dave@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=dave@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed：account + 一只 forex pair + 一个 forex position
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"FX","broker":"OANDA","account_type":"margin","base_currency":"USD"}' | jq -r .id)
# EURUSD forex instrument（kind/symbol 的精确形态以你的 instruments router
# 为准；这里仅作示意）：
PAIR=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"forex","symbol":"EURUSD","currency":"USD","forex_pair":{"base_currency":"EUR","quote_currency":"USD"}}' | jq -r .id)
POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$PAIR\",\"strategy_type\":\"spot_forex\",\"opened_at\":\"2026-06-01T08:00:00Z\"}" | jq -r .id)

# 1) 空 GET current → 404 + detail
curl -sSi "$BASE/api/positions/$POS/trade-plans/current" -b "$JAR"

# 2) Append revision 1 —— 初始 thesis + 各档位
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{
    "effective_at":"2026-06-01T08:00:00Z",
    "planned_entry":"1.0850",
    "planned_stop_loss":"1.0800",
    "planned_take_profit":"1.0950",
    "target_rr":"2",
    "thesis":"周线阻力被突破后回踩，确认为支撑。"
  }'

# 3) Append revision 2 —— 触及 +1R 后将 SL 上移到保本
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{
    "effective_at":"2026-06-03T14:30:00Z",
    "planned_entry":"1.0850",
    "planned_stop_loss":"1.0850",
    "planned_take_profit":"1.0950",
    "target_rr":"2",
    "reason":"+1R 后 SL 上移到 BE。"
  }'

# 4) GET current → revision 2
curl -fsS "$BASE/api/positions/$POS/trade-plans/current" -b "$JAR" | jq

# 5) List → oldest first
curl -fsS "$BASE/api/positions/$POS/trade-plans" -b "$JAR" | jq '[.[] | {revision_no, planned_stop_loss, reason}]'

# 6) GET 指定 revision
curl -fsS "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR" | jq

# 7) 在已 CLOSED 的 position 上 append → 仍 201（已定决策）
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-10T18:00:00Z"}'
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"effective_at":"2026-06-10T18:00:00Z","reason":"复盘：一次 SL 调整后吃到 TP。下次复用该套路。"}'

# 8) PATCH 与 DELETE 全部 405
curl -sSi -X PATCH "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"reason":"oops"}'
curl -sSi -X DELETE "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR"

# 9) 客户端尝试塞 revision_no → 422
curl -sSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"effective_at":"2026-06-11T00:00:00Z","revision_no":42}'
```

## 9. 实施者快速开始

```bash
cd backend
# 按 P11.1 → P11.2 → P11.3 推进，每步后：
uv run pytest -q && uv run ruff check . && uv run mypy src

# 手工跑 API 验证：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

P11 落地后，F3 前端那一面（Position 详情页 = Overview + Meta + Plan +
Trades-placeholder）从后端侧完全解锁。下一道后端门是 **P12**（派生读层），
跨 position 聚合 Trade 行供 dashboard 使用。

## 10. 面向未来的注记（不要实现，只是不要堵死）

- **Diff 端点**（`GET /positions/{pid}/trade-plans/diff?from=1&to=2`）。
  完全可以由客户端从 `TradePlanRead` 自行算出来；UI 需求未明确前不上
  服务端端点。
- **跨 position 的"当前 plan"列表**（比如 F5 dashboard "所有 open 的
  forex position 及它们的当前 SL/TP"）。属于 P12 派生读层；不要回头
  改 P11。
- **revision 上的软删除。** P11 不引入（严格 append-only）。如果未来真
  出现"这条 revision 是错的、不要展示"的审计需求，最干净的路径是再加
  一个 `hidden` flag 列，而不是塞 DELETE 语义。append-only 保持神圣。
- **`revision_no` 压缩 / 重排。** 永远不。序列即历史；因为不存在 DELETE，
  所以也不会出现 gap。
- **并发增强。** 单用户 MVP 让唯一约束重试路径几乎不可达。如果 P11 真
  遇到多用户场景（比如 broker import job 并发写？），用
  `SERIALIZABLE` 事务或对父 Position 加行级锁来替代"重试一次"。
- **校验钩子**（比如多头/空头方向的 entry/SL/TP 一致性）—— 可以作为
  `services/trade_plans.py` 的 helper 在 POST 时调用。本期不做，因为
  方向并不在 Position 上编码。

---

## Changelog

- **v0.1（2026-05-26）** —— P11 初版实施 plan。与用户敲定三个 P11
  子决策：(1) `revision_no` 由服务端按 `MAX+1` 分配（客户端不能传）；
  (2) **严格 append-only** —— 无 PATCH、无 DELETE；revision 永久保留，
  纠错走 append；(3) GET list 默认 oldest-first（revision 1 → N）
  以契合事件流阅读顺序。按惯例继承：嵌套 sub-resource URL
  `/positions/{pid}/trade-plans/...`、closed-position **不**锁（沿用
  P10）、不限制 `strategy_type`（data-model §5.5 说"主用 forex"但
  没限制）、Owner-scoped via Position + 跨用户 404。三个 sub-phase：
  P11.1 schemas + service helper（仅一个函数：`allocate_next_revision_no`）、
  P11.2 router + 4 个端点（POST + GET list + GET current + GET by
  revision_no）、P11.3 回归 + codegen + brief。无新 migration —— 表自
  `0001_initial_schema` 起就在，含 `UNIQUE (position_id, revision_no)`
  约束，allocator 直接靠它。`services/trade_plans.py` 加入
  `services/positions.py` / `services/trades.py` /
  `services/strategy_meta.py` 行列。P11 不对宏观 §6 做任何修订——
  子决策都是 P11 内部的。
