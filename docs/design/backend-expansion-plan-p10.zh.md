# 后端 Phase P10 — Strategy-meta extensions（实施 plan）

**语言：** [English](./backend-expansion-plan-p10.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-26）。来自宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 中 **P10** 的
> 详细实施 plan。自包含——实施者可直接执行。配套：
> [data-model.zh.md §4.8](./data-model.zh.md#48-strategy-specific-extensions)
> （WheelCycleMeta + PmccCycleMeta 字段定义 + 不存在 IcPositionMeta 的理由）、
> 刚起草的 [backend-expansion-plan-p9.zh.md](./backend-expansion-plan-p9.zh.md)、
> 刚 ship 的 [backend-expansion-plan-p8.zh.md](./backend-expansion-plan-p8.zh.md)
> （Position CRUD + `services/positions.py` 接缝），以及
> [backend-expansion-plan.zh.md §6](./backend-expansion-plan.zh.md#6-design-decisions)
> 的已定决策汇总。

## 1. 目的与上下文

把已经迁移好的 `wheel_cycle_metas` 和 `pmcc_cycle_metas` 表变成带类型的 CRUD
API：策略级 1:1 的 Position 扩展，承载通用 `Position` 行无法表达的
配置/快照数据（WheelCycleMeta = funding/loan/interest，PmccCycleMeta = 那张
具体的 LEAP OptionContract）。快照通用的策略（比如 IC 的
`max_risk_at_open`）直接用 `Position` 自身字段，无需扩展——data-model §4.8
解释了为什么不存在 `IcPositionMeta`。

P10 是**纯 Pydantic + router + service + tests + 一个小的 PMCC 跨表校验守卫**。
**无需 DB migration**——两张表自 Phase 2 的 `0001_initial_schema` 起就存在。
工作形态更接近 P8（单行 CRUD）而不是 P9（多行 + cash_flow），但有一个有意思的
点：PMCC 要求所引用的 LEAP `Instrument` 必须是 `option`，**且**它的 underlying
必须匹配父 Position 的 `primary_instrument_id`。

P10 解锁 F3 Position 详情页三个 tab 里的两个（wheel 的 Meta + PMCC 的 Meta）。

### 已定决策（不要重新推导）

2026-05-26 与用户敲定的四个 P10 子决策，外加从 P7/P8/P9 继承的"按惯例"选项：

- **嵌套 sub-resource 风格 URL。** `GET / POST / PATCH / DELETE
  /positions/{pid}/wheel-meta` 与 `.../pmcc-meta`。与 Position 的 1:1 关系完全
  由 URL 表达——没有 listing 端点、没有请求 body 里的 `position_id`、没有
  `?position_id=` 查询参数。（这是相对于其他扁平 `/accounts`、`/positions`、
  `/trades` 风格的有意偏离：那些是独立 collection；meta 不是。）
- **`strategy_type` 严格匹配。** `WheelCycleMeta` 只能挂在
  `strategy_type == wheel` 的 Position；`PmccCycleMeta` 只能挂在
  `strategy_type == pmcc`。POST 或首写时不匹配 → **422**。校验在服务端
  解析 Position 之后执行；客户端不被信任。
- **PMCC LEAP 三重校验。** `PmccCycleMeta.leap_instrument_id` 必须同时满足
  三条，写入时都检查：
  1. Instrument 行存在 → 否则 **422** `"leap instrument not found"`。
  2. `instrument.kind == option` → 否则 **422**
     `"leap_instrument_id must reference an option instrument"`。
  3. 对应的 `OptionContract.underlying_instrument_id` 等于
     `position.primary_instrument_id` → 否则 **422**
     `"leap option's underlying does not match position's primary instrument"`。
  第三条最有用——能拦下"LEAP 选错标的"这种否则会静默生成废 PMCC position
  的真实错误。
- **closed 状态**对 meta **不**构成锁定。 与 P9（Trade POST/PATCH/DELETE
  在 closed position 下一律 409）不同，与 P8（status `closed → open` 拒绝）
  不同，meta 写入**不受父 Position 状态影响**。理由：meta 承载
  配置/快照数据（已计利息、LEAP 指针），不是金融事件；用户经常需要在
  position 关闭后补录利息；LEAP 指针选错可以追溯修订。`pnl_realized` 不从
  meta 派生，meta 改动不会让它过期。
- **POST = 仅创建，已存在则 409。** 因为 `position_id` 就是 meta 表的主键，
  每个 Position 最多一行 meta。POST 不做 upsert；第二次 POST → 409
  `"meta already exists for this position; use PATCH"`。PATCH 是修订路径。
  DELETE 是硬删（meta 表无软删列，meta 也没有 Trade 那种审计价值）。
- **Owner-scoped via Position。** Meta 无直接 `user_id`；归属经
  `position.user_id` 流通。每个端点先解析 Position；跨用户 `position_id`
  → **404**（与 P6/P7/P8/P9 一致）。
- **本层校验仅做格式。** Pydantic enforce `loan_amount` /
  `interest_rate_apr` / `interest_accrued` 的 `ge=0`（零有意义——cash-funded
  cycle 的 `loan_amount=0`）。不做跨字段业务校验（比如"funding_source=cash
  时 loan_amount 必须 null"）—— 用户自选。与 P8 的"format-only"哲学一致。
- **无新 migration。** 两张表自 `0001_initial_schema` 起就存在。
- **meta 无 `created_at` / `updated_at`。** 现有 ORM 不带；P10 不加。meta
  不承担审计史。

## 2. 范围

### 本 plan 之内

- `schemas/strategy_meta.py` —— 两组 schema 装在一个模块里：
  `WheelMetaCreate` / `WheelMetaUpdate` / `WheelMetaRead`，
  `PmccMetaCreate` / `PmccMetaUpdate` / `PmccMetaRead`。
- `services/strategy_meta.py` —— 跨表校验 helper：
  `validate_strategy_type_match()`、`validate_leap_instrument()`。
  router 调用它们；测试覆盖两层。
- `api/strategy_meta.py` —— 一个 router，挂载 8 个端点：
  `/positions/{pid}/wheel-meta`（×4）与 `/positions/{pid}/pmcc-meta`（×4）。
- 在 `main.py` 里挂载——meta router 作为兄弟挂载，prefix 以
  `/positions/{position_id}/...` 开头。（最终 URL：
  `/api/positions/{pid}/wheel-meta` 等。）
- `tests/test_strategy_meta.py`。
- 后端绿灯后，前端 `npm run codegen` → 重新生成 `frontend/src/api/schema.d.ts`
  并提交。

### 不在范围内

- **不引入新 meta 类型。** IC 不加 meta 表（参 data-model §4.8：只有
  `max_risk_at_open`，已在 `Position`）。MVP 不预计 spot-stock / spot-forex
  的 meta 表。
- **不做 wheel funding 的跨字段业务校验**（如 margin ⇒ loan_amount 必填）。
  格式校验为限。
- **不做 `interest_accrued` 重算 / 每日累计 job。** 参 data-model §4.8：
  "MVP 手填总数；未来在 §7 讨论"。P10 存什么用户输什么。
- **`leap_instrument_id` PATCH 不做任何级联。** 改 LEAP 指针就是一次单行
  更新；不会回溯重定向 trade、不会重算、不会提醒用户历史 trade 可能与新 meta
  不一致。
- **无新 migration。**
- 前端 F3 实现。
- 聚合 / 派生端点（P12）。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/strategy_meta.py                ← 新增
├── services/strategy_meta.py               ← 新增
├── api/strategy_meta.py                    ← 新增
└── main.py                                 ← 修改：include strategy_meta.router
backend/tests/test_strategy_meta.py         ← 新增
frontend/src/api/schema.d.ts                ← 末尾重新生成
```

`schemas/` 和 `services/` 包已经存在；P10 每个包加一个模块。新增的
`api/strategy_meta.py` 单文件一个 `APIRouter`——两个 meta 类型共用 router 是
为了 prefix 一致写成 `/positions/{position_id}`。

## 4. Schema 形状（目标）

```python
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import FundingSource


# ─────────────────── WheelCycleMeta ───────────────────

class WheelMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)
    # 不接受：position_id（URL 绑定），无其他字段


class WheelMetaUpdate(BaseModel):
    """Partial update；所有字段可选。数字字段仍 `ge=0`。"""
    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource | None = None
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)


class WheelMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    funding_source: FundingSource
    loan_amount: Decimal | None
    interest_rate_apr: Decimal | None
    interest_accrued: Decimal | None


# ─────────────────── PmccCycleMeta ───────────────────

class PmccMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID
    # 不接受：position_id（URL 绑定）


class PmccMetaUpdate(BaseModel):
    """Partial update —— leap_instrument_id 是唯一字段。"""
    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID | None = None


class PmccMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    leap_instrument_id: uuid.UUID
```

**形状要点。**

- 每个写 schema 都 `extra="forbid"`。`position_id` 不能从 body 提供——URL
  `/positions/{pid}/...` 是唯一来源，客户端塞了就 422 `extra_forbidden`。
- `WheelMetaUpdate.funding_source` 在 Pydantic 类型上接受 `None`，意思仅是
  "未设置"。因为 ORM 字段是 `nullable=False`，router 不会把显式 `null` 当成
  "清空"——它跟省略效果一样（都视为未设置）。要清空 funding_source 用户做
  不到；只能 DELETE + 重建。这种做法对齐 ORM 约束，不引入虚假的
  "set null" 语义。
- `PmccMetaUpdate.leap_instrument_id: ... = None` 同理——"未设置"，非
  "设置为 null"。ORM 列非空。
- `*Read` 上没有 `created_at` / `updated_at` —— meta 表不带。

## 5. Service 层接口（`services/strategy_meta.py`）

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, StrategyType
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position


def validate_strategy_type_match(
    position: Position, expected: StrategyType
) -> None:
    """position.strategy_type 不等于 expected 时抛 ValueError；router 转 422。"""
    if position.strategy_type is not expected:
        raise ValueError(
            f"position.strategy_type is '{position.strategy_type.value}', "
            f"meta requires '{expected.value}'"
        )


async def validate_leap_instrument(
    session: AsyncSession,
    position: Position,
    leap_instrument_id: uuid.UUID,
) -> None:
    """三重检查（参 §1 已定决策）。失败抛 ValueError 并带特定 message；
    router 转 422。"""
    instrument = await session.get(Instrument, leap_instrument_id)
    if instrument is None:
        raise ValueError("leap instrument not found")
    if instrument.kind is not InstrumentKind.OPTION:
        raise ValueError(
            "leap_instrument_id must reference an option instrument"
        )
    contract = await session.get(OptionContract, leap_instrument_id)
    if contract is None:
        # 防御：kind==option 但无 OptionContract 行 = 数据损坏。
        raise ValueError(
            f"instrument {leap_instrument_id} is kind=option but has no "
            "OptionContract row"
        )
    if contract.underlying_instrument_id != position.primary_instrument_id:
        raise ValueError(
            "leap option's underlying does not match position's primary instrument"
        )
```

两个 helper 都是纯函数，吃已解析的 ORM 行（或 session + id）；不渗 HTTP 层关切。
测试用 seeded fixture 直接走它们。

## 6. 分阶段 plan

三个 sub-phase。每个之后跑 `uv run pytest -q && uv run ruff check . &&
uv run mypy src` —— 基线视 P9 是否先 ship 而定。**P9 先 P10 后**：基线
≈ 243。**P10 先（P9 还没落）**：基线 = 183（P8 完成后）。

### P10.1 — Schemas + service helpers

**目标。** 类型表面和校验 helper 就绪；尚无 HTTP。

**任务。**

1. `schemas/strategy_meta.py` —— 上面六个类。
2. `services/strategy_meta.py` —— `validate_strategy_type_match` 与
   `validate_leap_instrument`。
3. service 层单元测试，`tests/test_strategy_meta.py`：
   - `test_validate_strategy_type_match_ok` —— wheel position +
     `expected=wheel` → 不抛。
   - `test_validate_strategy_type_match_mismatch_raises` —— IC position +
     `expected=wheel` → 抛。
   - `test_validate_leap_instrument_ok` —— underlying 匹配 → 不抛。
   - `test_validate_leap_instrument_unknown_raises` —— 随机 UUID。
   - `test_validate_leap_instrument_not_option_raises` —— 拿股票 id 当 LEAP。
   - `test_validate_leap_instrument_wrong_underlying_raises` —— option 的
     underlying ≠ position.primary_instrument。

**验收。** Schema 可 import；service 单测全绿；尚无 API。

### P10.2 — Router + 完整 CRUD

**目标。** 8 个端点 HTTP 走通，归属判定和跨表校验全部正确。

**任务。**

1. `api/strategy_meta.py` —— 单个 `APIRouter`。私有 helper：

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

   async def _get_wheel_meta_or_404(
       session: AsyncSession, position_id: uuid.UUID
   ) -> WheelCycleMeta:
       meta = await session.get(WheelCycleMeta, position_id)
       if meta is None:
           raise HTTPException(404, "Wheel meta not found")
       return meta

   async def _get_pmcc_meta_or_404(
       session: AsyncSession, position_id: uuid.UUID
   ) -> PmccCycleMeta:
       meta = await session.get(PmccCycleMeta, position_id)
       if meta is None:
           raise HTTPException(404, "PMCC meta not found")
       return meta
   ```

2. **端点 —— WheelCycleMeta。**

   | Method | Path | 行为 |
   |---|---|---|
   | `POST` | `/positions/{pid}/wheel-meta` | 解析 position。`validate_strategy_type_match(pos, StrategyType.WHEEL)`。检查无已有 meta（否则 409）。插入。返回 201 + `WheelMetaRead`。 |
   | `GET` | `/positions/{pid}/wheel-meta` | 解析 position（owner）。返回 200 + meta，未创建则 404。 |
   | `PATCH` | `/positions/{pid}/wheel-meta` | 解析 position + meta。`exclude_unset` 偏应用（未指定字段保留原值）。返回 200。 |
   | `DELETE` | `/positions/{pid}/wheel-meta` | 解析 position + meta。硬删。返回 204。 |

3. **端点 —— PmccCycleMeta。**

   | Method | Path | 行为 |
   |---|---|---|
   | `POST` | `/positions/{pid}/pmcc-meta` | 解析 position。`validate_strategy_type_match(pos, StrategyType.PMCC)`。`validate_leap_instrument(session, pos, payload.leap_instrument_id)`。检查无已有 meta（否则 409）。插入。返回 201。 |
   | `GET` | `/positions/{pid}/pmcc-meta` | 解析 position。返回 200 + meta，未创建则 404。 |
   | `PATCH` | `/positions/{pid}/pmcc-meta` | 解析 position + meta。如果 payload 带 `leap_instrument_id`，重跑 `validate_leap_instrument`。应用。返回 200。 |
   | `DELETE` | `/positions/{pid}/pmcc-meta` | 硬删。返回 204。 |

4. **closed-position 故意不检查。** §1 已定 —— meta 不锁生命周期。§7 测试显式
   写 "closed position 上 PATCH meta → 200" 防回归。

5. **`main.py`** —— 注册 `strategy_meta.router`。router 自身把
   `prefix="/positions"`，让路由形如 `/positions/{position_id}/wheel-meta`，
   `main.py` 顶层 API 挂载再加 `/api` 前缀。和现有 `positions.router` 的
   挂载方式一致。

6. `tests/test_strategy_meta.py` —— 见 §7 完整矩阵。

**验收。** 所有 P10 测试绿；完整套件 + ruff + mypy 干净。预期新增
**~45 tests**。

### P10.3 — 回归 + codegen + brief

**目标。** 锁基线；类型推给前端。

**任务。**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` —— 全绿。
2. 前端 codegen。后端跑在 `:8000`，`cd frontend && npm run codegen` →
   应看到 6 个新 schema（`WheelMetaCreate/Update/Read` +
   `PmccMetaCreate/Update/Read`）；`npm run build` 通过；提交 `schema.d.ts`。
3. 端到端跑一遍 §8 curl recipe。
4. 写 `review-notes/p10_implementation_brief.md`（参照前面 brief）。

**验收。** 全绿；recipe 通过；brief 入库。

## 7. 测试矩阵

`tests/test_strategy_meta.py`，复用 `auth_client`、`second_user_client` 以及
migrate 过的 tempfile fixture。Seed helper 扩展成可选造一个 wheel-strategy
Position 和一个 PMCC-strategy Position + 必要的 Instruments（股票 + 挂在该股
上的 LEAP OptionContract + 一个挂在不同股上的诱饵 option）。

### Service 层测试（无 HTTP）

| 测试 | 校验 |
|---|---|
| `test_validate_strategy_type_match_ok` | wheel position + expected=wheel → 不抛 |
| `test_validate_strategy_type_match_mismatch_raises` | IC position + expected=wheel 抛 |
| `test_validate_leap_instrument_ok` | underlying 匹配 → 不抛 |
| `test_validate_leap_instrument_unknown_raises` | 随机 UUID |
| `test_validate_leap_instrument_not_option_raises` | 股票 id |
| `test_validate_leap_instrument_wrong_underlying_raises` | option 的 underlying ≠ position.primary_instrument |

### POST `/positions/{pid}/wheel-meta`

| 测试 | 校验 |
|---|---|
| `test_create_wheel_meta_201_min_payload` | 只填 `funding_source` → 201；nullable 字段为 null |
| `test_create_wheel_meta_with_all_fields` | 每个字段都回环 |
| `test_create_wheel_meta_rejects_position_id_in_body_422` | URL 绑定 |
| `test_create_wheel_meta_rejects_unknown_field_422` | extra="forbid" |
| `test_create_wheel_meta_rejects_negative_loan_amount_422` | ge=0 |
| `test_create_wheel_meta_rejects_negative_interest_rate_422` | ge=0 |
| `test_create_wheel_meta_rejects_negative_interest_accrued_422` | ge=0 |
| `test_create_wheel_meta_allows_zero_loan_amount` | cash-funded cycle |
| `test_create_wheel_meta_rejects_bad_funding_source_422` | enum 校验 |
| `test_create_wheel_meta_rejects_missing_funding_source_422` | 必填 |
| `test_create_wheel_meta_rejects_on_non_wheel_position_422` | strategy_type 严格 |
| `test_create_wheel_meta_409_if_already_exists` | 第二次 POST |
| `test_create_wheel_meta_404_unknown_position` | 随机 pid |
| `test_create_wheel_meta_404_cross_user` | 别人的 pid |

### GET `/positions/{pid}/wheel-meta`

| 测试 | 校验 |
|---|---|
| `test_get_wheel_meta_200` | 自己的行 |
| `test_get_wheel_meta_404_when_not_created` | position 存在但 meta 没建 |
| `test_get_wheel_meta_404_unknown_position` | 随机 pid |
| `test_get_wheel_meta_404_cross_user` | 别人的 → 404（非 403） |

### PATCH `/positions/{pid}/wheel-meta`

| 测试 | 校验 |
|---|---|
| `test_patch_wheel_meta_partial_update` | 每次改一个字段 |
| `test_patch_wheel_meta_multiple_fields` | 组合改 |
| `test_patch_wheel_meta_unset_means_no_change` | exclude_unset 生效 —— 未提供字段保留原值 |
| `test_patch_wheel_meta_rejects_negative_value_422` | ge=0 仍生效 |
| `test_patch_wheel_meta_rejects_position_id_in_body_422` | URL 绑定 |
| `test_patch_wheel_meta_404_when_meta_not_created` | 先 POST |
| `test_patch_wheel_meta_404_cross_user` | |
| `test_patch_wheel_meta_allowed_on_closed_position` | closed-position **不**锁定（已定决策） |

### DELETE `/positions/{pid}/wheel-meta`

| 测试 | 校验 |
|---|---|
| `test_delete_wheel_meta_204` | 硬删 |
| `test_delete_wheel_meta_404_when_not_created` | 幂等下界：第二次 DELETE → 404 |
| `test_delete_wheel_meta_404_cross_user` | |
| `test_delete_wheel_meta_allowed_on_closed_position` | 已定决策 |
| `test_delete_wheel_meta_does_not_affect_position` | parent Position 仍在 |

### POST `/positions/{pid}/pmcc-meta`

| 测试 | 校验 |
|---|---|
| `test_create_pmcc_meta_201` | 匹配 LEAP → 201 |
| `test_create_pmcc_meta_rejects_on_non_pmcc_position_422` | strategy_type 严格 |
| `test_create_pmcc_meta_rejects_unknown_leap_422` | LEAP 三重 (a) |
| `test_create_pmcc_meta_rejects_non_option_leap_422` | LEAP 三重 (b)（拿股票 id） |
| `test_create_pmcc_meta_rejects_wrong_underlying_leap_422` | LEAP 三重 (c) |
| `test_create_pmcc_meta_409_if_already_exists` | |
| `test_create_pmcc_meta_404_cross_user` | |
| `test_create_pmcc_meta_rejects_position_id_in_body_422` | URL 绑定 |

### GET `/positions/{pid}/pmcc-meta`

| 测试 | 校验 |
|---|---|
| `test_get_pmcc_meta_200` | 自己的行 |
| `test_get_pmcc_meta_404_when_not_created` | |
| `test_get_pmcc_meta_404_cross_user` | |

### PATCH `/positions/{pid}/pmcc-meta`

| 测试 | 校验 |
|---|---|
| `test_patch_pmcc_meta_changes_leap` | 改 LEAP —— 新 LEAP 通过三重则成功 |
| `test_patch_pmcc_meta_rejects_wrong_underlying_leap_422` | 重跑 validate_leap_instrument |
| `test_patch_pmcc_meta_rejects_non_option_leap_422` | |
| `test_patch_pmcc_meta_404_when_meta_not_created` | |
| `test_patch_pmcc_meta_allowed_on_closed_position` | 已定决策 |

### DELETE `/positions/{pid}/pmcc-meta`

| 测试 | 校验 |
|---|---|
| `test_delete_pmcc_meta_204` | |
| `test_delete_pmcc_meta_404_when_not_created` | |
| `test_delete_pmcc_meta_allowed_on_closed_position` | 已定决策 |

### Auth

| 测试 | 校验 |
|---|---|
| `test_requires_auth` | 两个 meta 类型的 POST/GET/PATCH/DELETE 不带 cookie → 401（参数化） |

## 8. 手工验证 reference（完整 P10 走查）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# 注册 + 登录
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"carol@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=carol@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed account + AAPL 股票 instrument
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)
AAPL=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)

# 一个 AAPL 上的 wheel position
WHEEL_POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$AAPL\",\"strategy_type\":\"wheel\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 1) 创建 wheel meta —— 现金驱动，无 loan / interest
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 2) PATCH —— 改成 margin 并补录 loan / interest 快照
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"funding_source":"margin","loan_amount":"10000","interest_rate_apr":"0.055"}'

# 3) 读回
curl -fsS "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" | jq

# 4) 第二次 POST wheel meta → 409
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 5) 关掉 position 再 PATCH meta → 仍然 200（closed-position **不**锁）
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-08-01T20:00:00Z"}'
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"interest_accrued":"250.50"}'

# 6) PMCC 分支 —— seed 一个挂在 AAPL 上的 LEAP option + 一个 PMCC position
LEAP=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"kind\":\"option\",\"symbol\":\"AAPL\",\"currency\":\"USD\",\"option_contract\":{\"underlying_instrument_id\":\"$AAPL\",\"opt_type\":\"call\",\"strike\":\"150.00\",\"expiry\":\"2028-01-21\",\"multiplier\":100}}" | jq -r .id)
PMCC_POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$AAPL\",\"strategy_type\":\"pmcc\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 7) 用匹配的 LEAP 建 pmcc meta → 201
curl -fsSi -X POST "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$LEAP\"}"

# 8) 尝试在 PMCC position 上挂 wheel meta → 422（strategy 不匹配）
curl -fsSi -X POST "$BASE/api/positions/$PMCC_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 9) 尝试在 wheel position 上挂 pmcc-meta + 同一个 LEAP → 422
#    （strategy 不匹配会先于 LEAP 校验拦下）
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$LEAP\"}"

# 10) 尝试把 pmcc meta 的 LEAP PATCH 成股票 id → 422
curl -fsSi -X PATCH "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$AAPL\"}"

# 11) DELETE pmcc meta → 204；第二次 DELETE → 404
curl -fsSi -X DELETE "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR"
curl -fsSi -X DELETE "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR"
```

## 9. 实施者快速开始

```bash
cd backend
# 按 P10.1 → P10.2 → P10.3 推进，每步后：
uv run pytest -q && uv run ruff check . && uv run mypy src

# 手工跑 API 验证：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

P10 落地后，后端下一道门是 **P11**（TradePlan 事件流），与 P10 一起解锁 F3
Position 详情页的完整布局（wheel/PMCC 的 Meta tab + forex 的 Plan tab）。

## 10. 面向未来的注记（不要实现，只是不要堵死）

- **IcPositionMeta（或任何新 meta 类型）** —— 加新表是纯加法：新 ORM 模型 +
  新 alembic migration（建新表）+ 在 `schemas/strategy_meta.py` /
  `api/strategy_meta.py` 里再加一组 schema + endpoint。router 模式无需改动。
  strategy-type 匹配枚举需要加一个分支。
- **每日利息累计 job** —— broker API 整合成熟后，后台 job 可以回调
  `services/strategy_meta.py` 来更新 `interest_accrued`。P10 列可写，无需
  schema 改动。
- **跨字段业务校验**（margin ⇒ loan_amount 必填等）—— 作为
  `services/strategy_meta.py` 的额外 helper 干净加入，不动 schema。
- **`leap_instrument_id` 变更检测** —— 用户通过 PATCH 改 LEAP 后，未来的
  "trade-vs-meta 一致性检查"可以提示旧 LEAP 上的历史 trade。它属于 P12 /
  派生层，不在这里。
- **meta 软删除** —— P10 不引入，因为 meta 无审计价值。未来若需要，参 P9
  的 `archived_at` + list filter 模式平移过来即可，再加一次 migration。

---

## Changelog

- **v0.1（2026-05-26）** —— P10 初版实施 plan。和用户敲定四个 P10 子决策：
  (1) 嵌套 sub-resource URL `/positions/{pid}/wheel-meta` 和
  `.../pmcc-meta`，不做扁平 collection；(2) `strategy_type` 严格匹配——
  WheelCycleMeta 只能挂 `strategy_type=wheel` 的 position，PmccCycleMeta 只能挂
  `pmcc`；(3) LEAP 三重校验——存在 + kind=option + underlying 匹配
  position.primary_instrument；(4) closed-position **不**锁 meta——
  PATCH/DELETE 不受父 Position 状态影响（meta 是配置/快照，非金融事件）。
  三个 sub-phase：P10.1 schemas + service helpers、P10.2 router（8 个端点）
  + tests、P10.3 回归 + codegen + brief。无新 migration——两张表自
  `0001_initial_schema` 起就存在。`services/strategy_meta.py` 与
  `services/positions.py`、（未来的）`services/trades.py` 并列，把跨表校验
  helper 做成可复用构件。P10 不对宏观 §6 做任何修订——子决策都是
  P10 内部的。
