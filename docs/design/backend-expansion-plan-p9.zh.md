# 后端 Phase P9 — Trade CRUD（实施 plan）

**语言：** [English](./backend-expansion-plan-p9.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-26）。来自宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 中 **P9** 的详细
> 实施 plan。自包含——实施者可直接执行。配套：
> [data-model.zh.md §4.5](./data-model.zh.md#45-trade-atomic-event)（Trade 字段 +
> §4.5.2 Notion 事件 → atomic Trade 映射）、刚交付的
> [backend-expansion-plan-p8.zh.md](./backend-expansion-plan-p8.zh.md)（Position
> CRUD + 本 plan 继续使用的 `services/positions.py` 接缝）、**StrategyConfig 模板**
> （`api/strategy_configs.py` + `tests/test_strategy_configs.py`），以及
> [backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)
> 的已定决策汇总。

## 1. 目的与上下文

把已经迁移好的 `trades` 表变成带类型的 CRUD API：原子级别的 broker fill，是用户
日常录入的主战场。P9 是后端剩下的单体最大门槛——它解锁 F4（Trade 录入），并通过
P8 settled 的 Trade-led Position 模型，让 F3 的内联 Position 创建流真正诚实起来。
P9 同时把 P8 的 `freeze_pnl_realized()` 验证盲区补上——以前只能在 sum=0 的退化
路径上验，等 P9 的 Trade 行落地后求和路径才被真实数据 exercise。

P9 ship 一个小的 DB migration（`Trade.archived_at`），一个 service 模块
（`services/trades.py`，承载 `cash_flow` 公式和 action↔kind 守卫），一个同时接受
单行和多行提交的 router，以及一份对齐 §4.5.2 Notion 事件词汇表的测试套件。

### 已定决策（不要重新推导）

下列条目是
[backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)
④（Trade 校验）在 P9 的子级展开，2026-05-26 与用户敲定。哪几条修订宏观 §6④ 会
明确注明。

- **Owner-scoped via Position。** Trade 没有直接 `user_id`；归属经
  `position.user_id` 流通。每个端点先解析 Position；跨用户 `position_id` → **404**
  （与 P6/P7/P8 一致——避免信息泄露）。
- **`account_id` 服务端派生。** 创建时从 `position.account_id` 复制；**不**接受
  客户端传入。data-model §4.5 的去规范化不变量（"Denormalized; matches
  position.account_id"）由代码保证，不是靠信任。
- **`price >= 0`（修订宏观 §6④）。** 原 §6④ 写的是 `price > 0`。data-model §4.5.2
  *要求* worthless expire / assignment / exercise 的期权 close 腿 `price = 0.00`
  （这就是 broker 的真实成交）。严格按 `> 0` 会拒绝这些流程。P9 enforce
  `price >= 0`；正负号仍完全由 `cash_flow` 经 action 符号承担。**P9.3 任务：
  在 `backend-expansion-plan.md` 和 `.zh.md` 双语 §6④ 都修订，并各加一行
  changelog。**
- **`cash_flow` 服务端计算。** 公式照宏观 §6④：
  ```
  cash_flow = sign(action) × price × quantity × multiplier
              − commission − fees
  其中 sign(action) = -1 对应 buy / bto / btc,
                      +1 对应 sell / sto / stc,
        multiplier  = 期权时取 OptionContract.multiplier,
                    = 其他情况取 1。
  ```
  `TradeCreate` **不**包含 `cash_flow`。客户端在 POST body 里塞这个字段 → 422
  `extra_forbidden`。
- **`action ↔ instrument.kind` 一致性。** `bto / sto / btc / stc` ⇒
  `kind == option`；`buy / sell` ⇒ `kind in (stock, forex)`。服务端先解析
  Instrument 再校验。不匹配 → **422**。
- **数量规则。**
  - `quantity > 0` 总是成立。
  - 期权（`instrument.kind == option`）：**必须整数**（Decimal 强制后
    `quantity % 1 == 0`）。没有"分数合约"这种东西。
  - 股票 / 外汇：允许小数（碎股 + 外汇微手）。
  - 正数校验放在 Pydantic 层（`gt=0`）；整数约束放在 service 层（需要先解析 Instrument）。
- **费用字段默认值。** `commission` 与 `fees` 客户端省略时默认 `Decimal("0")`；
  二者均 `>= 0`（Pydantic `ge=0`）。
- **多腿 POST = 单端点同时接受单对象或数组。** `POST /trades` 的 body 既可以是
  一个 `TradeCreate` 对象，也可以是非空的 `TradeCreate` 列表。**数组规则：**
  - 所有行的 `position_id` 必须**一致**（否则 422）。
  - 客户端在任一行提供 `order_group_id`，则**所有行**必须一致（否则 422）；
    多行提交时若全部未提供，服务端**自动生成一个新的 UUID** 并赋给所有行。
  - 单行提交：`order_group_id` 默认 NULL，除非客户端显式提供。
  - 原子事务——任一行校验失败，全部回滚。
  - 响应：201 + 一个 JSON 数组，保留提交顺序，**单行提交也返回长度 1 的数组**
    （客户端无需对响应形状做分支）。
- **审计友好的软删除（新 migration）。** Trade 通过 `0002_trade_archived_at.py`
  增加 `archived_at: timestamptz nullable, indexed`。`DELETE /trades/{id}` 把
  `archived_at` 设为 `now()`，返回 204。list 默认过滤已归档行。
  **`?include_archived=true`** 主动开关把归档行也带出来，供审计视图使用。
- **Trade 其余字段全部 immutable。** `PATCH /trades/{id}` 仅允许修改 `notes`。
  body 中任何其他字段 → 422 `extra_forbidden`。要修正数字数据，用户必须 DELETE
  （= 归档）该行后 POST 一笔新的替代 Trade。理由：审计安全 + MVP 内零 `cash_flow`
  重算分支。
- **Closed-position 锁死。** 当父级 `Position.status == "closed"` 时，对该
  Position 下任意 Trade 的 `POST` / `PATCH` / `DELETE` → **409**，detail
  `"parent position is closed; trades on closed positions are immutable"`。
  与 P8 拒绝 reopen 的精神一致：冻结的东西保持冻结。
- **Position-DELETE 兼容性（P8 代码不变）。** P8 的"无 attached trades"检查
  计入**所有** Trade 行，包括归档行。把所有 Trade 归档**不会**解锁
  `DELETE /positions/{id}`——保留审计不变量。若未来要放开，只需一处 filter，
  详见 §10。
- **`broker_trade_id` 在 P9 不暴露。** P9 的 Trade 全是手工录入；该列保持 NULL。
  未来的 PX 整合阶段可以加性地把它暴露到 `TradeRead`、并在 import-only 端点上接受
  传入。
- **Trade 事件不触发 Position auto-close。** Position 自动平仓（净 qty → 0 即
  closed）仍是 P12 / `services/positions.py::detect_auto_close` 的职责。P9 的
  POST/PATCH/DELETE **不会**变更 Position 状态。

## 2. 范围

### 本 plan 之内

- `alembic/versions/0002_trade_archived_at.py` — 给 `trades` 加 `archived_at`；
  新列上建索引。
- `schemas/trade.py` — `TradeCreate` / `TradeUpdate` / `TradeRead`；POST body
  的单对象/列表 type alias。
- `services/trades.py` — `compute_cash_flow()`、`validate_action_kind()`、
  `validate_option_quantity_integer()`、`resolve_multiplier()`、
  `create_trades_atomic()`（原子事务下批量插入一行或多行）。
- `api/trades.py` — router：`POST /trades`、`GET /trades`、`GET /trades/{id}`、
  `PATCH /trades/{id}`、`DELETE /trades/{id}`。
- `main.py` 挂载 `/trades`（最终 URL 前缀 `/api/trades`）。
- `tests/test_trades.py` — 完整覆盖 §7 矩阵。
- 后端绿灯后，重新生成 `frontend/src/api/schema.d.ts`。
- **文档修订**：把宏观 `backend-expansion-plan.md` §6④ 的 `price > 0` 改为
  `price >= 0`（+ `.zh.md`），并在双文件 changelog 里各加一行。

### 不在范围内

- Position auto-close 检测（P12 / `services/positions.py` 桩位）。
- **可变的数字字段**。P9 不写 `cash_flow` 重算逻辑。
- `broker_trade_id` API surface（PX External Integrations）。
- 策略元扩展（P10）与 TradePlan（P11）。
- P8 `freeze_pnl_realized` 之外的 Trade 行聚合（比如未平仓的 running PnL）—— P12。
- `GET /trades` 分页（与 Account / Position MVP 一致——等行数到了再加）。
- 前端 F4 实施（见 `frontend-expansion-plan.md`）。
- "全部 Trade 归档后允许 Position-DELETE"——保留 P8 当前不变量。

## 3. 文件

```
backend/alembic/versions/0002_trade_archived_at.py    ← 新增 migration
backend/src/trading_journal/
├── schemas/trade.py                                  ← 新增
├── services/trades.py                                ← 新增
├── api/trades.py                                     ← 新增
└── main.py                                           ← 修改：include trades.router
backend/tests/test_trades.py                          ← 新增
frontend/src/api/schema.d.ts                          ← 末尾重新生成
docs/design/backend-expansion-plan.md                 ← 修订 §6④ + changelog
docs/design/backend-expansion-plan.zh.md              ← 镜像修订
```

`services/` 包在 P8 已经存在（`services/positions.py` + `services/__init__.py`）。
P9 只是再加一个模块。

## 4. Schema 形状（目标）

```python
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import TradeAction


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)            # 见 §1 对宏观 §6④ 的修订
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    executed_at: datetime
    order_group_id: uuid.UUID | None = None
    notes: str | None = None
    # 不接受：account_id（服务端派生）、cash_flow（服务端计算）、
    # broker_trade_id（PX）、archived_at（服务端管理）、id（服务端生成）


class TradeUpdate(BaseModel):
    """Trade 其余字段全部 immutable —— 只允许修改 `notes`。

    任何其他数字 / 结构字段都会被 `extra="forbid"` 拒绝。要修正数字，
    走 DELETE（=归档）+ POST 一笔新的替代 Trade。
    """
    model_config = ConfigDict(extra="forbid")

    notes: str | None = None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    account_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal
    price: Decimal
    commission: Decimal
    fees: Decimal
    cash_flow: Decimal
    executed_at: datetime
    order_group_id: uuid.UUID | None
    broker_trade_id: str | None
    notes: str | None
    archived_at: datetime | None


# POST body 判别器 —— 在 router 层用 TypeAlias：
TradeCreatePayload = TradeCreate | list[TradeCreate]
```

**形状要点。**

- 写入 schema 上的 `extra="forbid"` 意味着客户端塞 `cash_flow`、`account_id`、
  `broker_trade_id`、`archived_at`、`id` 都会被 422 拒绝并指出具体字段。绝不静默吞掉。
- `quantity: Field(gt=0)` 守正数；**期权整数规则**在 `services/trades.py` 里
  解析 Instrument 之后执行。
- `commission` / `fees` 默认 `Decimal("0")` —— 客户端可省略；契合手工录入"没有
  手续费档？空着就行"的人体工学。
- `TradeRead` 包含 `archived_at`，方便审计视图渲染；过滤归档行的客户端只需判断
  `archived_at is None`。
- POST 单对象 / 数组的二态**不**通过 Pydantic 判别 union 表达（FastAPI 原生支持
  `body: TradeCreate | list[TradeCreate]`）。router 层内部统一规范化为
  `list[TradeCreate]`。

## 5. Service 层接口（`services/trades.py`）

```python
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, TradeAction
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade


_SELL_SIDE_ACTIONS = {TradeAction.SELL, TradeAction.STO, TradeAction.STC}
_OPTION_ACTIONS = {TradeAction.BTO, TradeAction.STO, TradeAction.BTC, TradeAction.STC}
_NONOPTION_ACTIONS = {TradeAction.BUY, TradeAction.SELL}


def compute_cash_flow(
    action: TradeAction,
    price: Decimal,
    quantity: Decimal,
    multiplier: int,
    commission: Decimal,
    fees: Decimal,
) -> Decimal:
    """带符号的净现金影响（宏观 §6④）。

    sign = -1 对 buy/bto/btc，+1 对 sell/sto/stc；期权 multiplier 取
    OptionContract.multiplier，否则取 1。commission / fees 无论方向都扣减
    （它们总是花钱）。
    """
    sign = Decimal(1) if action in _SELL_SIDE_ACTIONS else Decimal(-1)
    gross = sign * price * quantity * Decimal(multiplier)
    return gross - commission - fees


def validate_action_kind(action: TradeAction, kind: InstrumentKind) -> None:
    """action ↔ kind 不匹配时抛 ValueError；router 转 422。"""
    if action in _OPTION_ACTIONS and kind is not InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires an option instrument, "
            f"got '{kind.value}'"
        )
    if action in _NONOPTION_ACTIONS and kind is InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires a stock or forex instrument, "
            f"got 'option'"
        )


def validate_option_quantity_integer(
    action: TradeAction, kind: InstrumentKind, quantity: Decimal
) -> None:
    """期权必须按整数合约数交易。"""
    if kind is InstrumentKind.OPTION and quantity % 1 != 0:
        raise ValueError(
            f"option quantity must be an integer number of contracts, got {quantity}"
        )


async def resolve_multiplier(
    session: AsyncSession, instrument: Instrument
) -> int:
    """期权返回 `OptionContract.multiplier`；其他返回 1。"""
    if instrument.kind is not InstrumentKind.OPTION:
        return 1
    contract = await session.get(OptionContract, instrument.id)
    if contract is None:
        # 数据一致的情况下永远不该发生，但做防御。
        raise ValueError(
            f"instrument {instrument.id} is kind=option but has no OptionContract row"
        )
    return contract.multiplier


async def create_trades_atomic(
    session: AsyncSession,
    position: Position,
    rows: list["TradeCreate"],
) -> list[Trade]:
    """逐行校验、计算 cash_flow、原子插入。事务提交由调用方负责。任意行
    校验失败 → 抛 ValueError（router 转 422）。"""
    # 具体实现见 §6 P9.2
```

为什么用 service 模块而不是把代码堆进 router：cash_flow 公式只活在**一个地方**，
P12 派生层重建归档前历史时可以直接调 `compute_cash_flow`，测试套件也能在 HTTP
层之外单独覆盖公式的边界条件（期权 `multiplier`、worthless expire 的
`price=0`、sell side 符号）。

## 6. 分阶段 plan

三个 sub-phase。每个之后都跑 `uv run pytest -q && uv run ruff check . &&
uv run mypy src` —— 基线是 P8 完成后的 **183 tests**。

### P9.1 — Migration + schemas + service 模块

**目标。** 持久层和纯函数层就绪；尚无 HTTP。

**任务。**

1. **Migration `0002_trade_archived_at.py`。**
   ```python
   def upgrade() -> None:
       with op.batch_alter_table("trades", schema=None) as batch_op:
           batch_op.add_column(
               sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
           )
           batch_op.create_index(
               batch_op.f("ix_trades_archived_at"), ["archived_at"], unique=False
           )

   def downgrade() -> None:
       with op.batch_alter_table("trades", schema=None) as batch_op:
           batch_op.drop_index(batch_op.f("ix_trades_archived_at"))
           batch_op.drop_column("archived_at")
   ```
   `models/trade.py` 上加 `archived_at: Mapped[datetime | None]`。
2. **`schemas/trade.py`** —— §4 的三个类。
3. **`services/trades.py`** —— `compute_cash_flow`、`validate_action_kind`、
   `validate_option_quantity_integer`、`resolve_multiplier`、
   `create_trades_atomic`。`create_trades_atomic` 主体：
   - 逐行 `instrument = await session.get(Instrument, row.instrument_id)`；
     missing → 422 风格的错误。
   - `validate_action_kind(row.action, instrument.kind)`。
   - `validate_option_quantity_integer(row.action, instrument.kind, row.quantity)`。
   - `multiplier = await resolve_multiplier(session, instrument)`。
   - `cash_flow = compute_cash_flow(...)`。
   - 把 `Trade(...)` 攒进 buffer；末尾 `session.add_all(buffer)`。
   - `flush()`，让调用方能 `refresh()` 读回。
4. **单元测试**（暂时无 HTTP），`tests/test_trades.py`：
   - `test_compute_cash_flow_buy_stock` —— `-price*qty - commission - fees`。
   - `test_compute_cash_flow_sell_stock` —— `+price*qty - commission - fees`。
   - `test_compute_cash_flow_sto_option_multiplier_100` —— 符号 + multiplier。
   - `test_compute_cash_flow_btc_at_zero_price_worthless_expire` —— 只扣
     commission + fees（≤ 0）。
   - `test_compute_cash_flow_btc_at_zero_price_zero_costs_equals_zero`。
   - `test_validate_action_kind_*` —— 期权 ↔ 期权、股票 ↔ 股票 OK；不匹配抛。
   - `test_validate_option_quantity_integer_*` —— 分数期权抛；分数股票 OK；
     整数永远 OK。

**验收。** Migration 干净应用（`alembic upgrade head`）；schema 可 import；
service 单测全绿；尚无 API surface。

### P9.2 — Router：POST / GET / PATCH / DELETE

**目标。** HTTP 层全 CRUD 走通，含多腿数组提交。

**任务。**

1. **`api/trades.py`** —— router 挂在 `/trades`。私有 helper：
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

   async def _get_owned_trade(
       session: AsyncSession, user: User, trade_id: uuid.UUID
   ) -> Trade:
       # 经 Position 关联做归属判定。
       stmt = (
           select(Trade)
           .join(Position, Trade.position_id == Position.id)
           .where(Trade.id == trade_id, Position.user_id == user.id)
       )
       trade = (await session.execute(stmt)).scalar_one_or_none()
       if trade is None:
           raise HTTPException(404, "Trade not found")
       return trade
   ```

2. **端点。**

   | Method | Path | 行为 |
   |---|---|---|
   | `POST` | `""` | body 为 `TradeCreate \| list[TradeCreate]`。规范化为 list。校验"所有行 `position_id` 一致"。解析 position（owner + 必须 open，否则 409）。按 §1 处理 `order_group_id`。调用 `services.create_trades_atomic`。提交。返回 201 + `list[TradeRead]`。 |
   | `GET` | `""` | 经 Position join 实现 owner-scoped。query 参数：`position_id`（可选 UUID）、`order_group_id`（可选 UUID）、`include_archived`（bool，默认 false）。排序：`executed_at DESC, id ASC`。 |
   | `GET` | `"/{id}"` | 单条，owner-scoped（归档行也能按 id 取——审计详情视图）。跨用户 / missing → 404。 |
   | `PATCH` | `"/{id}"` | 仅允许 `notes`（`extra="forbid"` 守住）。父 Position closed → 409。已归档 → 409 `"cannot modify an archived trade"`。 |
   | `DELETE` | `"/{id}"` | 父 Position closed → 409。已归档 → 404。否则 `archived_at = func.now()`。204。 |

3. **POST 规范化 helper。**
   ```python
   def _normalize_payload(
       body: TradeCreate | list[TradeCreate],
   ) -> tuple[list[TradeCreate], bool]:
       """返回 (rows, was_array)。空数组 → 422。"""
       if isinstance(body, list):
           if not body:
               raise HTTPException(422, "trade array must be non-empty")
           return body, True
       return [body], False
   ```

4. **POST 跨行校验。**
   ```python
   # 所有行的 position_id 必须一致。
   distinct_positions = {row.position_id for row in rows}
   if len(distinct_positions) > 1:
       raise HTTPException(
           422, "all rows in a multi-leg POST must share the same position_id"
       )

   # order_group_id：任一行提供则全部必须一致。
   supplied_ogids = {row.order_group_id for row in rows if row.order_group_id}
   if len(supplied_ogids) > 1:
       raise HTTPException(
           422, "rows in a multi-leg POST must share order_group_id"
       )
   if supplied_ogids:
       group_id = supplied_ogids.pop()
   elif was_array and len(rows) > 1:
       group_id = uuid.uuid4()
   else:
       group_id = None  # 尊重单行未提供时的 NULL 默认
   # 应用到每一行（单行未提供时 group_id 为 None，没问题）。
   for row in rows:
       row.order_group_id = group_id
   ```

5. **POST closed-position 守卫。**
   ```python
   position = await _resolve_position(session, user, rows[0].position_id)
   if position.status is PositionStatus.CLOSED:
       raise HTTPException(
           409,
           "parent position is closed; trades on closed positions are immutable",
       )
   ```
6. **`account_id` 去规范化** —— 在 `create_trades_atomic` 内构造每一行时从
   `position.account_id` 写入。
7. **`main.py`** —— 把 `trades.router` 紧挨 `positions.router` 之后挂载。
8. **`tests/test_trades.py`** —— 见 §7 完整矩阵。

**验收。** 全部 P9 测试绿；完整套件 + ruff + mypy 干净。预期总数：
**183（P8）+ ~60 P9 ≈ ~243**。

### P9.3 — 回归、codegen、文档修订、brief

**目标。** 锁基线；类型推给前端；落地宏观 plan 的修订。

**任务。**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` —— 全绿。
2. **修订宏观 §6④。** 把 `docs/design/backend-expansion-plan.md` §6 第 4 条
   的 `price > 0 always (per-unit fill price...)` 改成 `price >= 0 always
   (per-unit fill price; sign lives entirely in cash_flow via the action
   sign — see data-model §4.5.2 for worthless-expire / assignment flows
   that legitimately use price=0)`。`.zh.md` 同步。两个文件 changelog 各加一行：
   `"P9 v0.1 (2026-05-26): price > 0 → price >= 0 to honor data-model §4.5.2
   broker-fill semantics."`
3. **前端 codegen。** 后端跑在 `:8000`，
   `cd frontend && npm run codegen` → 应当看到 `TradeCreate`、`TradeUpdate`、
   `TradeRead` 出现；`npm run build` 通过；提交 `schema.d.ts`。
4. 端到端跑一遍 §8 curl recipe。
5. 写 `review-notes/p9_implementation_brief.md`（参照 P6/P7/P8 brief 的风格）。

**验收。** 全绿；文档修订入库；recipe 通过；brief 入库。

## 7. 测试矩阵

`tests/test_trades.py`，复用 `auth_client`、`second_user_client` 以及
`conftest.py` 里 migrate 过的 tempfile fixture。再补一个 helper 在干净 DB 里
seed `Account` + `Instrument`（含一只样本 OptionContract）+ open 状态的
`Position` —— 仿照 positions 测试已有的写法。

### Service 层测试（无 HTTP）

| 测试 | 校验 |
|---|---|
| `test_compute_cash_flow_buy_stock` | sign=-1, multiplier=1 |
| `test_compute_cash_flow_sell_stock` | sign=+1, multiplier=1 |
| `test_compute_cash_flow_sto_option_x100` | sign=+1, multiplier=100 |
| `test_compute_cash_flow_btc_at_zero_price` | gross=0, 返回 -(commission+fees) |
| `test_compute_cash_flow_costs_subtracted_on_both_sides` | sell 侧仍扣费 |
| `test_validate_action_kind_option_ok` | option 上 bto → 通过 |
| `test_validate_action_kind_stock_ok` | stock 上 buy → 通过 |
| `test_validate_action_kind_bto_on_stock_raises` | 不匹配 |
| `test_validate_action_kind_buy_on_option_raises` | 不匹配 |
| `test_validate_option_quantity_integer_fractional_raises` | option qty 1.5 → 抛 |
| `test_validate_option_quantity_integer_stock_fractional_ok` | stock qty 0.5 → OK |

### POST `/trades`（单笔）

| 测试 | 校验 |
|---|---|
| `test_create_single_stock_buy_201` | 最小 payload → 201，数组长度 1；`cash_flow = -price*qty - costs`；`account_id` 由 position 派生；`order_group_id` 为 null |
| `test_create_single_stock_sell_cash_flow_positive` | 符号反向 |
| `test_create_single_option_sto_uses_multiplier` | cash_flow 含 ×100 |
| `test_create_with_supplied_order_group_id` | 服务端尊重客户端值 |
| `test_create_rejects_unknown_position_404` | 不存在的 position_id |
| `test_create_rejects_other_users_position_404` | 跨用户 → 404 |
| `test_create_rejects_unknown_instrument_422` | 不存在的 instrument_id |
| `test_create_rejects_action_kind_mismatch_422` | stock 上 bto |
| `test_create_rejects_buy_on_option_422` | option 上 buy |
| `test_create_rejects_fractional_option_qty_422` | option qty 1.5 |
| `test_create_allows_fractional_stock_qty` | 0.25 股 OK |
| `test_create_rejects_negative_quantity_422` | Pydantic gt=0 |
| `test_create_rejects_zero_quantity_422` | gt=0（非 ge=0） |
| `test_create_rejects_negative_price_422` | Pydantic ge=0 |
| `test_create_allows_zero_price_for_btc` | worthless-expire 流 |
| `test_create_allows_zero_price_for_stc` | exercise/expire long-leg 流 |
| `test_create_rejects_negative_commission_422` | ge=0 |
| `test_create_rejects_negative_fees_422` | ge=0 |
| `test_create_rejects_account_id_in_body_422` | 服务端派生 |
| `test_create_rejects_cash_flow_in_body_422` | 服务端计算 |
| `test_create_rejects_broker_trade_id_in_body_422` | PX 才暴露 |
| `test_create_rejects_archived_at_in_body_422` | 服务端管理 |
| `test_create_409_when_position_closed` | 父 closed → 409 含 detail |

### POST `/trades`（数组 / 多腿）

| 测试 | 校验 |
|---|---|
| `test_create_array_4leg_ic_open_201` | 4 行共享自动生成的 order_group_id；每行 cash_flow 正确；account_id 派生 |
| `test_create_array_2leg_assignment_short_put` | btc put @ 0.00 + buy 股 @ strike；两行都落盘 |
| `test_create_array_with_supplied_shared_ogid` | 服务端尊重客户端 UUID |
| `test_create_array_rejects_mixed_position_id_422` | position_id 必须一致 |
| `test_create_array_rejects_mixed_ogid_422` | 客户端给的 ogid 必须一致 |
| `test_create_array_rejects_one_row_fails_422_rollback` | 第 3 行非法 → 4 行全部回滚；DB 无残留 |
| `test_create_array_rejects_empty_422` | 空数组 |
| `test_create_array_409_when_position_closed` | 一次拒绝覆盖全部 |
| `test_create_array_returns_in_submit_order` | 响应保留入参顺序 |

### GET `/trades`（list）

| 测试 | 校验 |
|---|---|
| `test_list_default_excludes_archived` | 默认不返回归档行 |
| `test_list_include_archived_true_shows_them` | `?include_archived=true` |
| `test_list_filter_position_id` | 正确 scope |
| `test_list_filter_order_group_id` | 只返回 IC 的 4 条腿 |
| `test_list_filter_combined` | position_id + order_group_id |
| `test_list_unfiltered_returns_all_user_trades` | 跨 position |
| `test_list_cross_user_isolation` | 别人的行看不到 |
| `test_list_orders_executed_at_desc` | 新 → 旧 |
| `test_list_rejects_bad_uuid_422` | 非法 query 值 |

### GET `/trades/{id}`

| 测试 | 校验 |
|---|---|
| `test_get_200` | 自己的行 |
| `test_get_returns_archived_row` | 归档行仍可按 id 拿（审计） |
| `test_get_404_unknown` | 随机 UUID |
| `test_get_404_cross_user` | 别人的 id → 404（不是 403） |

### PATCH `/trades/{id}`

| 测试 | 校验 |
|---|---|
| `test_patch_notes_200` | notes 基本改 |
| `test_patch_notes_to_null_200` | 清空 notes |
| `test_patch_rejects_quantity_change_422` | extra_forbidden |
| `test_patch_rejects_price_change_422` | extra_forbidden |
| `test_patch_rejects_action_change_422` | extra_forbidden |
| `test_patch_rejects_cash_flow_change_422` | extra_forbidden |
| `test_patch_rejects_position_id_change_422` | extra_forbidden |
| `test_patch_rejects_account_id_change_422` | extra_forbidden |
| `test_patch_rejects_archived_at_change_422` | extra_forbidden |
| `test_patch_409_when_position_closed` | 父 closed |
| `test_patch_409_when_already_archived` | "cannot modify an archived trade" |
| `test_patch_404_cross_user` | |
| `test_patch_does_not_change_cash_flow` | 只改 notes 不动 cash_flow |

### DELETE `/trades/{id}`

| 测试 | 校验 |
|---|---|
| `test_delete_204_sets_archived_at` | 行仍在，`archived_at` 被填上 |
| `test_delete_list_default_excludes_after_delete` | 默认 list 看不到 |
| `test_delete_get_by_id_still_works_after_delete` | 详情读得到（审计） |
| `test_delete_404_already_archived` | 第二次 DELETE → 404 |
| `test_delete_409_when_position_closed` | 父 closed |
| `test_delete_404_cross_user` | |
| `test_delete_does_not_unlock_position_delete` | 行归档后 DELETE position 仍 409 |

### 跨 data-model §4.5.2 流的 cash-flow 正确性（集成）

证明 §4.5.2 映射表能被忠实实现。

| 测试 | Notion 事件 | 校验 |
|---|---|---|
| `test_flow_sell_put` | sell put | 1 行 `sto` put，cash_flow > 0 |
| `test_flow_close_sell_put` | close sell put | 1 行 `btc` put，cash_flow < 0 |
| `test_flow_assignment_short_put` | assignment | 2 行共享 ogid，`btc` @ 0 + `buy` 100 @ strike；总 cash_flow 正确 |
| `test_flow_worthless_expire_short_option` | expire | 1 行 `btc` @ 0，commission 0、fees 0 → cash_flow == 0 |
| `test_flow_iron_condor_open` | open IC | 4 行共享 ogid，净收 credit > 0 |

### Auth

| 测试 | 校验 |
|---|---|
| `test_requires_auth` | 参数化 POST/GET/PATCH/DELETE 不带 cookie → 401 |

## 8. 手工验证 reference（完整 P9 走查）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# 注册 + 登录
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=bob@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed：account + 股票 instrument + position
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)
STOCK=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)
POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$STOCK\",\"strategy_type\":\"spot_stock\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 1) 单笔 buy → 201，cash_flow = -100*150 - 1 - 0 = -15001
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"buy\",\"quantity\":\"100\",\"price\":\"150.00\",\"commission\":\"1.00\",\"executed_at\":\"2026-06-01T14:30:00Z\"}"

# 2) 数组多腿（合成的 2 行"分批 sell"）→ 201，共享自动生成的 order_group_id
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "[
    {\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"sell\",\"quantity\":\"50\",\"price\":\"160.00\",\"executed_at\":\"2026-06-10T18:00:00Z\"},
    {\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"sell\",\"quantity\":\"50\",\"price\":\"161.00\",\"executed_at\":\"2026-06-10T18:00:01Z\"}
  ]"

# 3) 期权 worthless expire 流（前提是你也建好了 option instrument；这里省略——
#    recipe 形态对齐 §7 的 test_flow_worthless_expire_short_option）。

# 4) PATCH notes → 200
TID=$(curl -fsS "$BASE/api/trades?position_id=$POS" -b "$JAR" | jq -r '.[0].id')
curl -fsSi -X PATCH "$BASE/api/trades/$TID" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"首笔建仓。"}'

# 5) PATCH notes 之外的字段 → 422
curl -fsSi -X PATCH "$BASE/api/trades/$TID" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"quantity":"200"}'

# 6) DELETE（归档）→ 204；默认 list 看不到
curl -fsSi -X DELETE "$BASE/api/trades/$TID" -b "$JAR"
curl -fsS "$BASE/api/trades?position_id=$POS" -b "$JAR" | jq 'length'
curl -fsS "$BASE/api/trades?position_id=$POS&include_archived=true" -b "$JAR" | jq 'length'

# 7) 把 position 关掉（参 P8 §8）；之后任何 trade 写操作 → 409
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-15T20:00:00Z"}'
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"buy\",\"quantity\":\"1\",\"price\":\"1\",\"executed_at\":\"2026-06-20T14:00:00Z\"}"
```

## 9. 实施者快速开始

```bash
cd backend
uv run alembic upgrade head   # P9.1 落地后跑一次
# 按 P9.1 → P9.2 → P9.3 顺序推进，每步后：
uv run pytest -q && uv run ruff check . && uv run mypy src

# 手工跑 API 验证：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

P9 落地后，后端下一道门是 P10（策略元扩展）和 P11（TradePlan 事件流），二者都
喂给 F3；F4（Trade 录入 UI）可以从 P9 ship 当天就开工，共用同一份 `schema.d.ts`
类型。

## 10. 面向未来的注记（不要实现，只是不要堵死）

- **数字字段 PATCH（qty/price/commission/fees）。** 如果"归档审计"模式摩擦
  太大，未来阶段可以扩展 `TradeUpdate` 并在 `services/trades.py` 里加
  `recompute_cash_flow_on_change` 分支。closed-position 锁和 archived-row 锁
  仍然有效。
- **全部 Trade 归档时允许 Position-DELETE。** 改一处 filter：
  `select(Trade.id).where(Trade.position_id == position.id,
  Trade.archived_at.is_(None)).limit(1)`，写进 `api/positions.py`。等到
  实际需求出现再放，目前严格不变量保审计。
- **`broker_trade_id` 暴露。** PX 阶段把它加入读 schema，并在 import-only 端点
  上接受传入。
- **Auto-close 检测。** 插进 `services/positions.py::detect_auto_close`，可调
  `services/trades.compute_cash_flow` 或净仓位 query。挂载点：Trade POST 提交
  之后、返回客户端之前。保持 opt-in。
- **分页。** list 响应超过约 500 行时再加 cursor 或 offset；当前的
  `executed_at DESC, id ASC` 排序对 `(executed_at, id)` 游标分页稳定。
- **策略相关校验放到 P10。** P9 故意不校验诸如"wheel position 只接受股票 +
  同标的期权 trade"这类语义；该层校验等到 `WheelCycleMeta` / `PmccCycleMeta`
  存在再落地。

---

## Changelog

- **v0.1（2026-05-26）** —— P9 初版实施 plan。和用户敲定了五个 P9 子决策：
  (1) `price >= 0` —— 兼容 data-model §4.5.2 的 worthless-expire / assignment
  流（修订宏观 §6④）；(2) Trade 除 `notes` 外 immutable —— DELETE 走新加的
  `archived_at` 列做软删除以保留审计；(3) parent Position 已关闭时
  POST/PATCH/DELETE 一律 409（与 P8 拒绝 reopen 的精神一致）；(4) list 端点
  扁平 `GET /trades?position_id=...`，自带 `order_group_id` 与
  `include_archived` 过滤；(5) 多腿 POST 走同一端点接单对象或数组，数组
  未指定时服务端自动生成共享 `order_group_id`。三个 sub-phase：
  P9.1 migration + schemas + service、P9.2 router、P9.3 回归 +
  codegen + 文档修订 + brief。`services/trades.py` 与已有的
  `services/positions.py` 并列，把 cash-flow 公式和 action-kind / qty 守卫
  做成 P12 派生层可复用的构件。
