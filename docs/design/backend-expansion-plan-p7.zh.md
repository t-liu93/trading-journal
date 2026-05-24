# Backend Phase P7 — StrategyConfig CRUD（实现规划）

**语言：** [English](./backend-expansion-plan-p7.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-24）。来自宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 的 **P7** 详细
> 实现规划。自包含 — 实现者可直接据此执行。配套：
> [data-model.zh.md §4.7](./data-model.zh.md#47-strategyconfig-strategy-level-configuration)、
> **Account 模板**（`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`）、以及刚交付的
> [backend-expansion-plan-p6.zh.md](./backend-expansion-plan-p6.zh.md)（本规划复用
> 了它的 get-or-create 200/201 模式）。

## 1. 目的与上下文

把已经迁移好的 `strategy_configs` 表变成 typed CRUD API：一行**用户级 + 策略级**
的配置，承载用户对某个策略类型的合计曝光上限（例如对
`iron_condor.max_risk_at_open` 总和的 $3,000 上限）。无需数据库迁移
（Phase 2 的 `0001_initial_schema` 中已建表）；P7 纯粹是 Pydantic schemas + 路由
+ 测试。

### 已确定的决策（无需再推导）

- **Owner-scoped。** 每行都有 `user_id`；每个端点按 `current_active_user.id`
  过滤。跨用户访问返回 **404（不是 403）** — 与 Account 同规则。数据库唯一约束是
  `(user_id, strategy_type)`，因此同一个 `strategy_type` 可以在不同用户间共存。
- **URL 自然键 = `strategy_type`（enum 值），不用 `id`。** 资源每用户最多 5 行
  （一个 `StrategyType` enum 值一行），用可读 enum 做 path 最干净。UUID `id` 仍
  在行上（备未来交叉引用），但不出现在 URL 路径里。
- **端点：**
  - `POST /strategy-configs` — **基于 `(user_id, strategy_type)` 的 get-or-create**。
    已存在 → **200**；新建 → **201**。与 Instrument 200/201 模式一致。
  - `GET /strategy-configs` — 列出当前用户全部，按 `strategy_type` 排序。
  - `GET /strategy-configs/{strategy_type}` — 取单条；缺失 404。
  - `PATCH /strategy-configs/{strategy_type}` — 通过 `exclude_unset` 局部更新；
    缺失 404。
  - `DELETE /strategy-configs/{strategy_type}` — 硬删除（行上无 `archived_at`）；
    缺失 404。
- **POST 是 get-or-create，不是纯创建。** 当 `(user_id, strategy_type)` 已存在时
  返回 **200** + 现有行，而非 409。理由：与 Instrument 模式一致（F2 plan 已暴露
  给用户看过），前端不需要先做"存在性预检"。要改字段用 `PATCH`。
- **`strategy_type` 不可变。** 它是自然键 — `PATCH` 不接受；想"换策略"就 DELETE
  后再 POST 新建。
- **`updated_at` 由服务端管理。** SQLAlchemy `onupdate=func.now()` 已自动处理；
  路由不显式赋值。
- **无 `created_at`。** 模型只有 `updated_at`
  （[data-model §4.7](./data-model.zh.md#47-strategyconfig-strategy-level-configuration)）；
  read schema 对齐。
- **校验 = 格式校验。** `exposure_currency` 匹配 `^[A-Z]{3}$`；`max_exposure`
  存在时 `> 0`（允许为空表示"暂无上限"）；`strategy_type` 必须是合法
  `StrategyType` enum 值（Pydantic 自动强制）。

## 2. 范围

### 在范围内（本规划）

- `schemas/strategy_config.py` — `StrategyConfigCreate` / `StrategyConfigUpdate` /
  `StrategyConfigRead`
- `api/strategy_configs.py` — 路由（`POST` get-or-create、`GET` list、
  `GET /{type}`、`PATCH /{type}`、`DELETE /{type}`）
- 在 `main.py` 中挂到 `/strategy-configs` 之下（最终 URL：
  `/api/strategy-configs`）
- `tests/test_strategy_configs.py`
- 后端绿后：重新生成 `frontend/src/api/schema.d.ts`（`npm run codegen`）+ 提交

### 不在范围内

- **下单时强制上限**（即当 `sum(open.max_risk_at_open) + new ≥ max_exposure` 时
  拒绝创建 Position）。属于 P8/P9 或后续 services 层。P7 只存上限。
- **多币种上限聚合**。每行自带 `exposure_currency`；无 FX 换算。与
  [data-model §6](./data-model.zh.md#currency-placement) 一致。
- **上限变更的审计历史**。`updated_at` 就地覆盖；无事件流。
- **软删除**。模型上没有这个字段。
- **批量端点**。每用户 ≤5 行，无须批处理。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/strategy_config.py        ← NEW
├── api/strategy_configs.py           ← NEW
└── main.py                           ← 改：include strategy_configs.router
backend/tests/test_strategy_configs.py ← NEW
frontend/src/api/schema.d.ts          ← 末尾重新生成
```

## 4. Schema 形态（目标）

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import StrategyType

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class StrategyConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_type: StrategyType
    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str = Field(pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # strategy_type 不可更新 — 它是 URL 里的自然键。
    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_type: StrategyType
    max_exposure: Decimal | None
    exposure_currency: str
    notes: str | None
    updated_at: datetime
```

**关于 `max_exposure: Decimal | None = Field(default=None, gt=0)`。** Pydantic v2
在值为 `None` 时跳过 `gt=0` 约束，因此这能同时正确接受"暂无上限"（`null` 或缺省）
与正数；非正数仍然校验失败。

**关于 `PATCH` 对可空字段的语义。** 配合 `extra="forbid"` 和
`model_dump(exclude_unset=True)`：`{}` 是 no-op，`{"max_exposure": null}` 显式
清零上限，`{"max_exposure": "5000"}` 设置上限。与 F1 Account 更新同模式。

## 5. 分阶段计划

两个子 phase。P7 本身不大，实现者可压缩到一次会话，但保留拆分以便独立提交。
每段后跑：`uv run pytest -q && uv run ruff check . && uv run mypy src` — 基线
P6 之后是 **92 测试**。

### P7.1 — schemas + 路由 + 测试

**目标。** 完整 CRUD 流水线跑通。

**任务。**

1. **`schemas/strategy_config.py`** — 上述三个类。`CURRENCY_PATTERN` 常量放在
   文件顶部附近（与 `schemas/account.py`、`schemas/instrument.py` 一致；不为
   此专门搞共享常量模块）。

2. **`api/strategy_configs.py`**：
   - `router = APIRouter(prefix="/strategy-configs", tags=["strategy-configs"])`
   - 私有辅助：
     ```python
     async def _get_owned_config(
         session: AsyncSession,
         user: User,
         strategy_type: StrategyType,
     ) -> StrategyConfig:
         stmt = select(StrategyConfig).where(
             StrategyConfig.user_id == user.id,
             StrategyConfig.strategy_type == strategy_type,
         )
         cfg = (await session.execute(stmt)).scalar_one_or_none()
         if cfg is None:
             raise HTTPException(status_code=404, detail="Strategy config not found")
         return cfg
     ```
   - `POST ""` → `StrategyConfigRead`，**get-or-create**。取 FastAPI
     `response: Response` 来动态设置 **200（已存在） vs 201（新建）**：先按
     `(user_id, strategy_type)` 查询；存在则原样返回 + 200；否则插入 + 201。
   - `GET ""` → `list[StrategyConfigRead]`，owner-scoped，按 `strategy_type`
     排序。
   - `GET /{strategy_type}` → `StrategyConfigRead`；通过 `_get_owned_config`
     404。
   - `PATCH /{strategy_type}` → `StrategyConfigRead`；`model_dump(exclude_unset=True)`
     + `setattr` 循环，与 `api/accounts.py:95-108` 的 `update_account` 同模式。
     commit + refresh。`updated_at` 借 `onupdate=func.now()` 自动前进。
   - `DELETE /{strategy_type}` → 204；先 `_get_owned_config` 再
     `session.delete(cfg)` + commit。**硬删除** — 无 `archived_at` 字段。
   - 所有路由依赖 `current_active_user` + `get_session`（DI 与 Account 一致）。

3. **`main.py`** — 加 `from trading_journal.api import ..., strategy_configs`
   并在 `create_app()` 中 `api.include_router(strategy_configs.router)`（与
   `accounts.router`、`instruments.router` 的接线方式一致）。加一行注释：
   `# Domain: per-user StrategyConfig under /api/strategy-configs.`

4. **`tests/test_strategy_configs.py`** — 复用 `tests/conftest.py` 的
   `auth_client` 与 `second_user_client`。

**手动验证。**
```bash
BASE=http://localhost:8000; JAR=cookies.txt
# （先 register + login）

# 1. 创建 wheel config → 201
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"50000","exposure_currency":"USD"}'
# → 201；max_exposure="50000.0000"；updated_at 已写入

# 2. 同 strategy_type 再 POST → 200，同一 id（get-or-create）
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"99999","exposure_currency":"EUR"}'
# → 200；返回**原行**（max_exposure 仍是 50000）— POST 不会覆盖现有行

# 3. PATCH 更新上限并加 notes
curl -fsSi -X PATCH "$BASE/api/strategy-configs/wheel" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":"60000","notes":"Bull market only"}'
# → 200；max_exposure=60000，notes 写入，updated_at 前进

# 4. PATCH 清空上限（显式 null）
curl -fsSi -X PATCH "$BASE/api/strategy-configs/wheel" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":null}'
# → 200；max_exposure=null

# 5. 列表
curl -fsS "$BASE/api/strategy-configs" -b "$JAR"   # → [{wheel, ...}]

# 6. GET 404
curl -fsSi "$BASE/api/strategy-configs/pmcc" -b "$JAR"   # → 404

# 7. DELETE → 204；之后 GET → 404
curl -fsSi -X DELETE "$BASE/api/strategy-configs/wheel" -b "$JAR"   # → 204
curl -fsSi "$BASE/api/strategy-configs/wheel" -b "$JAR"             # → 404
```

**自动化测试。**

| 测试 | 验证内容 |
|---|---|
| `test_create_strategy_config_201` | POST 返回 201 + 序列化 read 形态 |
| `test_create_returns_200_when_existing` | 同 strategy_type 第二次 POST → 200 + 同一 id；**原值保留**（POST 对已有行只读） |
| `test_create_rejects_unknown_strategy_type_422` | `strategy_type="cowabunga"` → 422 |
| `test_create_rejects_bad_currency_422` | `exposure_currency="usd"` → 422 |
| `test_create_rejects_nonpositive_max_exposure_422` | `max_exposure="-1"` → 422；`"0"` → 422 |
| `test_create_accepts_null_max_exposure` | 不传 `max_exposure` 或显式 `null` → 201，存为 null |
| `test_create_rejects_unknown_field_422` | 多余字段被拒 |
| `test_list_returns_only_current_user_rows` | 用户 A 创建 wheel；用户 B 列表为空 |
| `test_list_ordered_by_strategy_type` | 行按稳定 enum 顺序返回 |
| `test_get_by_strategy_type_200` | GET `/wheel` 返回该行 |
| `test_get_unknown_strategy_type_404` | GET 未设置的策略 → 404 |
| `test_patch_updates_only_provided_fields` | PATCH `{notes}` 不改 max_exposure |
| `test_patch_clears_max_exposure_with_explicit_null` | PATCH `{max_exposure: null}` 清空 |
| `test_patch_unknown_strategy_type_404` | PATCH 不存在的 config → 404 |
| `test_patch_rejects_strategy_type_in_body_422` | PATCH body 含 `strategy_type` → 422（`extra="forbid"`） |
| `test_patch_advances_updated_at` | PATCH 成功后 updated_at 严格变大 |
| `test_delete_strategy_config_204` | DELETE → 204；行消失 |
| `test_delete_unknown_strategy_type_404` | DELETE 缺失 → 404 |
| `test_requires_auth` | 参数化：POST/GET/PATCH/DELETE 无 cookie → 401 |
| `test_same_strategy_isolated_across_users` | 用户 A 建 `iron_condor`；用户 B 也建 `iron_condor`；两者都成功、互不可见、各自一行 |

**验收。** 全部测试通过；后端绿；手动 recipe 一致。

### P7.2 — 回归 + codegen + brief

**目标。** 锁定基线，把类型同步到前端。

**任务。**

1. 后端：`uv run pytest -q && uv run ruff check . && uv run mypy src` — 全绿。
   预期总数：92（P6 基线）+ ~20（P7）≈ **112 测试**。
2. 前端 codegen：后端起在 `:8000`，然后 `cd frontend && npm run codegen` →
   `git diff src/api/schema.d.ts` 应显示新的 `StrategyConfigCreate / Update /
   Read` schemas 和 `StrategyType` enum。`npm run build` 通过；**提交重新生成
   的 `schema.d.ts`**。
3. 端到端跑 §7 curl recipe。
4. 在 `review-notes/p7_implementation_brief.md` 留实现简报（对标 F1 / P6 简报）。
5. （可选，如不与 F2 一起交付）落地
   [backend-expansion-plan.zh.md §5](./backend-expansion-plan.zh.md#5-cross-cutting--deferred-deliverables-tracked)
   中跟踪的 CI codegen-freshness gate。

**验收。** 全绿；`schema.d.ts` 已提交；recipe 通过；brief 就位。

## 6. 测试方式

与 P4 + P6 同 harness（`tests/conftest.py`：`auth_client`、`second_user_client`、
迁移过的 tempfile SQLite、依赖覆盖的 session）。StrategyConfig 是 owner-scoped，
跨用户测试聚焦 **isolation**（与 Account 一致），**外加**确认
`(user_id, strategy_type)` 唯一约束**不会**阻止两个不同用户各自拥有自己的
`iron_condor` 配置。无新 fixture。

## 7. 手动验证参考（完整 P7 走查）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# 创建 → 201
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"iron_condor","max_exposure":"3000","exposure_currency":"USD","notes":"MVP cap"}'

# 幂等 get-or-create → 200，同 id，原 payload 保留
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"iron_condor","max_exposure":"99999","exposure_currency":"EUR"}'

# 创建第二个策略
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"50000","exposure_currency":"USD"}'

# 列表 → 2 行，按 strategy_type 排序
curl -fsS "$BASE/api/strategy-configs" -b "$JAR"

# PATCH — 局部更新 + 显式 null
curl -fsSi -X PATCH "$BASE/api/strategy-configs/iron_condor" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"Updated for Q3"}'                                              # 只改 notes
curl -fsSi -X PATCH "$BASE/api/strategy-configs/iron_condor" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":null}'                                                   # 清空上限

# GET 404
curl -fsSi "$BASE/api/strategy-configs/pmcc" -b "$JAR"                          # → 404

# DELETE → 204
curl -fsSi -X DELETE "$BASE/api/strategy-configs/iron_condor" -b "$JAR"         # → 204
curl -fsSi "$BASE/api/strategy-configs/iron_condor" -b "$JAR"                   # → 404
```

## 8. 实现者快速开始

```bash
cd backend
# P7.1 → P7.2 顺序构建；每段后：
uv run pytest -q && uv run ruff check . && uv run mypy src
# 起 API 做手动检查：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

P7 绿后，前端 F2 可立即同时消费 P6 + P7 — 见
[frontend-implementation-plan-f2.zh.md](./frontend-implementation-plan-f2.zh.md)。

---

## Changelog

- **v0.1（2026-05-24）** — 初版 P7 build plan：owner-scoped CRUD，`strategy_type`
  作为 path key，`POST` 为 get-or-create（200/201，与 P6 Instrument 模式一致）。
  两个子 phase：P7.1 schemas+路由+测试，P7.2 回归+codegen+brief。
