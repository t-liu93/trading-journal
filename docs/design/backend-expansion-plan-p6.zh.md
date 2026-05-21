# 后端 Phase P6 — Instrument CRUD（实现计划）

**语言：** [English](./backend-expansion-plan-p6.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-21）。宏观路线图
> [backend-expansion-plan.zh.md](./backend-expansion-plan.zh.md) 中 **P6 核心**的详细施工图。
> 自包含——实现者可直接照做。配套：[data-model.zh.md](./data-model.zh.md) §4.3 & §6，
> 以及 **Account 模板**（`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`）。
>
> **P6.x（外部校验）不在本文档。** 它需要 provider spike + 决策，且排在 P6 核心之后——见
> [roadmap §P6.x](./backend-expansion-plan.zh.md)。**不要**从本计划启动它。

## 1. 目的与背景

把已迁移的 `instruments` / `option_contracts` / `forex_pairs` 三张表变成带类型的 CRUD API：
一本**共享、全局的 instrument 字典**，用户把它挂到自己的 position / trade 上。**无需写
migration**（表自 Phase 2 的 `0001_initial_schema` 就已存在）；P6 纯粹是 Pydantic schema +
路由 + 测试。

### 已定决策（勿重新推导）

- **全局，非 owner-scoped。** `Instrument` **无 `user_id`**。所有端点仍要求认证
  （`current_active_user`），但**不做按用户过滤**——每个用户看到并共享同一本字典。（这是唯一
  与 Account 模板不同之处。）
- **端点：** `GET /instruments`（列表/搜索）、`GET /instruments/{id}`、`POST /instruments`
  （**get-or-create**）。**无 PATCH/DELETE**——instrument 会被他人 position 引用。
- **get-or-create + 去重**，按自然键（每种 kind，见下）。已存在→**200**；新建→**201**。
  应用层去重（先查后建）；DB 唯一约束延后（需 migration）——MVP 接受这点竞态窗口。
- **symbol 规范化：** 查/插前 `.upper().strip()`。
- **校验仅做格式**（不做"是不是真实代码"的事实校验——那是 P6.x）。
- **期权**用 `underlying_symbol` 顺带建底层股票；`currency` 共享（期权 currency == 底层
  currency，data-model §4.3）——只提供一次。
- **外汇**由 `quote_currency` 派生 `Instrument.currency`，使 §4.3 不变量无法被违反。

## 2. 范围

### 本计划内

- `schemas/instrument.py` —— 判别联合（discriminated union）的 create + 嵌套 read schema
- `api/instruments.py` —— 路由（`GET` 列表/搜索、`GET /{id}`、`POST` get-or-create）
- 在 `main.py` 中挂到 `/instruments`
- `tests/test_instruments.py`
- 后端绿后：重新生成 `frontend/src/api/schema.d.ts`（`npm run codegen`）+ 提交

### 不在范围内

- **P6.x 外部校验 / `/instruments/lookup` / 缓存** —— 独立、延后。
- instrument 的 PATCH/DELETE。
- DB 唯一约束 / 去重 migration。
- Position/Trade 接线（P8/P9）—— 这里 instrument 独立创建。

## 3. 文件

```
backend/src/trading_journal/
├── schemas/instrument.py        ← 新增
├── api/instruments.py           ← 新增
└── main.py                      ← 改：include instruments.router
backend/tests/test_instruments.py ← 新增
frontend/src/api/schema.d.ts     ← 最后重新生成
```

## 4. Schema 形状（目标）

`schemas/instrument.py` —— create 用按 `kind` 的 Pydantic **判别联合**，read 用单个
`InstrumentRead` 带可选的嵌套扩展块：

```python
CURRENCY = r"^[A-Z]{3}$"

class StockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stock"]
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY)

class OptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["option"]
    underlying_symbol: str = Field(min_length=1, max_length=64)
    underlying_exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY)        # 期权 + 底层共享
    opt_type: OptType
    strike: Decimal = Field(gt=0)
    expiry: date
    multiplier: int = Field(default=100, gt=0)
    style: OptionStyle = OptionStyle.AMERICAN

class ForexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["forex"]
    symbol: str = Field(min_length=1, max_length=64)   # 例 "EURUSD"
    base_currency: str = Field(pattern=CURRENCY)
    quote_currency: str = Field(pattern=CURRENCY)
    pip_size: Decimal = Field(gt=0)
    contract_size: Decimal | None = Field(default=None, gt=0)
    # Instrument.currency 派生 = quote_currency（不在此 payload）

InstrumentCreate = Annotated[
    Union[StockCreate, OptionCreate, ForexCreate], Field(discriminator="kind")
]

class OptionContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    underlying_id: uuid.UUID
    opt_type: OptType
    strike: Decimal
    expiry: date
    multiplier: int
    style: OptionStyle

class ForexPairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    base_currency: str
    quote_currency: str
    pip_size: Decimal
    contract_size: Decimal | None

class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: InstrumentKind
    symbol: str
    exchange: str | None
    currency: str
    created_at: datetime
    option: OptionContractRead | None = None   # kind == option 时填充
    forex: ForexPairRead | None = None          # kind == forex 时填充
```

> `InstrumentRead.option`/`.forex` 不会被 `from_attributes` 自动填充（关系名不同）。路由取出
> 扩展行后显式构造 read 模型（小 helper `_to_read(instrument, session)`）。

## 5. 分阶段计划

顺序执行。每步之后保持后端全绿：`uv run pytest -q && uv run ruff check . && uv run mypy src`
（Phase 0–4 基线当前 47/47）。每个子阶段可独立提交。

### P6.1 — 股票 create + get + 列表/搜索

**目标。** 模块骨架 + 完整的 read/list/get-or-create 管线，先只支持 `stock`。立好另两种
kind 套用的范式。

**任务。**
1. `schemas/instrument.py` —— 加 `StockCreate`、`InstrumentRead`（先只 base 字段，暂无扩展
   块），以及暂时只含 `StockCreate` 的 `InstrumentCreate` 联合。
2. `api/instruments.py`：
   - `router = APIRouter(prefix="/instruments", tags=["instruments"])`
   - `POST ""` → `InstrumentRead`，get-or-create。用 FastAPI `response: Response` 动态设置
     **200（已存在）vs 201（新建）**。规范化 symbol；去重查询按 `(kind=stock, symbol,
     currency, exchange)` —— **exchange 为 None 时用 `.is_(None)`**（SQL `= NULL` 永不匹配）。
   - `GET ""` → `list[InstrumentRead]`。查询参数：`kind?`、`q?`（symbol 前缀不区分大小写，
     `ilike(f"{q}%")`）、`limit=50`。按 `symbol` 再 `created_at` 排序。
   - `GET /{id}` → `InstrumentRead`；缺失 404。
   - 均依赖 `current_active_user` + `get_session`（照搬 Account 路由 DI）。
3. `main.py` 中 `app.include_router(instruments.router)`（与 accounts 一致，同在 `/api` 前缀下）。
4. `tests/test_instruments.py` —— 复用 `auth_client` / `second_user_client` fixture。

**人工验证。**
```bash
# （登录拿到 cookies.txt 后，参考 test_accounts 的 curl 配方）
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"aapl","exchange":"NASDAQ","currency":"USD"}'
# → 201，symbol 规范化为 "AAPL"
# 完全相同的 POST 再来一次 → 200（get-or-create 返回同一行，无重复）
curl -fsS "$BASE/instruments?q=aa" -b cookies.txt        # → [AAPL]
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"X","currency":"usd"}'    # → 422（currency 不符 ^[A-Z]{3}$）
```

**自动化测试。**
- `test_create_stock_201`（且 symbol 规范化为大写）
- `test_create_stock_idempotent_returns_200_same_id`（get-or-create）
- `test_create_stock_distinct_exchange_creates_new_row`
- `test_list_filters_by_kind_and_prefix_q`
- `test_get_by_id_200` / `test_get_unknown_404`
- `test_create_rejects_bad_currency_422` / `test_create_rejects_empty_symbol_422`
- `test_requires_auth_401`（POST + GET 无 cookie）
- **`test_instruments_are_global`**：用户 A 建 AAPL；用户 B 的 `GET /instruments` 能看到它，
  且 B 完全相同的 `POST` 返回 **200** 且 id 为 A 那行（共享字典）。

**验收。** 全部测试通过；后端绿；人工配方符合预期。

### P6.2 — 期权 create + 嵌套 read

**目标。** `POST {kind:"option"}` 自动解析/创建底层股票，并原子写入 `OptionContract` 扩展；
读取返回嵌套 `option` 块。

**任务。**
1. schema 加 `OptionCreate` + `OptionContractRead`；加入联合；`InstrumentRead` 加 `option` 字段。
2. 路由 `option` 创建分支：
   - 按 `(underlying_symbol, currency, underlying_exchange)` get-or-create **底层股票**
     （复用 P6.1 的股票 helper）。
   - 合约按 `(underlying_id, opt_type, strike, expiry, multiplier)` 去重；已存在→200，否则在
     **一个事务**内建 `Instrument(kind=option, symbol=underlying_symbol, currency, ...)`
     **加** `OptionContract(...)`（单次 `commit`）。
   - 期权行的 `Instrument.symbol` = 底层 symbol（data-model §4.3："对期权这是底层 symbol"）。
3. `_to_read` 在 `kind == option` 时填充 `.option`。

**人工验证。**
```bash
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' -d '{
  "kind":"option","underlying_symbol":"AAPL","underlying_exchange":"NASDAQ","currency":"USD",
  "opt_type":"put","strike":"220","expiry":"2026-05-28"}'
# → 201；响应含 option:{opt_type:"put",strike:"220.000000",expiry:"2026-05-28",
#   multiplier:100,style:"american"}；底层 AAPL 股票行已存在/被复用
# 完全相同再来一次 → 200 同 id；AAPL 股票不重复
```

**自动化测试。**
- `test_create_option_201_and_nested_read`
- `test_create_option_autocreates_underlying_stock`（此后存在该 symbol 的股票行）
- `test_create_option_reuses_existing_underlying`（预建 AAPL 股票 → 不产生第二行股票）
- `test_create_option_idempotent_returns_200`
- `test_option_currency_matches_underlying`
- `test_create_option_rejects_nonpositive_strike_422` / `bad opt_type 422`

**验收。** 同上；后端绿。

### P6.3 — 外汇 create + 嵌套 read

**目标。** `POST {kind:"forex"}` 写 `Instrument` + `ForexPair`，派生
`Instrument.currency = quote_currency`。

**任务。**
1. 加 `ForexCreate` + `ForexPairRead`；加入联合；`InstrumentRead` 加 `forex` 字段。
2. 路由 `forex` 创建分支：
   - 规范化 `symbol`；令 `Instrument.currency = quote_currency`（**不**从 payload 读 currency
     —— 它不在里面）。
   - 按 `(kind=forex, symbol)` 去重；已存在→200，否则在一个事务内建 `Instrument` + `ForexPair`。
3. `_to_read` 在 `kind == forex` 时填充 `.forex`。

**人工验证。**
```bash
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' -d '{
  "kind":"forex","symbol":"EURUSD","base_currency":"EUR","quote_currency":"USD",
  "pip_size":"0.0001"}'
# → 201；instrument.currency == "USD"（== quote_currency）；含 forex 块
```

**自动化测试。**
- `test_create_forex_201_currency_equals_quote`
- `test_create_forex_idempotent_returns_200`
- `test_create_forex_rejects_bad_quote_currency_422`
- `test_forex_nested_read_has_pip_size`

**验收。** 同上；后端绿。

### P6.4 — 回归 + codegen + 冒烟

**目标。** 锁定基线并把类型传播到前端。

**任务。**
1. 后端：`uv run pytest -q && uv run ruff check . && uv run mypy src` —— 全绿。
2. 前端 codegen：后端起在 :8000，然后 `cd frontend && npm run codegen` →
   `git diff src/api/schema.d.ts` 应显示新增的 Instrument schema；`npm run build` 通过；
   **提交重新生成的 `schema.d.ts`**。
3. 端到端走一遍 §7 的 curl 配方。
4. 在 `review-notes/p6_implementation_brief.md` 留实现简报（仿 F1 简报）。

**验收。** 全绿；`schema.d.ts` 已提交；配方通过。

## 6. 测试方式

与 Phase 4 同一套（`tests/conftest.py`：`auth_client`、`second_user_client`、迁移过的临时
SQLite、依赖覆盖的 session）。instrument 是全局的，所以关键的额外测试是**跨用户共享**
（P6.1 的 `test_instruments_are_global`），而非隔离。无需新 fixture。

## 7. 人工验证参考（P6 完整走查）

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"
curl -fsS -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# 股票 —— 创建，再幂等
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"aapl","exchange":"NASDAQ","currency":"USD"}'   # 201, AAPL
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","exchange":"NASDAQ","currency":"USD"}'   # 200 同 id

# 期权 —— 顺带建底层，嵌套 read
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' -d '{
  "kind":"option","underlying_symbol":"AAPL","underlying_exchange":"NASDAQ","currency":"USD",
  "opt_type":"put","strike":"220","expiry":"2026-05-28"}'                       # 201 + option{}

# 外汇 —— currency 由 quote 派生
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' -d '{
  "kind":"forex","symbol":"EURUSD","base_currency":"EUR","quote_currency":"USD",
  "pip_size":"0.0001"}'                                                          # 201, currency USD

curl -fsS "$BASE/instruments?q=aa" -b "$JAR"          # AAPL 股票 + AAPL 期权
curl -fsS "$BASE/instruments?kind=forex" -b "$JAR"    # EURUSD
```

## 8. 实现者快速上手

```bash
cd backend
# 逐子阶段构建（P6.1 → P6.2 → P6.3 → P6.4）；每步之后：
uv run pytest -q && uv run ruff check . && uv run mypy src
# 跑起 API 做人工检查：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 变更日志

- **v0.1（2026-05-21）** — 初版 P6 施工图：股票 → 期权 → 外汇 → 回归/codegen。P6.x 外部校验
  明确排除（延后，需 spike）。
