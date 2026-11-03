# Trading Journal（交易日志）

> [English](../README.md) · **中文**

[![Test and Build](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/t-liu93/trading-journal?sort=semver)](https://github.com/t-liu93/trading-journal/releases/latest)
[![Container image](https://img.shields.io/badge/ghcr.io-trading--journal-2496ED?logo=docker&logoColor=white)](https://github.com/t-liu93/trading-journal/pkgs/container/trading-journal)

> 一个自托管、单用户的交易日志，支持股票、外汇 CFD，以及多腿期权策略。

Trading Journal 是一个用来**记录与分析交易**的 Web 应用 —— 覆盖现货股票、外汇 CFD，以及 **wheel（轮转）**、**iron condor（铁鹰）**、**LEAP + PMCC** 等复杂期权策略。它围绕一个通用的 *position（仓位）/ 原子 trade* 数据模型构建，因此新增品种或策略是「叠加式」的扩展，而不是推倒重来。整个应用以**单个 Docker 容器**交付，在同一个端口上同时提供 API 和前端界面。

## 功能

- **账户** —— 多个交易账户（`cash` / `margin` / `paper`），支持归档。
- **品种** —— 股票、期权、外汇对；带 typeahead 选择器，并支持内联即时创建（重复项自动去重）。
- **仓位** —— 一套模型覆盖所有策略（`spot_stock`、`spot_forex`、`wheel`、`iron_condor`、`pmcc`）；详情页含 **Overview / Meta / Plan / Trades** 四个 tab。
- **Trade（成交）** —— 单腿或多腿录入、同一订单共享一个 order group，cash flow 由服务端计算，软删除并保留历史（审计友好）。
- **Dashboard** —— 分币种的已实现盈亏卡片、开仓/平仓仓位表、按月已实现盈亏图、胜率仪表。
- **部署** —— 单容器；默认 SQLite（PostgreSQL 可移植性是设计目标）；基于 cookie 的鉴权；以你的宿主用户身份运行。

技术栈：后端 **FastAPI · SQLAlchemy 2 · Alembic**，前端 **Vue 3 · Vite · TypeScript · Naive UI**。

## 快速开始

只需要装好 Docker 和 Compose 插件。

```bash
mkdir trading-journal && cd trading-journal

# 拉取示例 compose 文件
curl -O https://raw.githubusercontent.com/t-liu93/trading-journal/main/example/docker-compose.yml

# 建好 data 目录（属主是你，用来放 SQLite 数据库）
mkdir -p data

# 拉取镜像并启动（会先跑一个一次性的 migrate 服务，迁移成功后才启动 app）。
# 不需要配置任何密钥 —— 应用会自己生成并持久化。
# 快速开始采用本地 HTTP；HTTPS 部署保持 secure cookie。
COOKIE_SECURE=false docker compose up -d
```

然后打开 **http://localhost:8000**，注册账号，开始记录交易。

> Cookie **默认 secure（仅 HTTPS）**。如果你通过纯 HTTP 访问、发现登录状态保持不住，在 compose 文件旁边的 `.env` 里设 `COOKIE_SECURE=false`，或者用反向代理终结 TLS（见「部署」）。

## 部署

发布的镜像会同时提供前端 SPA 和 API。compose 用一个专门的 **`migrate`** 服务跑迁移，**只有迁移成功后才启动 `app`**（fail-closed：迁移出错绝不会进入一个在跑的 app）。数据持久化到宿主机上的 bind mount。

**镜像**（GitHub Container Registry，多架构 `linux/amd64` + `linux/arm64`）：

```
ghcr.io/t-liu93/trading-journal:latest   # 也可固定版本，如 :1.0.0
```

**配置**（全部可选，写在 compose 文件旁边的 `.env`）：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `COOKIE_SECURE` | `true` | Cookie 默认仅 HTTPS。只有纯 HTTP 本地访问时才设 `false`。 |
| `PUID` / `PGID` | `1000` | 容器运行所用的宿主用户/组，确保 `./data` 归你所有。 |
| `DEBUG` | `false` | 后端详细日志。 |

**无需管理 `COOKIE_SECRET`**：token 签名密钥在首次启动时生成并存入 `app_config`，登录 session 使用数据库不透明 token。后续纯 HTTP 启动可在部署目录的 `.env` 保留 `COOKIE_SECURE=false`；HTTPS 部署保持 secure 默认值。

**数据与备份。** SQLite 数据库在宿主机 `./data/app.db`。使用一致的 SQLite 备份，或停止写入后再复制；在隔离目录验证恢复。容器以非 root 宿主用户运行，并设 `restart: unless-stopped`。

**HTTPS / 远程访问。** 示例只绑定 loopback（`127.0.0.1:8000`），适合配合 SSH 隧道使用。要对外公开，请在前面加一个反向代理来终结 TLS —— 并保持 `COOKIE_SECURE=true`（默认值）。

完整的构建与验收指南见 [`docs/walkthrough.zh.md`](walkthrough.zh.md)（[English](walkthrough.md)）。

## 开发

从[开发指南](development.zh.md)（[English](development.md)）开始，了解架构、锁定依赖、一次性数据库热重载和检查。当前 CI／Docker 使用 Python 3.12、Node 22。

用[隔离 Compose 走查](walkthrough.zh.md)从 checkout 构建整套应用，不使用已有交易记录或替换本地 Compose。共享模板在 `example/`，根目录 Compose 是被忽略的本地工作副本。已提交 API 类型使前端／镜像可在后端未启动时构建。

当前范围与验收记录在[路线图](plan/roadmap.zh.md)和任务卡。历史 P/F 设计计划仍作参考，不再作为活动清单。

## 文档

- [文档地图](index.zh.md)（[English](index.md)）—— 当前指导与历史参考。
- [当前路线图](plan/roadmap.zh.md)（[English](plan/roadmap.md)）—— 优先级、任务契约、进度与验收。
- [开发指南](development.zh.md)（[English](development.md)）—— 命令、领域规则、验证与评审。
- [走查指南](walkthrough.zh.md)（[English](walkthrough.md)）—— 一次性构建与代表性功能检查。
- [设计参考](design/README.zh.md)（[English](design/README.md)）和[发布记录](release-notes/)—— 历史计划与版本记录。

## License

本项目基于 [MIT License](../LICENSE) 授权。
