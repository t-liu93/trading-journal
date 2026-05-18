# MVP Implementation Plan — v0 Draft

**Language:** English | [中文](./mvp-implementation-plan.zh.md)

> Status: **DRAFT v0.1** (2026-05-18). The execution plan for the first end-to-end slice of the rebuild on `refactoring/rebuild`. Companion document to [data-model.md](./data-model.md). Iterate here before writing code.

## 1. Purpose and approach

This document is the **execution plan** for building the first working slice of the trading journal backend. The data model is settled in [data-model.md](./data-model.md); this plan is about how we turn that schema into a running, testable, deployable application — incrementally, with verifiable checkpoints.

**Approach: tracer bullet.** Instead of building every entity's CRUD up-front, we drive **one narrow end-to-end path** through every layer of the stack (DB → ORM → migration → API → auth → tests → Docker), then expand horizontally. The chosen path: **register a user → log in → create an account → list accounts** — all via JSON API, no UI yet.

Why: the riskiest part of this project isn't writing CRUD handlers (they're repetitive). It's making sure the pieces (SQLAlchemy + Alembic + FastAPI Users + uv + Docker + remote SSH workflow) actually fit together. A tracer bullet exposes that integration risk fast, on a small surface, so debugging stays cheap.

## 2. Scope

### In scope (this plan)

- Project skeleton with uv-managed venv, ruff, mypy, pytest
- FastAPI app with `/health` endpoint
- SQLAlchemy 2.x models for the **full v0.2 schema** (all tables from [data-model.md](./data-model.md), minus the future-auth tables in its §7)
- Alembic initial migration that creates the full schema
- FastAPI Users wired in with cookie session + DB-backed users
- `Account` CRUD endpoints (the vertical slice): create, list, get, update, soft-delete
- Detailed manual verification (curl recipes) at every phase
- Automated end-to-end tests covering happy paths and key corner cases
- Single-container Dockerfile exposing one port

### Explicitly NOT in scope (deferred)

- Jinja/HTML templates (no SSR UI yet — backend-only with curl/Postman)
- Vue frontend (later)
- CRUD for any entity besides `Account` (Position, Trade, Instrument, TradePlan, StrategyConfig come next pass)
- Any strategy-specific logic (wheel state machine, IC max-risk computation, PMCC roll detection)
- Statistics, charts, reports
- OAuth, MFA, audit logging, broker credential storage (already documented as future in [data-model.md §7](./data-model.md))
- Postgres deployment (SQLite for MVP; migration ready though)
- CI/CD pipeline

## 3. Tech stack summary

| Layer | Choice |
|---|---|
| Language | Python **3.12** |
| Package manager | **uv** (PEP 621 `pyproject.toml`, standard `.venv`, dev/prod dep groups) |
| Web framework | **FastAPI** (latest stable) |
| ORM | **SQLAlchemy 2.x** (async, typed `Mapped[...]` style) |
| Migrations | **Alembic** |
| Auth | **FastAPI Users** with cookie + DB strategy; bcrypt password hashing |
| DB (dev) | **SQLite** via `aiosqlite` |
| DB (prod, later) | **PostgreSQL** via `asyncpg` (schema is Postgres-compatible from day one) |
| Settings | **pydantic-settings** (env-var driven) |
| Validation / API schemas | **Pydantic v2** |
| Test framework | **pytest** + **pytest-asyncio** + **httpx.AsyncClient** |
| Linting + formatting | **ruff** |
| Type checking | **mypy** in strict mode |
| Container | **Docker** (single image, single port exposed) |

## 4. Directory structure

```
trading-journal/
├── .gitignore                          # extend with .venv/, .env, *.db, __pycache__/, .pytest_cache, .ruff_cache, .mypy_cache
├── .env.example                        # SQLite path, cookie secret, debug flag, etc.
├── README.md                           # short — points readers to docs/
├── docs/
│   └── design/
│       ├── data-model.md, data-model.zh.md
│       └── mvp-implementation-plan.md, mvp-implementation-plan.zh.md
├── backend/
│   ├── pyproject.toml                  # PEP 621 project + dependency-groups + tool configs (ruff, mypy, pytest)
│   ├── uv.lock                         # committed
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_schema.py  # full v0.2 schema in one revision
│   ├── src/trading_journal/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app factory + router wiring
│   │   ├── config.py                   # Settings via pydantic-settings
│   │   ├── db.py                       # async engine + sessionmaker + get_session dependency
│   │   ├── models/                     # SQLAlchemy models, one file per logical group
│   │   │   ├── __init__.py             # Base + import all models so Alembic sees them
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── instrument.py           # Instrument + OptionContract + ForexPair
│   │   │   ├── position.py
│   │   │   ├── trade.py
│   │   │   ├── trade_plan.py
│   │   │   ├── strategy_config.py
│   │   │   └── strategy_meta.py        # WheelCycleMeta, PmccCycleMeta
│   │   ├── schemas/                    # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   └── account.py
│   │   ├── api/                        # FastAPI routers
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   └── accounts.py
│   │   └── auth/                       # FastAPI Users wiring
│   │       ├── __init__.py
│   │       ├── users.py                # UserManager
│   │       ├── backend.py              # CookieTransport + DatabaseStrategy
│   │       └── deps.py                 # current_active_user dependency
│   └── tests/
│       ├── conftest.py                 # fixtures: app, async client, test DB, logged-in user
│       ├── test_health.py
│       ├── test_auth.py                # register, login, logout, /me, edge cases
│       └── test_accounts.py            # CRUD happy + corner cases
├── frontend/                           # placeholder for future Vue app
│   └── README.md                       # "Vue lives here once we get past tracer bullet"
├── Dockerfile                          # multi-stage: uv install → runtime
└── docker-compose.yml                  # dev convenience: app + volume for SQLite
```

## 5. Phased plan

Each phase has a **Goal**, **Tasks**, **Files**, **Manual verification** (curl), **Automated tests**, **Acceptance**. Phases are sequential — don't start phase N+1 until N's acceptance passes.

### Phase 0 — Project skeleton and tooling

**Goal.** A bootable project with venv, dependency management, linting, type checking, and test runner. No application logic yet.

**Tasks.**
1. Install uv on the dev server: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. `cd backend && uv init --package` to create `pyproject.toml` skeleton; remove the auto-generated `src/backend/` if present and start fresh as `src/trading_journal/`
3. Install Python via uv: `uv python install 3.12`
4. Create venv: `uv venv --python 3.12` (produces `backend/.venv/`)
5. Add runtime deps (`uv add`): `fastapi[standard]`, `sqlalchemy[asyncio]`, `aiosqlite`, `alembic`, `fastapi-users[sqlalchemy]`, `pydantic-settings`, `uvicorn[standard]`
6. Add dev deps (`uv add --dev`): `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`, `types-aiofiles` (and others as needed)
7. Configure tools in `pyproject.toml`:
   - `[tool.ruff]` — `line-length = 100`, `target-version = "py312"`, lint rules `["E", "F", "I", "B", "UP", "ASYNC"]`
   - `[tool.mypy]` — `strict = true`, `python_version = "3.12"`
   - `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]`
8. Create empty `tests/conftest.py` and a placeholder `tests/test_smoke.py` that asserts `True`
9. Extend root `.gitignore` for Python + uv artifacts
10. Create `.env.example` with placeholder vars

**Files created.** `backend/pyproject.toml`, `backend/uv.lock`, `backend/.venv/` (gitignored), `backend/src/trading_journal/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_smoke.py`, `.env.example`, updated `.gitignore`.

**Manual verification.**
```bash
cd backend
source .venv/bin/activate
ruff check .                # should report no issues
mypy src                    # should report success (empty project)
pytest -q                   # should report 1 passed (smoke test)
```

**Automated tests.** Only the smoke test — sanity check that pytest discovers and runs.

**Acceptance.** All four commands above exit 0.

---

### Phase 1 — FastAPI app boots, `/health` works

**Goal.** A running FastAPI app reachable via HTTP, with a health endpoint.

**Tasks.**
1. Write `config.py` — `Settings` class via `pydantic_settings.BaseSettings`, reads `.env`; fields: `database_url`, `cookie_secret`, `debug`
2. Write `main.py` — `create_app() -> FastAPI` factory, mounts `health` router; module-level `app = create_app()`
3. Write `api/health.py` — router with `GET /health` returning `{"status": "ok"}`
4. Document `uv run uvicorn trading_journal.main:app --reload --host 127.0.0.1 --port 8000` as the dev-run command

**Files created.** `src/trading_journal/config.py`, `src/trading_journal/main.py`, `src/trading_journal/api/__init__.py`, `src/trading_journal/api/health.py`, `tests/test_health.py`.

**Manual verification.**
```bash
# On the server (one tmux/screen pane):
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000

# On your laptop (after the SSH forward — see §6):
curl -i http://localhost:8000/health
# Expected: HTTP/1.1 200 OK, body {"status":"ok"}

curl -i http://localhost:8000/does-not-exist
# Expected: HTTP/1.1 404 Not Found
```

**Automated tests.**
- `test_health_ok` — `GET /health` returns 200 + correct JSON
- `test_unknown_route_404` — unknown path returns 404 with FastAPI default error shape

**Acceptance.** Both tests pass; manual curl produces expected output.

---

### Phase 2 — SQLAlchemy models + initial Alembic migration

**Goal.** All v0.2 tables (per [data-model.md](./data-model.md) §4 — excluding the future-auth tables in §7) defined as typed SQLAlchemy 2.x models, with one Alembic migration that creates them on an empty DB.

**Tasks.**
1. Write `db.py` — `Base = DeclarativeBase`; `async_engine = create_async_engine(settings.database_url)`; `async_session_maker`; `get_session()` async dependency for FastAPI
2. Write models, one file per logical group, all importing the shared `Base`:
   - `user.py` — User (matches FastAPI Users `SQLAlchemyBaseUserTableUUID` mixin shape)
   - `account.py` — Account
   - `instrument.py` — Instrument (base) + OptionContract + ForexPair as separate tables joined on `instrument_id`
   - `position.py` — Position with `strategy_type` enum
   - `trade.py` — Trade with `action` enum and `order_group_id`
   - `trade_plan.py` — TradePlan (event stream, unique on `(position_id, revision_no)`)
   - `strategy_config.py` — StrategyConfig (unique on `(user_id, strategy_type)`)
   - `strategy_meta.py` — WheelCycleMeta + PmccCycleMeta
3. Define enums in a shared `models/_enums.py` or co-located: `InstrumentKind`, `OptType`, `OptionStyle`, `AccountType`, `StrategyType`, `PositionStatus`, `TradeAction`, `FundingSource`
4. `models/__init__.py` re-exports everything so a single `import` brings all models into Base's metadata (Alembic auto-detect needs this)
5. Initialize Alembic: `cd backend && uv run alembic init -t async alembic` (template `async` is critical)
6. Edit `alembic/env.py` to import `Base` and set `target_metadata = Base.metadata`; set `sqlalchemy.url` from `settings.database_url`
7. Generate the migration: `uv run alembic revision --autogenerate -m "initial schema"` → review generated file → rename to `0001_initial_schema.py`
8. Manually review the autogenerated migration for: correct enum types, FK constraints, unique constraints, nullable settings. Tweak as needed
9. Apply: `uv run alembic upgrade head` (creates `dev.db` SQLite file in backend root)

**Files created.** `src/trading_journal/db.py`, all model files, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial_schema.py`.

**Manual verification.**
```bash
# Apply migration
uv run alembic upgrade head

# Inspect tables (SQLite)
sqlite3 dev.db ".tables"
# Expected: users, accounts, instruments, option_contracts, forex_pairs, positions, trades,
#           trade_plans, strategy_configs, wheel_cycle_metas, pmcc_cycle_metas, alembic_version

sqlite3 dev.db ".schema users"
# Expected: columns matching data-model.md §4.1

# Roundtrip test:
uv run alembic downgrade base
sqlite3 dev.db ".tables"      # Expected: only alembic_version (or empty)
uv run alembic upgrade head
sqlite3 dev.db ".tables"      # Expected: all tables back
```

**Automated tests.**
- `test_alembic_upgrade_creates_all_tables` — boots a temp SQLite, runs `alembic upgrade head`, asserts expected table names exist
- `test_alembic_downgrade_roundtrip` — upgrade → downgrade → upgrade, no errors, ends in expected state
- `test_models_can_be_imported` — sanity that `models/__init__.py` imports cleanly

**Acceptance.** Migration applies cleanly to fresh DB; all expected tables exist with correct columns; downgrade roundtrip works; all three tests pass.

---

### Phase 3 — Auth via FastAPI Users

**Goal.** Users can register, log in (cookie session), call a protected endpoint, and log out.

**Tasks.**
1. Implement `auth/users.py` — `UserManager(BaseUserManager[User, UUID])` (override `on_after_register` to log; rest can stay default)
2. Implement `auth/backend.py` — `CookieTransport(cookie_max_age=...)` + `DatabaseStrategy` factory (DB-backed sessions; uses `SQLAlchemyAccessTokenDatabase`). The corresponding table must be added in Phase 2 model (`AccessToken`) and present in the initial migration — **add now if missed in Phase 2 and create a 0002 migration**
3. Implement `auth/deps.py` — `current_active_user` dependency
4. Wire `fastapi_users.get_auth_router(...)` and `get_register_router(...)` into `main.py` under `/auth`
5. Wire `fastapi_users.get_users_router(...)` under `/users` for `/users/me`

**Files created/changed.** `auth/users.py`, `auth/backend.py`, `auth/deps.py`, updates to `main.py`, possibly `0002_access_tokens.py` migration (or rolled into 0001 if caught early), updates to `models/user.py` for `AccessToken`.

**Manual verification.**
```bash
# Register
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'
# Expected: 201 Created, response body with user fields (id, email, is_active=true, is_verified=false)

# Re-register with same email
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'
# Expected: 400 Bad Request, REGISTER_USER_ALREADY_EXISTS error code

# Login (note: form-urlencoded, not JSON; FastAPI Users uses OAuth2 password form)
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=correct horse battery" \
  -c cookies.txt
# Expected: 204 No Content; cookies.txt contains a session cookie (HttpOnly)

# Login with wrong password
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=wrong"
# Expected: 400 Bad Request, LOGIN_BAD_CREDENTIALS

# /users/me without cookie
curl -i http://localhost:8000/users/me
# Expected: 401 Unauthorized

# /users/me with cookie
curl -i http://localhost:8000/users/me -b cookies.txt
# Expected: 200 OK, user fields

# Logout
curl -i -X POST http://localhost:8000/auth/logout -b cookies.txt
# Expected: 204 No Content; subsequent /users/me with same cookies.txt → 401
```

**Automated tests** (in `tests/test_auth.py`):
- `test_register_success`
- `test_register_duplicate_email_rejected`
- `test_register_invalid_email_400`
- `test_register_password_too_short_400` (FastAPI Users default min length)
- `test_login_success_sets_cookie`
- `test_login_wrong_password_400`
- `test_login_unknown_user_400`
- `test_me_without_cookie_401`
- `test_me_with_cookie_200`
- `test_logout_invalidates_session` — login, hit /me success, logout, hit /me → 401

**Acceptance.** All curl commands produce expected output; all 10 tests pass.

---

### Phase 4 — Account CRUD (the vertical slice)

**Goal.** Authenticated users can create, list, read, update, and soft-delete (archive) their own `Account` rows — and crucially cannot see or modify other users'.

**Tasks.**
1. Pydantic schemas in `schemas/account.py`:
   - `AccountCreate` — name, broker, account_type, base_currency, notes (no user_id; derived from auth)
   - `AccountRead` — all fields including timestamps and archived_at
   - `AccountUpdate` — all fields optional (PATCH-style)
2. Router in `api/accounts.py`:
   - `POST /accounts` → 201, creates account owned by `current_active_user`
   - `GET /accounts` → 200, lists `current_active_user`'s accounts, excludes archived by default; `?include_archived=true` includes them
   - `GET /accounts/{account_id}` → 200 if owned + not archived; 404 otherwise (avoid leaking existence to other users)
   - `PATCH /accounts/{account_id}` → 200, updates allowed fields; 404 if not owned
   - `DELETE /accounts/{account_id}` → 204, sets `archived_at = now()`; 404 if not owned or already archived
3. Wire the router under `/accounts` in `main.py`

**Files created.** `schemas/__init__.py`, `schemas/account.py`, `api/accounts.py`.

**Manual verification.** (Assumes you've completed Phase 3's register/login and have `cookies.txt`.)
```bash
# Create
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"IBKR Margin","broker":"IBKR","account_type":"margin","base_currency":"USD"}'
# Expected: 201, JSON with id, all fields, archived_at=null

# Create with invalid account_type
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"X","broker":"X","account_type":"checkings","base_currency":"USD"}'
# Expected: 422 Unprocessable Entity, validation error

# Create without auth
curl -i -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -d '{"name":"X","broker":"X","account_type":"cash","base_currency":"USD"}'
# Expected: 401

# List
curl -i http://localhost:8000/accounts -b cookies.txt
# Expected: 200, array of own accounts

# Get specific
curl -i http://localhost:8000/accounts/<id-from-create> -b cookies.txt
# Expected: 200

# Get nonexistent / not-owned
curl -i http://localhost:8000/accounts/00000000-0000-0000-0000-000000000000 -b cookies.txt
# Expected: 404

# Update
curl -i -X PATCH http://localhost:8000/accounts/<id> \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"notes":"changed my mind"}'
# Expected: 200, updated fields reflected

# Soft-delete
curl -i -X DELETE http://localhost:8000/accounts/<id> -b cookies.txt
# Expected: 204

# Verify excluded from default list
curl http://localhost:8000/accounts -b cookies.txt
# Expected: account no longer in result

# Verify included with ?include_archived=true
curl 'http://localhost:8000/accounts?include_archived=true' -b cookies.txt
# Expected: archived account present with archived_at set

# Cross-user isolation: register a second user, log in as Bob, try to GET Alice's account
# Expected: 404 (not 403, to avoid leaking existence)
```

**Automated tests** (in `tests/test_accounts.py`):
- Happy path: `test_create_account`, `test_list_accounts_empty`, `test_list_accounts_after_create`, `test_get_account_by_id`, `test_update_account_partial`, `test_soft_delete_excludes_from_default_list`, `test_include_archived_param`
- Auth: `test_create_requires_auth`, `test_list_requires_auth`, `test_get_requires_auth`, `test_update_requires_auth`, `test_delete_requires_auth`
- Validation: `test_create_rejects_invalid_account_type`, `test_create_rejects_missing_required_fields`, `test_create_rejects_invalid_currency_code` (if validated), `test_update_rejects_unknown_field` (or silently ignored — pick a behavior and pin it)
- Authorization (multi-user): `test_list_only_returns_own_accounts`, `test_get_other_users_account_returns_404`, `test_update_other_users_account_returns_404`, `test_delete_other_users_account_returns_404`
- Idempotency / edge: `test_delete_already_archived_returns_404`, `test_get_archived_by_default_returns_404`

**Acceptance.** All curl commands produce expected output; all tests pass; cross-user isolation verified end-to-end.

---

### Phase 5 — Docker single-container deployment

**Goal.** The app runs inside one Docker container exposing exactly one port; SQLite database persists in a mounted volume.

**Tasks.**
1. Write `Dockerfile` with multi-stage build:
   - Stage 1 (`builder`): Python 3.12 slim base; install uv; `uv sync --no-dev --frozen` to produce a clean venv
   - Stage 2 (`runtime`): same Python slim base; copy `.venv` and source from builder; `ENV PATH=/app/.venv/bin:$PATH`; `EXPOSE 8000`; `CMD ["uvicorn", "trading_journal.main:app", "--host", "0.0.0.0", "--port", "8000"]`
2. Write `docker-compose.yml` for dev convenience: mounts a volume for the SQLite file; injects `.env`
3. Add a startup migration step (either: entrypoint runs `alembic upgrade head` before launching uvicorn, or a separate one-shot service; recommend entrypoint for MVP simplicity)

**Files created.** `Dockerfile`, `docker-compose.yml`, possibly `entrypoint.sh`.

**Manual verification.**
```bash
docker compose build
docker compose up
# In another shell on the server:
curl -i http://localhost:8000/health    # 200
curl -i -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d '{"email":"docker@example.com","password":"correct horse battery"}'
# Expected: 201
docker compose down
docker compose up                       # restart
# Then with cookies from a fresh login:
curl -i http://localhost:8000/users/me -b cookies.txt   # user still present (DB persisted via volume)
```

**Automated tests.** Optional for MVP — container build smoke test could run in CI later. Add a single test that asserts `Dockerfile` and `docker-compose.yml` parse (syntax) if helpful.

**Acceptance.** `docker compose up` brings the app up; full Phase 3 + Phase 4 curl walkthrough succeeds against the containerized instance; data persists across `docker compose down && up`.

## 6. Remote SSH development

Since the dev box is remote, you need a way to hit the app from your laptop's browser/curl. Two patterns:

### Pattern A — SSH local port forward (recommended)

```bash
# On your laptop:
ssh -L 8000:127.0.0.1:8000 user@server
# Now anything you do to localhost:8000 on your laptop tunnels to 127.0.0.1:8000 on the server.
```

- Keep the SSH session open in one terminal pane
- Bind the dev server to `127.0.0.1` on the server (not `0.0.0.0`) — keeps the port off the public network
- For background tunnels: `ssh -fNL 8000:127.0.0.1:8000 user@server` (`-f` background, `-N` no shell)

### Pattern B — Server-side reverse proxy + auth (NOT for tracer bullet)

Skip for MVP. When you publicly expose this, do it via Caddy/Nginx + Let's Encrypt + properly configured FastAPI Users (which is past tracer bullet).

### Running uvicorn long-term during development

`uvicorn --reload` ties to the foreground. To survive SSH disconnects:

- **tmux** (preferred): `tmux new -s journal` → run `uv run uvicorn ...` → `Ctrl-b d` to detach. Reattach with `tmux attach -t journal`
- **screen** equivalent if you prefer
- Don't background with `&` alone — losing the SSH session kills the process

### Pre-flight checklist

| Check | Command |
|---|---|
| uv installed | `uv --version` |
| Python 3.12 available via uv | `uv python list` |
| Server-side port free | `ss -lnt sport = :8000` |
| Tunnel works | `curl -s http://localhost:8000/health` from laptop after `ssh -L` |

## 7. Testing architecture

### Test framework setup

- **pytest** with `asyncio_mode = "auto"` (no per-test `@pytest.mark.asyncio` decorator needed)
- **httpx.AsyncClient** with `transport=ASGITransport(app=app)` — runs the FastAPI app in-process, no live server needed
- **Test database**: a fresh tempfile SQLite per test session (or even per test for fully isolated tests), created with `alembic upgrade head` once at session start, dropped at end. Faster than `create_all()` and also exercises migrations
- **Settings override**: a fixture that monkeypatches `Settings` to point at the test DB and a fixed cookie secret
- **Dependency overrides**: `app.dependency_overrides[get_session] = lambda: test_session` so endpoints use the test DB

### Shared fixtures in `tests/conftest.py`

| Fixture | Scope | Purpose |
|---|---|---|
| `event_loop` | session | event loop for async fixtures |
| `test_db_url` | session | tempfile SQLite path |
| `migrated_db` | session | runs alembic upgrade head once |
| `db_session` | function | fresh `AsyncSession`, rolled back after test |
| `app` | session | FastAPI app instance |
| `client` | function | `AsyncClient` with dependency overrides |
| `registered_user` | function | factory: registers a user, returns `(email, password, user_id)` |
| `auth_client` | function | `client` plus a logged-in cookie — most CRUD tests use this |
| `second_user_client` | function | a second logged-in user — for isolation tests |

### Coverage expectations per feature

For each endpoint (or feature), tests cover:

1. **Happy path** — the normal flow yields expected status code and response shape
2. **Auth** — every protected endpoint returns 401 without auth and 200/2xx with valid auth
3. **Validation** — invalid inputs (missing required fields, wrong enum values, wrong types) return 422 with the expected error shape
4. **Authorization (multi-user isolation)** — for every owned resource, a second user cannot read/modify/delete; assert 404 (not 403, to avoid existence-leaking)
5. **Business edge cases** — domain-specific corner cases (e.g., archived account cannot be re-archived; archived account excluded from list by default; etc.)
6. **State transitions** — for endpoints that change state (delete → archived), verify the after-state via a follow-up query

### Run commands

```bash
# All tests
uv run pytest

# Specific file with verbose output and stop on first failure
uv run pytest tests/test_accounts.py -vx

# With coverage (add pytest-cov to dev deps if you want this)
uv run pytest --cov=trading_journal --cov-report=term-missing
```

## 8. Manual verification reference

Full curl walkthrough that exercises the tracer bullet end-to-end. Run after Phase 5 (in the Docker container) for the most thorough check; runs equally well after Phase 4 against the bare `uvicorn`.

```bash
BASE=http://localhost:8000
JAR=cookies.txt; rm -f "$JAR"

# 0. Health
curl -fsSi "$BASE/health"

# 1. Register
curl -fsSi -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}'

# 2. Login (cookie set)
curl -fsSi -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' \
  -c "$JAR"

# 3. Me
curl -fsSi "$BASE/users/me" -b "$JAR"

# 4. Create account
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

# 8. Should be gone from default list
curl -fsS "$BASE/accounts" -b "$JAR"

# 9. Should appear with include_archived=true
curl -fsS "$BASE/accounts?include_archived=true" -b "$JAR"

# 10. Logout
curl -fsSi -X POST "$BASE/auth/logout" -b "$JAR"

# 11. /me should now 401
curl -i "$BASE/users/me" -b "$JAR"
```

## 9. After this tracer bullet

Once Phase 0–5 ship, the next iterations (separate planning docs as needed):

1. **Horizontal expansion of CRUD** — Instrument, Position, Trade, TradePlan, StrategyConfig, the two strategy-meta tables. Same patterns as Account, but Trade and Position need careful business logic (status transitions, denormalized fields). Estimate: one pass per logical group, similar size to Phase 4.
2. **Computed fields and aggregates** — PnL realized/unrealized, days_open, ROI, annualized. May warrant a separate `services/` layer.
3. **Frontend — Jinja or jump to Vue.** Decision point: enough backend stability to commit to Vue + Vite, or do a quick Jinja phase to make CRUD visually testable? Open question, decide later.
4. **Future auth/security work** — when broker API integration approaches, write `docs/design/auth-and-security.md` and implement MFA / AuditLog / BrokerCredential per [data-model.md §7](./data-model.md).
5. **Postgres parity** — verify the same migration applies cleanly to Postgres; run the full test suite against Postgres in CI before any production deployment.

---

## Changelog

- **v0.1 (2026-05-18)** — Initial plan. Tracer bullet covering Phase 0–5: skeleton, FastAPI boot, full v0.2 schema migration, FastAPI Users auth, Account CRUD, Docker. No frontend yet.
