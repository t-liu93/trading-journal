# MVP 实施方案 — v0 草案

**语言：** [English](./mvp-implementation-plan.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-18）。`refactoring/rebuild` 分支上首条端到端切片的执行方案。配套文档：[data-model.md](./data-model.zh.md)。写代码前先在这里迭代。

## 1. 目的与方法

本文档是搭建 trading journal 后端**首个可工作切片**的**执行方案**。数据模型已经在 [data-model.zh.md](./data-model.zh.md) 中定稿；本方案讨论如何把 schema 变成一个跑得起来、可测、可部署的应用——增量式推进，每步都有可验证的 checkpoint。

**方法：tracer bullet（曳光弹）。** 不预先实现每个 entity 的 CRUD，而是**打通一条端到端的窄路径**穿过整个栈（DB → ORM → migration → API → auth → tests → Docker），之后再做水平扩展。选定的路径：**注册用户 → 登录 → 创建 account → 列 account**——全部走 JSON API，**暂不做 UI**。

为什么这样：这个项目最大的风险不在写 CRUD handler（那是重复劳动），而在于**各组件能不能拼起来**：SQLAlchemy + Alembic + FastAPI Users + uv + Docker + 远程 SSH 工作流。Tracer bullet 在最小的代码面上暴露集成风险，让 debug 成本保持低。

## 2. 范围

### 本次范围

- 用 uv 管理的项目骨架（venv、ruff、mypy、pytest）
- FastAPI app 和 `/health` 端点
- v0.2 完整 schema（[data-model.zh.md](./data-model.zh.md) §4 全部，**不含** §7 的未来鉴权表）的 SQLAlchemy 2.x models
- 初始 Alembic migration，在空 DB 上建出全部表
- FastAPI Users 集成：cookie session + DB-backed users
- `Account` CRUD 端点（垂直切片）：create / list / get / update / soft-delete
- 每一阶段都附详细的人工验证（curl）
- 自动化端到端测试，覆盖 happy path 和关键 corner cases
- 单容器 Dockerfile，暴露一个端口

### 明确**不**做的事（延后）

- Jinja / HTML 模板（**没有 SSR UI**，纯后端 + curl/Postman）
- Vue 前端
- `Account` 以外的 entity CRUD（Position、Trade、Instrument、TradePlan、StrategyConfig 留下一轮）
- 策略专属逻辑（wheel 状态机、IC max_risk 计算、PMCC roll 识别）
- 统计 / 图表 / 报表
- OAuth、MFA、audit log、broker credential 存储（已在 [data-model.zh.md §7](./data-model.zh.md) 记录为未来工作）
- Postgres 部署（MVP 用 SQLite；migration 已 Postgres 兼容）
- CI/CD pipeline

## 3. 技术栈汇总

| 层 | 选定 |
|---|---|
| 语言 | Python **3.12** |
| 包管理 | **uv**（PEP 621 `pyproject.toml`、标准 `.venv`、dev/prod 分组） |
| Web framework | **FastAPI**（latest stable） |
| ORM | **SQLAlchemy 2.x**（async，类型化 `Mapped[...]` 风格） |
| Migrations | **Alembic** |
| Auth | **FastAPI Users** with cookie + DB strategy；bcrypt 密码哈希 |
| DB（dev） | **SQLite** via `aiosqlite` |
| DB（prod，未来） | **PostgreSQL** via `asyncpg`（schema 从第一天起就 Postgres 兼容） |
| Settings | **pydantic-settings**（env-var 驱动） |
| 校验 / API schema | **Pydantic v2** |
| 测试框架 | **pytest** + **pytest-asyncio** + **httpx.AsyncClient** |
| Lint + format | **ruff** |
| 类型检查 | **mypy** strict 模式 |
| 容器 | **Docker**（单镜像、单端口） |

## 4. 目录结构

```
trading-journal/
├── .gitignore                          # 加 .venv/、.env、*.db、__pycache__/、.pytest_cache、.ruff_cache、.mypy_cache
├── .env.example                        # SQLite 路径、cookie secret、debug 标志等
├── README.md                           # 简短，指向 docs/
├── docs/
│   └── design/
│       ├── data-model.md, data-model.zh.md
│       └── mvp-implementation-plan.md, mvp-implementation-plan.zh.md
├── backend/
│   ├── pyproject.toml                  # PEP 621 project + dependency-groups + tool 配置（ruff、mypy、pytest）
│   ├── uv.lock                         # 入仓
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py  # v0.2 完整 schema 一次性写完
│   ├── src/trading_journal/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app factory + router 装配
│   │   ├── config.py                   # pydantic-settings 的 Settings
│   │   ├── db.py                       # async engine + sessionmaker + get_session 依赖
│   │   ├── models/                     # SQLAlchemy models，按逻辑分组
│   │   │   ├── __init__.py             # Base + import 所有 model 让 Alembic 看见
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── instrument.py           # Instrument + OptionContract + ForexPair
│   │   │   ├── position.py
│   │   │   ├── trade.py
│   │   │   ├── trade_plan.py
│   │   │   ├── strategy_config.py
│   │   │   └── strategy_meta.py        # WheelCycleMeta、PmccCycleMeta
│   │   ├── schemas/                    # Pydantic 请求/响应 model
│   │   │   ├── __init__.py
│   │   │   └── account.py
│   │   ├── api/                        # FastAPI router
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   └── accounts.py
│   │   └── auth/                       # FastAPI Users 装配
│   │       ├── __init__.py
│   │       ├── users.py                # UserManager
│   │       ├── backend.py              # CookieTransport + DatabaseStrategy
│   │       └── deps.py                 # current_active_user 依赖
│   └── tests/
│       ├── conftest.py                 # fixtures：app、async client、test DB、已登录用户
│       ├── test_health.py
│       ├── test_auth.py                # register、login、logout、/me、边界场景
│       └── test_accounts.py            # CRUD happy + corner cases
├── frontend/                           # 未来 Vue 应用的占位
│   └── README.md                       # "tracer bullet 之后 Vue 进这里"
├── Dockerfile                          # 多阶段：uv install → runtime
└── docker-compose.yml                  # dev 便利：app + SQLite 的 volume
```

## 5. 分阶段方案

每个阶段都有 **Goal**、**Tasks**、**Files**、**Manual verification**（curl）、**Automated tests**、**Acceptance**。阶段是**串行**的——前一阶段 acceptance 通过前不开下一阶段。

### Phase 0 — 项目骨架与 tooling

**Goal.** 一个可启动的项目，含 venv、依赖管理、lint、类型检查、测试 runner。**没有任何业务逻辑**。

**Tasks.**
1. dev 服务器装 uv：`curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `cd backend && uv init --package` 生成 `pyproject.toml` 骨架；删除自动生成的 `src/backend/`（如有），重新建为 `src/trading_journal/`
3. 用 uv 装 Python：`uv python install 3.12`
4. 建 venv：`uv venv --python 3.12`（生成 `backend/.venv/`）
5. 添加 runtime 依赖（`uv add`）：`fastapi[standard]`、`sqlalchemy[asyncio]`、`aiosqlite`、`alembic`、`fastapi-users[sqlalchemy]`、`pydantic-settings`、`uvicorn[standard]`
6. 添加 dev 依赖（`uv add --dev`）：`pytest`、`pytest-asyncio`、`httpx`、`ruff`、`mypy`、`types-aiofiles`（其它按需）
7. 在 `pyproject.toml` 配 tools：
   - `[tool.ruff]` —— `line-length = 100`、`target-version = "py312"`、lint 规则 `["E", "F", "I", "B", "UP", "ASYNC"]`
   - `[tool.mypy]` —— `strict = true`、`python_version = "3.12"`
   - `[tool.pytest.ini_options]` —— `asyncio_mode = "auto"`、`testpaths = ["tests"]`
8. 创建空 `tests/conftest.py` 和占位 `tests/test_smoke.py`（断言 `True`）
9. 根 `.gitignore` 扩展 Python + uv 产物
10. 创建 `.env.example`，列占位环境变量

**Files created.** `backend/pyproject.toml`、`backend/uv.lock`、`backend/.venv/`（gitignored）、`backend/src/trading_journal/__init__.py`、`backend/tests/conftest.py`、`backend/tests/test_smoke.py`、`.env.example`、更新的 `.gitignore`。

**Manual verification.**
```bash
cd backend
source .venv/bin/activate
ruff check .                # 应无错误
mypy src                    # 应成功（空项目）
pytest -q                   # 应 1 passed（smoke test）
```

**Automated tests.** 只有 smoke test——确认 pytest 能正确发现并执行测试。

**Acceptance.** 上述 4 个命令 exit 0。

---

### Phase 1 — FastAPI app 启动 + `/health`

**Goal.** 一个跑起来的 FastAPI app，能 HTTP 访问，有 health 端点。

**Tasks.**
1. `config.py` —— `pydantic_settings.BaseSettings` 的 `Settings` 类，读 `.env`；字段：`database_url`、`cookie_secret`、`debug`
2. `main.py` —— `create_app() -> FastAPI` 工厂函数，挂载 `health` router；模块级 `app = create_app()`
3. `api/health.py` —— router 含 `GET /health`，返回 `{"status": "ok"}`
4. 文档记录 dev 启动命令：`uv run uvicorn trading_journal.main:app --reload --host 127.0.0.1 --port 8000`

**Files created.** `src/trading_journal/config.py`、`src/trading_journal/main.py`、`src/trading_journal/api/__init__.py`、`src/trading_journal/api/health.py`、`tests/test_health.py`。

**Manual verification.**
```bash
# 服务器端（一个 tmux/screen 窗口）：
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000

# 本机（SSH forward 之后——见 §6）：
curl -i http://localhost:8000/health
# 期望：HTTP/1.1 200 OK，body {"status":"ok"}

curl -i http://localhost:8000/does-not-exist
# 期望：HTTP/1.1 404 Not Found
```

**Automated tests.**
- `test_health_ok` —— `GET /health` 返回 200 + 正确 JSON
- `test_unknown_route_404` —— 未知路径返回 404 + FastAPI 默认 error 形状

**Acceptance.** 两个测试通过；curl 输出符合预期。

---

### Phase 2 — SQLAlchemy models + 初始 Alembic migration

**Goal.** v0.2 全部表（[data-model.zh.md](./data-model.zh.md) §4——**不含** §7 未来鉴权表）做成类型化的 SQLAlchemy 2.x models，并通过一条 Alembic migration 在空 DB 上建出全部表。

**Tasks.**
1. `db.py` —— `Base = DeclarativeBase`；`async_engine = create_async_engine(settings.database_url)`；`async_session_maker`；`get_session()` async 依赖给 FastAPI
2. 写 models，按逻辑分组，全部 import 共享的 `Base`：
   - `user.py` —— User（匹配 FastAPI Users `SQLAlchemyBaseUserTableUUID` mixin 形状）
   - `account.py` —— Account
   - `instrument.py` —— Instrument（base）+ OptionContract + ForexPair 作为独立表，通过 `instrument_id` 连接
   - `position.py` —— Position with `strategy_type` enum
   - `trade.py` —— Trade with `action` enum 和 `order_group_id`
   - `trade_plan.py` —— TradePlan（事件流，`(position_id, revision_no)` unique）
   - `strategy_config.py` —— StrategyConfig（`(user_id, strategy_type)` unique）
   - `strategy_meta.py` —— WheelCycleMeta + PmccCycleMeta
3. 共享的 enums 放 `models/_enums.py` 或就近放：`InstrumentKind`、`OptType`、`OptionStyle`、`AccountType`、`StrategyType`、`PositionStatus`、`TradeAction`、`FundingSource`
4. `models/__init__.py` re-export 全部 model，一句 `import` 把所有 model 带入 Base metadata（Alembic 自动检测的前提）
5. Alembic 初始化：`cd backend && uv run alembic init -t async alembic`（`async` template 是关键）
6. 编辑 `alembic/env.py`：import `Base` 设 `target_metadata = Base.metadata`；从 `settings.database_url` 取 `sqlalchemy.url`
7. 生成 migration：`uv run alembic revision --autogenerate -m "initial schema"` → review → 重命名为 `0001_initial_schema.py`
8. **人工检查** 自动生成的 migration：enum 类型对不对、FK 约束、unique 约束、nullable 设置。按需调整
9. 应用：`uv run alembic upgrade head`（在 backend 根目录生成 `dev.db` SQLite 文件）

**Files created.** `src/trading_journal/db.py`、所有 model 文件、`alembic.ini`、`alembic/env.py`、`alembic/script.py.mako`、`alembic/versions/0001_initial_schema.py`。

**Manual verification.**
```bash
# 应用 migration
uv run alembic upgrade head

# 检查表（SQLite）
sqlite3 dev.db ".tables"
# 期望：users、accounts、instruments、option_contracts、forex_pairs、positions、trades、
#       trade_plans、strategy_configs、wheel_cycle_metas、pmcc_cycle_metas、alembic_version

sqlite3 dev.db ".schema users"
# 期望：列匹配 data-model.zh.md §4.1

# 回滚 roundtrip 测试：
uv run alembic downgrade base
sqlite3 dev.db ".tables"      # 期望：仅 alembic_version（或空）
uv run alembic upgrade head
sqlite3 dev.db ".tables"      # 期望：全部表回来
```

**Automated tests.**
- `test_alembic_upgrade_creates_all_tables` —— 用 tempfile SQLite，跑 `alembic upgrade head`，断言所有期望的表名都存在
- `test_alembic_downgrade_roundtrip` —— upgrade → downgrade → upgrade，无错，最终状态正确
- `test_models_can_be_imported` —— 检查 `models/__init__.py` 干净 import

**Acceptance.** Migration 在新 DB 上干净应用；所有期望的表存在、列正确；downgrade roundtrip 工作；三个测试通过。

---

### Phase 3 — FastAPI Users 鉴权

**Goal.** 用户可以 register、login（cookie session）、调用受保护端点、logout。

**Tasks.**
1. `auth/users.py` —— `UserManager(BaseUserManager[User, UUID])`（覆盖 `on_after_register` 加日志；其它默认即可）
2. `auth/backend.py` —— `CookieTransport(cookie_max_age=...)` + `DatabaseStrategy` 工厂（DB-backed sessions；用 `SQLAlchemyAccessTokenDatabase`）。对应的 `AccessToken` 表必须在 Phase 2 model 里加好并出现在初始 migration 里——**如果 Phase 2 漏了，现在补，并新建 0002 migration**
3. `auth/deps.py` —— `current_active_user` 依赖
4. `main.py` 装配 `fastapi_users.get_auth_router(...)` 和 `get_register_router(...)` 到 `/auth`
5. `main.py` 装配 `fastapi_users.get_users_router(...)` 到 `/users` 给 `/users/me`

**Files created/changed.** `auth/users.py`、`auth/backend.py`、`auth/deps.py`、`main.py` 更新，可能加 `0002_access_tokens.py` migration（或如果 Phase 2 没漏就一起在 0001 里）、`models/user.py` 加 `AccessToken`。

**Manual verification.**
```bash
# Register
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'
# 期望：201 Created，响应体含 user 字段（id、email、is_active=true、is_verified=false）

# 用同邮箱再 register
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'
# 期望：400 Bad Request、REGISTER_USER_ALREADY_EXISTS 错误码

# Login（注意是 form-urlencoded，不是 JSON；FastAPI Users 用 OAuth2 password form）
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=correct horse battery" \
  -c cookies.txt
# 期望：204 No Content；cookies.txt 含 session cookie（HttpOnly）

# 密码错的 login
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=wrong"
# 期望：400 Bad Request、LOGIN_BAD_CREDENTIALS

# 无 cookie 的 /users/me
curl -i http://localhost:8000/users/me
# 期望：401 Unauthorized

# 有 cookie 的 /users/me
curl -i http://localhost:8000/users/me -b cookies.txt
# 期望：200 OK，user 字段

# Logout
curl -i -X POST http://localhost:8000/auth/logout -b cookies.txt
# 期望：204 No Content；之后用同 cookies.txt 调 /users/me → 401
```

**Automated tests**（`tests/test_auth.py`）：
- `test_register_success`
- `test_register_duplicate_email_rejected`
- `test_register_invalid_email_400`
- `test_register_password_too_short_400`（FastAPI Users 默认最短长度）
- `test_login_success_sets_cookie`
- `test_login_wrong_password_400`
- `test_login_unknown_user_400`
- `test_me_without_cookie_401`
- `test_me_with_cookie_200`
- `test_logout_invalidates_session` —— login → /me 成功 → logout → /me → 401

**Acceptance.** 所有 curl 输出符合预期；10 个测试全部通过。

---

### Phase 4 — Account CRUD（垂直切片）

**Goal.** 已认证用户可以对**自己的** `Account` 行做 create / list / read / update / soft-delete（archive），并且**看不到也无法修改别人的**。

**Tasks.**
1. `schemas/account.py` 的 Pydantic schema：
   - `AccountCreate` —— name、broker、account_type、base_currency、notes（**不要** user_id，从 auth 推出）
   - `AccountRead` —— 含 timestamps、archived_at 在内的全字段
   - `AccountUpdate` —— 全部 optional（PATCH 风格）
2. `api/accounts.py` 的 router：
   - `POST /accounts` → 201，归属 `current_active_user`
   - `GET /accounts` → 200，列 `current_active_user` 的 account，默认排除 archived；`?include_archived=true` 包含
   - `GET /accounts/{account_id}` → 200 owned + not archived 时；否则 404（避免向其他用户泄露存在性）
   - `PATCH /accounts/{account_id}` → 200，更新允许字段；非自有 → 404
   - `DELETE /accounts/{account_id}` → 204，设 `archived_at = now()`；非自有或已 archived → 404
3. 在 `main.py` 装配 router 到 `/accounts`

**Files created.** `schemas/__init__.py`、`schemas/account.py`、`api/accounts.py`。

**Manual verification.** （假设你已完成 Phase 3 的 register/login，有 `cookies.txt`。）
```bash
# Create
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"IBKR Margin","broker":"IBKR","account_type":"margin","base_currency":"USD"}'
# 期望：201，JSON 含 id、全字段，archived_at=null

# 无效 account_type
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"X","broker":"X","account_type":"checkings","base_currency":"USD"}'
# 期望：422 Unprocessable Entity，校验错误

# 无 auth
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -d '{"name":"X","broker":"X","account_type":"cash","base_currency":"USD"}'
# 期望：401

# List
curl -i http://localhost:8000/accounts -b cookies.txt
# 期望：200，自己 account 的数组

# Get 单个
curl -i http://localhost:8000/accounts/<id-from-create> -b cookies.txt
# 期望：200

# Get 不存在 / 非自有
curl -i http://localhost:8000/accounts/00000000-0000-0000-0000-000000000000 -b cookies.txt
# 期望：404

# Update
curl -i -X PATCH http://localhost:8000/accounts/<id> \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"notes":"changed my mind"}'
# 期望：200，更新后字段反映

# Soft-delete
curl -i -X DELETE http://localhost:8000/accounts/<id> -b cookies.txt
# 期望：204

# 确认默认 list 不含已删除
curl http://localhost:8000/accounts -b cookies.txt
# 期望：account 不在结果里

# 加 ?include_archived=true 应含
curl 'http://localhost:8000/accounts?include_archived=true' -b cookies.txt
# 期望：archived account 含 archived_at

# 跨用户隔离：注册第二个用户，以 Bob 登录，尝试 GET Alice 的 account
# 期望：404（不是 403，避免泄露存在性）
```

**Automated tests**（`tests/test_accounts.py`）：
- Happy：`test_create_account`、`test_list_accounts_empty`、`test_list_accounts_after_create`、`test_get_account_by_id`、`test_update_account_partial`、`test_soft_delete_excludes_from_default_list`、`test_include_archived_param`
- Auth：`test_create_requires_auth`、`test_list_requires_auth`、`test_get_requires_auth`、`test_update_requires_auth`、`test_delete_requires_auth`
- Validation：`test_create_rejects_invalid_account_type`、`test_create_rejects_missing_required_fields`、`test_create_rejects_invalid_currency_code`（如做了校验）、`test_update_rejects_unknown_field`（或静默忽略——选一个固定行为）
- Authorization（多用户）：`test_list_only_returns_own_accounts`、`test_get_other_users_account_returns_404`、`test_update_other_users_account_returns_404`、`test_delete_other_users_account_returns_404`
- 幂等 / 边界：`test_delete_already_archived_returns_404`、`test_get_archived_by_default_returns_404`

**Acceptance.** 所有 curl 输出符合预期；所有测试通过；跨用户隔离端到端验证。

---

### Phase 5 — Docker 单容器部署

**Goal.** App 跑在一个 Docker 容器内，**只暴露一个端口**；SQLite 数据库在挂载的 volume 里持久化。

**Tasks.**
1. `Dockerfile` 多阶段构建：
   - Stage 1（`builder`）：Python 3.12 slim base；装 uv；`uv sync --no-dev --frozen` 生成 clean venv
   - Stage 2（`runtime`）：同 Python slim base；从 builder copy `.venv` 和源码；`ENV PATH=/app/.venv/bin:$PATH`；`EXPOSE 8000`；`CMD ["uvicorn", "trading_journal.main:app", "--host", "0.0.0.0", "--port", "8000"]`
2. `docker-compose.yml` 给 dev 用：挂 SQLite 文件的 volume；注入 `.env`
3. 加 migration 启动步骤（两个选项：entrypoint 在启动 uvicorn 前跑 `alembic upgrade head`；或独立的 one-shot service。MVP 推荐 entrypoint，简单）

**Files created.** `Dockerfile`、`docker-compose.yml`，可能 `entrypoint.sh`。

**Manual verification.**
```bash
docker compose build
docker compose up
# 另一个服务器 shell：
curl -i http://localhost:8000/health    # 200
curl -i -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d '{"email":"docker@example.com","password":"correct horse battery"}'
# 期望：201
docker compose down
docker compose up                       # 重启
# 然后用刚 login 的 cookies：
curl -i http://localhost:8000/users/me -b cookies.txt   # 用户仍存在（DB 通过 volume 持久化）
```

**Automated tests.** MVP 阶段 optional——容器构建 smoke 测试可以以后进 CI。如需要可加一个测试断言 `Dockerfile` 和 `docker-compose.yml` 语法解析通过。

**Acceptance.** `docker compose up` 起来；完整 Phase 3 + Phase 4 curl 流程对容器化实例跑通；`docker compose down && up` 后数据持久。

## 6. 远程 SSH 开发

dev 机是远程的，需要从笔记本 browser/curl 访问。两种模式：

### 模式 A —— SSH 本地端口转发（推荐）

```bash
# 笔记本上：
ssh -L 8000:127.0.0.1:8000 user@server
# 笔记本访问 localhost:8000 = 隧道到服务器的 127.0.0.1:8000
```

- 保持 SSH session 在一个 terminal pane 开着
- dev server 绑 **`127.0.0.1`** 而**不是** `0.0.0.0`——把端口挡在公网外
- 后台 tunnel：`ssh -fNL 8000:127.0.0.1:8000 user@server`（`-f` 后台、`-N` 不开 shell）

### 模式 B —— 服务器端反向代理 + 鉴权（**MVP 不做**）

MVP 先跳过。将来真正公网部署时，再用 Caddy/Nginx + Let's Encrypt + 配置好的 FastAPI Users（已超出 tracer bullet 范围）。

### dev 阶段长期跑 uvicorn

`uvicorn --reload` 绑定前台。要扛 SSH 断线：

- **tmux**（首选）：`tmux new -s journal` → 跑 `uv run uvicorn ...` → `Ctrl-b d` 脱离。重连用 `tmux attach -t journal`
- 偏好 **screen** 也行
- **别只用 `&` 后台**——SSH 断开会 SIGHUP 进程

### Pre-flight 检查清单

| 检查 | 命令 |
|---|---|
| uv 已装 | `uv --version` |
| uv 能用 Python 3.12 | `uv python list` |
| 服务器端口空闲 | `ss -lnt sport = :8000` |
| 隧道工作 | 笔记本上 `ssh -L` 之后 `curl -s http://localhost:8000/health` |

## 7. 测试架构

### 测试框架设置

- **pytest** 用 `asyncio_mode = "auto"`（不需要每个测试加 `@pytest.mark.asyncio`）
- **httpx.AsyncClient** + `transport=ASGITransport(app=app)`——in-process 跑 FastAPI app，不需要起真实 server
- **测试 DB**：每个 test session 一个 tempfile SQLite（或每个测试一个，完全隔离），session 开始时 `alembic upgrade head` 一次，结束销毁。比 `create_all()` 快，并且**顺带验证 migration**
- **Settings 覆盖**：fixture monkeypatch `Settings` 指向测试 DB 和固定 cookie secret
- **依赖覆盖**：`app.dependency_overrides[get_session] = lambda: test_session` 让 endpoint 用测试 DB

### `tests/conftest.py` 的共享 fixtures

| Fixture | Scope | 用途 |
|---|---|---|
| `event_loop` | session | 给 async fixture 用的 event loop |
| `test_db_url` | session | tempfile SQLite 路径 |
| `migrated_db` | session | 跑一次 alembic upgrade head |
| `db_session` | function | 新 `AsyncSession`，测试后 rollback |
| `app` | session | FastAPI app 实例 |
| `client` | function | 含 dependency override 的 `AsyncClient` |
| `registered_user` | function | factory：注册用户，返回 `(email, password, user_id)` |
| `auth_client` | function | `client` + 已登录 cookie——多数 CRUD 测试用这个 |
| `second_user_client` | function | 第二个已登录用户——用于隔离测试 |

### 每个 feature 的覆盖要求

每个 endpoint（或 feature）测试覆盖：

1. **Happy path** —— 正常流程返回期望状态码 + 响应形状
2. **Auth** —— 每个受保护端点无 auth 时 401，有 valid auth 时 2xx
3. **Validation** —— 无效输入（缺必填、错枚举、错类型）返回 422 + 期望错误形状
4. **Authorization（多用户隔离）** —— 每个 owned 资源，第二个用户无法 read/modify/delete；断言 **404 不是 403**（不泄露存在性）
5. **业务边界** —— 域特定 corner case（如已 archived 不能再 archive、archived 默认排除 list 等）
6. **状态转换** —— 改状态的端点（delete → archived）通过后续查询验证最终状态

### 运行命令

```bash
# 全部测试
uv run pytest

# 指定文件，verbose，遇错即停
uv run pytest tests/test_accounts.py -vx

# 加 coverage（要装 pytest-cov 进 dev 依赖）
uv run pytest --cov=trading_journal --cov-report=term-missing
```

## 8. 人工验证 reference

完整 curl 跑通整个 tracer bullet。Phase 5 完成后在 Docker 容器里跑最完整；Phase 4 完成后对裸 `uvicorn` 跑也一样能跑通。

```bash
BASE=http://localhost:8000
JAR=cookies.txt; rm -f "$JAR"

# 0. Health
curl -fsSi "$BASE/health"

# 1. Register
curl -fsSi -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'

# 2. Login（设 cookie）
curl -fsSi -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' \
  -c "$JAR"

# 3. Me
curl -fsSi "$BASE/users/me" -b "$JAR"

# 4. 创建 account
ACCT=$(curl -fsS -X POST "$BASE/accounts" \
  -H 'Content-Type: application/json' \
  -b "$JAR" \
  -d '{"name":"IBKR Margin","broker":"IBKR","account_type":"margin","base_currency":"USD"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "Created account: $ACCT"

# 5. List
curl -fsSi "$BASE/accounts" -b "$JAR"

# 6. Update
curl -fsSi -X PATCH "$BASE/accounts/$ACCT" \
  -H 'Content-Type: application/json' \
  -b "$JAR" \
  -d '{"notes":"trading-journal MVP smoke test"}'

# 7. Soft-delete
curl -fsSi -X DELETE "$BASE/accounts/$ACCT" -b "$JAR"

# 8. 默认 list 应不含
curl -fsS "$BASE/accounts" -b "$JAR"

# 9. include_archived=true 应含
curl -fsS "$BASE/accounts?include_archived=true" -b "$JAR"

# 10. Logout
curl -fsSi -X POST "$BASE/auth/logout" -b "$JAR"

# 11. /me 现在应 401
curl -i "$BASE/users/me" -b "$JAR"
```

## 9. Tracer bullet 之后

Phase 0–5 完成后，下一轮迭代（按需另起 planning 文档）：

1. **CRUD 水平扩展** —— Instrument、Position、Trade、TradePlan、StrategyConfig、两张 strategy-meta 表。模式同 Account，但 Trade 和 Position 有业务逻辑（status 转换、冗余字段）需小心。每个逻辑组一轮，规模和 Phase 4 类似
2. **Computed fields 和聚合** —— PnL realized/unrealized、days_open、ROI、annualized。可能需要独立 `services/` 层
3. **Frontend —— Jinja 还是直接 Vue** —— 决策点：后端足够稳了就直接上 Vue + Vite，还是先做一轮 Jinja 让 CRUD 可视化便于测试？开放问题，到时候再决
4. **未来 auth / security 工作** —— 接近 broker API 集成时，写 `docs/design/auth-and-security.md`，按 [data-model.zh.md §7](./data-model.zh.md) 实现 MFA / AuditLog / BrokerCredential
5. **Postgres 对齐** —— 验证同一 migration 在 Postgres 上能干净应用；生产部署前在 CI 上跑全测试套件对 Postgres

---

## Changelog

- **v0.1（2026-05-18）** —— 初版方案。Tracer bullet 覆盖 Phase 0–5：骨架、FastAPI 启动、v0.2 完整 schema migration、FastAPI Users 鉴权、Account CRUD、Docker。暂不加前端。
