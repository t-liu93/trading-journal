# V1 Phase F6 —— 部署与发布就绪

**Language:** [English](./v1-implementation-plan-f6.md) | 中文

> 状态：**DRAFT v0.2**（2026-05-30）。V1 收尾 phase。配套
> [v1-release-plan.zh.md](./v1-release-plan.zh.md)（V1 北极星 —— 见 §6.5 F6、§8.1
> CI gate、§8.2 Postgres parity、§8.3 walkthrough）、
> [frontend-expansion-plan.zh.md §F6](./frontend-expansion-plan.zh.md)（macro）、
> [mvp-implementation-plan.zh.md §5 Phase 5](./mvp-implementation-plan.zh.md)
> （最初的单容器设想）。先在这里迭代，再写任何代码。
>
> **范围说明。** F6 最初只是「单容器 Docker 接线」。本 plan 把它拓宽为 V1 收尾
> phase，覆盖用户在 2026-05-30 一并提出的三件交付物：**(A) Docker 镜像构建**、
> **(B) CI/CD**、**(C) 全功能 walkthrough 指南**。三者作为一个 phase 出货，因为它们
> 是「发布就绪」这一捆 —— 应用本身已经能用（F0–F5 已完成）；F6 让它*可部署、可持续
> 验证、有文档*。
>
> **执行顺序（2026-05-30 修订）：A → C → B** —— 先手动 build 镜像，手动 walkthrough
> 一遍，再把这套已验证的 build 自动化成 CI。§4（Part B）放最后，现在不细化。

## 1. 目的与背景

F0–F5 与 P6–P12 均已在 `refactoring/rebuild` 上交付（后端 406 条测试全绿；
`vue-tsc` + `vite build` clean）。应用对 V1 已功能完整。缺的是代码周边那些把
「能在我笔记本上跑」变成「可部署、有防护的交付物」的东西：

- **A —— Docker 镜像。** 单容器，FastAPI 从 `/` 托管 Vite 构建的 SPA、从 `/api/*`
  提供 API（这个 URL 切分从第一天就为此设计 —— 见
  [`main.py` docstring](../../backend/src/trading_journal/main.py)）。
- **B —— CI/CD。** GitHub Actions：每次 push / PR 跑后端质量 gate，`main` 上构建并
  发布镜像到 GHCR。
- **C —— Walkthrough 指南。** 一份双语文档，带新用户端到端走完每一个 V1 功能。同时
  充当 [v1-release-plan.zh.md §8.3](./v1-release-plan.zh.md#83-人工验收-walkthrough)
  推迟到 F6 的人工验收脚本（触发条件现已激活）。

### 已敲定决策（不要再 re-derive）

2026-05-30 与用户锁定：

1. **Plan-first。** 本文档先写、先评审，再落任何代码，遵循项目的
   [phase-plan 约定](./v1-release-plan.zh.md#1-目的与维护约定)。
2. **镜像 registry = GHCR。** `ghcr.io/t-liu93/trading-journal`。CI 用内置
   `GITHUB_TOKEN`（`packages: write`）鉴权 —— 无需额外 secret。
3. **CI 后端范围 = 标准。** `ruff check` + `mypy --strict` + `pytest` + §8.1
   **codegen 新鲜度 gate**。前端 `npm run build` 是**可选 job**（V1 接受 non-blocking；
   见 §4.4）。**Postgres parity（§8.2）不在本 phase** —— 留作部署前 checklist 项。
4. **单容器 SPA 模型。** FastAPI 把构建好的 `dist/` 挂在 `/`；API 保持 `/api/*`
   前缀；`/docs` + `/openapi.json` 留在根。SQLite 仍是 V1 运行时 DB（Postgres 路径
   保持纯加/线下）。
5. **Walkthrough = 独立双语文档。** `docs/walkthrough.md` + `docs/walkthrough.zh.md`，
   从 v1-release-plan §8.3 链接过去 —— 不内联进 release plan，不并入仓库 README。
6. **执行顺序 = A → C → B。** 手动 build 镜像 → 手动 walkthrough → 把同一套 build
   自动化成 CI。§4（Part B）放最后。
7. **静态服务 = 纯 catch-all。** 一个 GET 路由：请求的文件存在就返回该文件，否则返回
   `index.html`（交给 SPA router）。外加两个 guard：未匹配的 `/api/*` 返回真正的
   **404**（而非 SPA 外壳）、**路径穿越**校验保证读取不出 `dist/`。不单独 mount
   `/assets` —— catch-all 已覆盖 `assets/` 和根级文件（`favicon.svg`、`icons.svg`）。
8. **uv：仅构建期用。** 构建期 `uv sync --frozen --no-dev --no-install-project` 把第三方
   依赖装进 `/app/.venv`；**运行镜像直接调 `uvicorn`、不含 `uv`**（更小、启动确定 ——
   `uv run` 会在启动时重新校验/同步环境）。项目包通过 `PYTHONPATH=/app/src` 被找到
   （与 alembic 的 `prepend_sys_path = src` 一致），不装进 venv。
9. **非 root 走 compose，不在 Dockerfile。** 镜像里不固定 `USER`；`docker-compose.yml`
   设 `user: "${PUID:-1000}:${PGID:-1000}"`，进程以宿主用户身份跑，`/data` 是 **bind
   mount**（`./data:/data`）—— SQLite 文件归宿主所有、便于备份（取代 v0.1 的具名 volume）。
10. **运维默认值。** compose `healthcheck`（`python urllib` → `/api/health`）+
    `restart: unless-stopped`；镜像按 version 打 tag（不 pin digest）；单容器同时托管
    SPA 与 API —— **无 nginx / 反代**（如需 HTTPS 终止，放在容器外的宿主上）。

## 2. 范围

### 本 plan 范围内

- **A。** 多阶段 `Dockerfile`、`.dockerignore`、`main.py` 里的 SPA 静态挂载 +
  客户端 fallback（config 门控，无 build 的 dev 环境仍能启动）、启动 uvicorn 前先
  `alembic upgrade head` 的容器 entrypoint，以及一份用于 dev/prod 等价的
  `docker-compose.yml`（宿主用户 + bind-mount `./data` + `.env`）。
- **B。** `.github/workflows/ci.yml`，含：`backend-quality`（ruff/mypy/pytest）、
  `codegen-freshness`（起后端 → `npm run codegen` → `git diff --exit-code`）、可选
  `frontend-build`、`docker-image`（始终 build；仅 `main` 上 push 到 GHCR）。
- **C。** `docs/walkthrough.md` + `.zh.md`，覆盖每条主 V1 流程，带「启动应用」前言
  （dev 模式 + docker 模式）和每条流程的步骤 + 预期结果。v1-release-plan §8.3 展开为
  指向它的入口。

### 显式不在范围内（推迟）

- **CI 里的 Postgres / parity 矩阵**（§8.2）—— 部署前 checklist，不是 F6。
- **HTTPS / TLS 终止** —— 由容器外宿主反向代理处理。
- **多实例 / 水平扩展 / 外部 session 存储。**
- **容器内 Postgres** —— SQLite 仍是 V1 运行时。
- **Playwright / Vitest** —— 前端 e2e/单测仍推迟（V1.x）。
- **语义化版本发布自动化 / changelog bot / GitHub Releases** —— `docker-image` job
  按 branch + SHA 打 tag；tag 驱动的 semver release 是 V1.x 的锦上添花（§10 提及，
  此处不做）。
- **`.env` / GitHub Actions secrets 之外的 secret 管理**（不上 Vault 之类）。

## 3. Part A —— Docker 镜像构建

### 3.1 多阶段 `Dockerfile`（仓库根）

三阶段让运行时镜像保持精简（无 Node、无构建工具链、无 dev 依赖）。前端构建**不**需要
运行中的后端 —— `src/api/schema.d.ts` 已提交，所以 `vite build` 自包含。

```dockerfile
# syntax=docker/dockerfile:1

# --- Stage 1: frontend builder -------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
# .npmrc（legacy-peer-deps=true）必须在 `npm ci` 之前 COPY。
COPY frontend/package.json frontend/package-lock.json* frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build            # vue-tsc -b && vite build -> /app/frontend/dist

# --- Stage 2: backend deps (uv) ------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend-deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# 只把运行时依赖装进 /app/.venv（不含 dev group）。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- Stage 3: runtime ----------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    DATABASE_URL=sqlite+aiosqlite:////data/app.db
WORKDIR /app
COPY --from=backend-deps /app/.venv /app/.venv
COPY backend/src/ ./src/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend /app/frontend/dist/ ./static/
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    mkdir -p /data
ENV PYTHONPATH=/app/src
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "trading_journal.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**已确认（2026-05-30 讨论）—— v0.1 两个待定项都收口：**
- `frontend/package-lock.json` **已**提交（90 KB，git 跟踪）—— v0.1「没有 lockfile」是
  我查漏了。`npm ci` 直接可用，无需改动。
- **uv：** deps 阶段保留 `uv sync --frozen --no-dev --no-install-project`，**运行期直接
  调 `uvicorn`、运行镜像不含 `uv`**。项目通过 `PYTHONPATH=/app/src` 被找到（与 alembic
  的 `prepend_sys_path = src` 一致）；不装进 venv，让依赖层缓存独立于源码变动。

### 3.2 SPA 静态挂载 + 客户端 fallback（`main.py` + `config.py`）

规则就是**「该返回什么就返回什么，否则返回 SPA 外壳」**：一个 GET catch-all，请求的
文件在 `dist/` 里就返回该文件，否则返回 `index.html`（让客户端 router 处理 `/positions/42`
这种深链刷新）。它注册在 API router **之后**，所以 `/api/*`、`/docs`、`/openapi.json`
先匹配、永不落到它。两个 guard 把它做扎实（决策 #7）：未匹配的 `/api/*` → 真正的 404；
路径穿越 → 限制在 `dist/` 内。

```python
# config.py —— 新增一个字段
static_dir: str | None = None   # 容器里设为构建好的 dist/ 路径

# main.py —— create_app() 末尾、`return app` 之前
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse

static_dir = settings.static_dir
if static_dir and Path(static_dir).is_dir():
    dist = Path(static_dir).resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # 落到这里的都是未匹配的 GET —— 即客户端路由 —— 因为 /api/*、/docs、
        # /openapi.json 注册得更早、会先匹配。
        # Guard #2：未匹配的 /api/* 应是真正的 404，而非 SPA 外壳。
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        # Guard #3：仅当文件存在且仍在 dist 内才返回（挡住 ../../etc/passwd 式
        # 穿越）。resolve() 会折叠 '..'。
        candidate = (dist / full_path).resolve()
        if candidate.is_relative_to(dist) and candidate.is_file():
            return FileResponse(candidate)
        # 否则就是客户端路由 → 返回 SPA 外壳。
        return FileResponse(dist / "index.html")
```

不需要单独 mount `/assets` —— catch-all 同样会 serve `assets/*` 和根级文件
（`favicon.svg`、`icons.svg`）。`FileResponse` 仍会设 `Content-Type` / `Last-Modified`
/ ETag 并支持 Range，对 SPA 的静态量足够。Config 门控：`STATIC_DIR` 未设时（本地 dev、
Vite 跑在 :5173）整块跳过，dev 代理照常工作。catch-all 仅 GET，绝不遮蔽 API 的
POST/PATCH/DELETE。

### 3.3 容器 entrypoint（`backend/docker-entrypoint.sh`）

```sh
#!/bin/sh
set -e
alembic upgrade head      # 幂等；把 /data/app.db 升到 head
exec "$@"                 # 交棒给 CMD（uvicorn）
```

托管前先对 bind-mount 上的 SQLite 跑迁移。`exec` 让 uvicorn 作为 PID 1，信号处理干净。
因为进程以宿主 UID 运行（compose `user:`），宿主上的 `./data` 目录必须在 `up` 之前就
存在、且属主是该用户 —— 否则迁移无法创建 `/data/app.db`。（见 §3.4 与 §8 recipe。）

### 3.4 `docker-compose.yml`（仓库根）

```yaml
services:
  app:
    build: .
    image: ghcr.io/t-liu93/trading-journal:dev
    user: "${PUID:-1000}:${PGID:-1000}"     # 以宿主用户身份跑 → app.db 归宿主所有
    ports: ["8000:8000"]
    environment:
      COOKIE_SECRET: ${COOKIE_SECRET:?set in .env}
      COOKIE_SECURE: ${COOKIE_SECURE:-false}
      DEBUG: ${DEBUG:-false}
      DATABASE_URL: sqlite+aiosqlite:////data/app.db
      STATIC_DIR: /app/static
    volumes:
      - ./data:/data                          # bind mount → 从宿主直接备份 app.db
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').getcode()==200 else 1)"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s
    restart: unless-stopped
```

- **`user:`** 让容器以宿主 UID/GID（默认 1000 —— 你的用户）运行，写进 bind mount 的
  SQLite 文件归你所有、而非 root。
- **`./data:/data` bind mount** 把 `app.db` 放到宿主上、便于直接备份。**坑：** 必须在
  `up` *之前* 创建 `./data`（属主是你，`mkdir -p data`）—— 否则 Docker 以 root 创建它，
  UID-1000 进程写不进、迁移失败。运行镜像里仍 `mkdir -p /data` 作为不带 bind mount 的
  纯 `docker run` 兜底。
- **`healthcheck`** 通过 `python -c urllib` 打 `/api/health`（slim 镜像没 curl/wget，但
  一定有 python）。**`restart: unless-stopped`** 让它跨宿主重启自动拉起。
- `.env` 提供 `COOKIE_SECRET`（唯一必填 secret）；一旦在 HTTPS 后面，`COOKIE_SECURE`
  必须为 `true`。

### 3.5 `.dockerignore` + 环境变量说明

`.dockerignore` 排除 `node_modules`、`.venv`、`**/dev.db`、`.git`、test 缓存、
`docs/`、`review-notes/`，以及宿主 `data/` 目录 —— 让构建上下文精简，也避免泄漏 dev DB
或本地数据。

`.env.example` 增加一个简短的「Docker / 生产」块，记录 `STATIC_DIR`、`PUID`/`PGID`
（容器的宿主用户；默认 1000）、`./data` bind mount + `/data/app.db` 路径，以及「HTTPS
后面 `COOKIE_SECURE=true`」规则。

## 4. Part B —— CI/CD（GitHub Actions）

单 workflow `.github/workflows/ci.yml`。触发：`push` 到 `main` 与
`refactoring/rebuild`，以及目标为 `main` 的 `pull_request`。默认
`permissions: contents: read`；`docker-image` job 提升到 `packages: write`。

### 4.1 `backend-quality` job

- `actions/checkout`。
- `astral-sh/setup-uv`（cache key 基于 `backend/uv.lock`）。
- `uv sync --frozen`（working-directory `backend`）。
- `uv run ruff check .`
- `uv run mypy --strict src`（mypy 配置已在 `pyproject.toml`）。
- `uv run pytest`（406 条测试；`asyncio_mode=auto` 已配）。

### 4.2 `codegen-freshness` job（§8.1 gate）

捕捉「后端 schema 改了但 `schema.d.ts` 没重新生成」：

1. `uv sync --frozen` + `npm ci`（前端）。
2. `uv run alembic upgrade head` 对一个一次性 SQLite。
3. 起 `uv run uvicorn trading_journal.main:app &`；等 `/api/health`。
4. `npm run codegen`（打 `http://127.0.0.1:8000/openapi.json`）。
5. `git diff --exit-code frontend/src/api/schema.d.ts` —— 过期则失败。

### 4.3 `frontend-build` job（可选、non-blocking）

- `actions/setup-node` + `npm ci` + `npm run build`（`vue-tsc -b && vite build`）。
- 标 `continue-on-error: false`，但作为独立 job，让纯前端的破坏一目了然。（按决策 3
  它是「可选」—— 指 V1 必过的是*后端* gate；我们仍跑它以捕捉类型/构建破坏。）

### 4.4 `docker-image` job（始终 build；`main` 上 push）

- `needs: [backend-quality]`。
- `docker/setup-buildx-action`。
- `docker/login-action` → `ghcr.io`，用 `${{ github.actor }}` / `${{ secrets.GITHUB_TOKEN }}`。
- `docker/metadata-action` → 给 `ghcr.io/t-liu93/trading-journal` 打 `sha-<short>`
  和 `latest`（`latest` 仅在 `main`）。
- `docker/build-push-action`，`push: ${{ github.ref == 'refs/heads/main' }}`，
  用 GitHub Actions 层缓存（`cache-from/to: type=gha`）。

在非 `main`（PR、`refactoring/rebuild`）上镜像**只 build 不 push** —— 证明 Dockerfile
保持绿色，又不污染 registry。

## 5. Part C —— 全功能 walkthrough 指南

### 5.1 形式与落点

`docs/walkthrough.md` + `docs/walkthrough.zh.md`（独立双语，按决策 5）。
v1-release-plan §8.3 展开为一行入口 + 验收 checklist 链接到这里。这是面向用户的活文档，
不是 phase plan，所以放在 `docs/` 而非 `docs/design/`。

### 5.2 流程覆盖 checklist（即验收脚本）

按依赖顺序覆盖每条主 V1 路径：

1. **注册 → 登录 → 登出**（FastAPI Users cookie session）。
2. **Account CRUD** —— 创建 / 编辑 / 归档（F1）。
3. **Instrument** —— 浏览 `/instruments`；通过 `InstrumentForm` 创建 stock / option /
   forex；走一遍 **`InstrumentPicker` 内嵌创建**（`allowCreate`，含两步式期权流程）
   （F2 + F3 决策 1）。
4. **Strategy config** —— 在 `/settings/strategies` 设一个 per-strategy 曝光上限。
5. **Position** —— 创建（用 `InstrumentPicker`）、编辑、详情页四个 tab：**Overview**
   （手填字段 + 前端派生值）、**Meta**（wheel funding/loan/interest、pmcc LEAP picker）、
   **Plan**（追加一条 TradePlan revision）、**Trades**（占位 → 第 6 步后变 live）（F3）。
6. **Trade 录入** —— 单条 trade；然后用 **Custom multi-leg** 表单录 §4.5.2 的四种事件：
   开 iron condor（4 腿）、assignment（2）、exercise（2）、expire（1）；确认 Trades tab
   上 pattern badge 正确渲染（F4）。
7. **Dashboard** —— per-currency PnL 卡、open/closed 表、按月已实现 PnL 图、胜率仪表（F5）。
8. **删除路径** —— position 有附属时 409；trade 软删 + `?include_archived=true`。

### 5.3 文档结构

- **0. 前置与启动应用** —— 两个小节：*Dev 模式*（`uv run uvicorn … --reload` +
  `npm run dev`、代理）与 *Docker 模式*（`docker compose up` + 首次启动的
  `COOKIE_SECRET`）。每个主要屏幕一个截图/录屏位（v0.1 可用占位）。
- **1–8。** 上面每条流程一节：编号步骤、要填的确切字段值、以及每步后的**预期结果**
  （这样它既是教程也是验收脚本）。
- **附录** —— §4.5.2 事件→行的速查表（每种多腿事件该录哪些腿），交叉链到
  [data-model.zh.md §4.5.2](./data-model.zh.md#452-notion-event--atomic-trade-mapping)。

## 6. 文件

**新增**
- `Dockerfile`、`.dockerignore`、`docker-compose.yml`（仓库根）
- `backend/docker-entrypoint.sh`
- `.github/workflows/ci.yml`（Part B，最后做）
- `docs/walkthrough.md`、`docs/walkthrough.zh.md`

**修改**
- `backend/src/trading_journal/main.py`（SPA catch-all + `/api` 404 + 穿越防护）
- `backend/src/trading_journal/config.py`（`static_dir` 设置）
- `.env.example`（Docker/生产块）
- `docs/design/v1-release-plan.md` + `.zh.md`（§6.5 文件名敲定；§8.1 → CI 已交付；
  §8.3 → walkthrough 链接；状态/changelog）
- `docs/design/frontend-expansion-plan.md` + `.zh.md`（§3 F6 行 → 完成；changelog）
- 后端测试：一个小的 `test_spa_fallback.py`，断言 (a) `/api/*` 仍然路由、(b) 设了
  `static_dir` 时未知 GET 返回 `index.html`、(c) 未设时跳过挂载。

## 7. 分阶段计划

执行顺序 **A → C → B**（2026-05-30 与用户修订）：先手动 build 镜像，手动 walkthrough
一遍确认端到端可用，再把同一套 build 自动化成 CI。每个子步骤都可独立出货。

- **F6.A —— Docker 镜像（现在）。** `config.static_dir` + `main.py` catch-all fallback
  （+ `/api` 404 + 穿越防护）+ 一个小 SPA 测试 → 多阶段 `Dockerfile` + entrypoint +
  `.dockerignore` + `docker-compose.yml`（宿主用户 + bind-mount `./data` + healthcheck
  + restart）。*验收：* `mkdir -p data` 后 `docker compose up --build` 在 `/` 托管 SPA、
  在 `/api/*` 提供 API；深链刷新可用；`./data/app.db` 在宿主上创建、归你所有、跨重启存活。
- **F6.C —— Walkthrough（下一步）。** 对运行中的容器手动跑每条 §5.2 流程，写出
  `docs/walkthrough.md` + `.zh.md`，记录步骤 + 预期结果。*验收：* 全新读者无需看代码即可
  从注册走到 dashboard；每条流程都覆盖；然后把 v1-release-plan §8.3 标为完成。
- **F6.B —— CI/CD（最后）。** `.github/workflows/ci.yml`（§4）自动化 F6.A 里手动验证过的
  那套 build。*验收：* PR 跑 backend-quality + codegen-freshness + frontend-build +
  docker build（不 push）；合到 `main` push `ghcr.io/t-liu93/trading-journal:latest`。

## 8. 人工验证 recipe

```bash
# A —— 本地 build + run（先做这个）
mkdir -p data                 # bind mount 的宿主目录，属主是你（UID 1000）
cp .env.example .env          # 设一个真实的 COOKIE_SECRET
docker compose up --build
# -> http://localhost:8000          （SPA）
# -> http://localhost:8000/docs     （API 仍在）
# -> http://localhost:8000/positions 然后刷新 -> 仍是 SPA（不 404）
# -> ./data/app.db 在宿主上、属主是你
docker compose down && docker compose up   # 数据经 ./data bind mount 持久化

# C —— walkthrough 本身就是验收走查（见 §5.2）

# B —— 最后：CI 镜像上面这套；可选用 `act` 本地试跑：
#     act pull_request -j backend-quality
```

## 9. 风险与已考虑的备选

- **静态服务。** 选了纯 GET catch-all（「文件存在就返回、否则 `index.html`」），而非
  `StaticFiles(html=True)`（后者深链刷新时 404）。注册在 API router 之后，不会遮蔽
  `/api/*` 或 `/docs`。两个 guard 补齐缺口：`/api/*` → 真 404（而非外壳）、穿越校验
  （`is_relative_to(dist)`）挡住 `dist/` 之外的读取。
- **运行期 uv。** 运行期直接调 `uvicorn`、**镜像里没有 `uv`** —— 更小、确定性更高
  （`uv run` 会在启动时重新校验/同步环境）。uv 只用在构建阶段（`uv sync`）。项目通过
  `PYTHONPATH` 解析、不装进 venv（让依赖层缓存稳定）。
- **非 root + 可写数据。** 通过 compose `user:` 以宿主 UID 运行；`/data` 是宿主 bind
  mount，所以 `app.db` 归你、便于备份。*已管理的坑：* `./data` 必须在 `up` 前存在且
  属主对（见 §3.4 / §8）。
- **GHCR 包可见性。** 新 GHCR 包默认 private；首次 push（在 F6.B）后须手动设可见性 +
  把包关联到仓库。一次性手动步骤。
- **`refactoring/rebuild` 上的 CI。** 我们还没在 `main`，所以 CI 触发包含
  `refactoring/rebuild`，让 gate 合并前就跑；`latest` 仅从 `main` 发布，避免半成品
  `latest`。（细节在 §4，最后做。）

## 10. F6 之后（V1 上线）

- **归档 macro。** 按 v1-release-plan §1，F6 落地后前后端 macro 路线图归档，V1 release
  plan 成为记录。
- **部署前 checklist**（非 phase）：§8.2 Postgres parity 跑一遍；GHCR 包设好可见性；
  部署环境里 `COOKIE_SECURE=true` + 真实 `COOKIE_SECRET`。
- **V1.x 候选**（同 v1-release-plan §9）：PX 外部集成、Position `archived_at` + Account
  取消归档、Vitest/Playwright、图表库重评、broker API、FX 换算、移动端/暗色/i18n。外加
  此处推迟的：tag 驱动的 semver release、CI 里的 Postgres。

---

## Changelog

- **v0.2（2026-05-30）** —— Part A（Docker）经与用户讨论后做实；执行顺序改为
  **A → C → B**（手动 build → 手动 walkthrough → 自动化成 CI；§4 放最后）。敲定：静态
  服务 = 纯 catch-all「文件存在就返回、否则 `index.html`」+ `/api/*`-404 guard（#2）+
  路径穿越 guard（#3），不单独 mount `/assets`；运行期直接调 `uvicorn`（运行镜像不含
  `uv`），项目通过 `PYTHONPATH` 找到；非 root 用 compose `user: ${PUID:-1000}:${PGID:-1000}`
  + 宿主 bind mount `./data`（便于备份）取代具名 volume + Dockerfile `USER`；加
  `healthcheck`（`python urllib` → `/api/health`）+ `restart: unless-stopped`；镜像按
  version 打 tag（不 pin digest）；确认单容器、无反代。撤销 v0.1「提交 lockfile」项 ——
  `frontend/package-lock.json` 已提交。
- **v0.1（2026-05-30）** —— 初版 F6 收尾计划。把 F6 从「Docker 接线」拓宽为 V1 发布就绪
  这一捆（A Docker 镜像 / B CI-CD / C walkthrough），对应用户 2026-05-30 一并提出的三件
  事。敲定：plan-first；GHCR registry；标准后端 CI 范围（ruff + mypy + pytest + codegen
  gate）、可选前端 build、Postgres parity 推迟；单容器 SPA 模型；独立双语 walkthrough
  文档。推荐执行顺序 A → B → C（理由：CI + walkthrough 都依赖 Dockerfile）。
