# Trading Journal（交易日志）

[![Test and Build](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/t-liu93/trading-journal?sort=semver)](https://github.com/t-liu93/trading-journal/releases/latest)
[![Container image](https://img.shields.io/badge/ghcr.io-trading--journal-2496ED?logo=docker&logoColor=white)](https://github.com/t-liu93/trading-journal/pkgs/container/trading-journal)

[English](../README.md) | **中文**

> 一个自托管、单用户的交易日志，支持股票、外汇 CFD，以及多腿期权策略。

Trading Journal 是一个用来**记录与分析交易**的 Web 应用 —— 覆盖现货股票、外汇 CFD，以及 **wheel（轮转）**、**iron condor（铁鹰）**、**LEAP + PMCC** 等复杂期权策略。它围绕一个通用的 *position（仓位）/ 原子 trade* 数据模型构建，因此新增品种或策略是「叠加式」的扩展，而不是推倒重来。整个应用以**单个 Docker 容器**交付，在同一个端口上同时提供 API 和前端界面。

## 功能

- **账户** —— 多个交易账户（`cash` / `margin` / `paper`），支持归档。
- **品种** —— 股票、期权、外汇对；带 typeahead 选择器，并支持内联即时创建（重复项自动去重）。
- **仓位** —— 一套模型覆盖所有策略（`spot_stock`、`spot_forex`、`wheel`、`iron_condor`、`pmcc`）；详情页含 **Overview / Meta / Plan / Trades** 四个 tab。
- **Trade（成交）** —— 单腿或多腿录入、同一订单共享一个 order group，cash flow 由服务端计算，软删除可恢复（审计友好）。
- **Dashboard** —— 分币种的已实现盈亏卡片、开仓/平仓仓位表、按月已实现盈亏图、胜率仪表。
- **部署** —— 单容器；默认 SQLite（schema 兼容 Postgres）；基于 cookie 的鉴权；以你的宿主用户身份运行。

技术栈：后端 **FastAPI · SQLAlchemy 2 · Alembic**，前端 **Vue 3 · Vite · TypeScript · Naive UI**。

## 快速开始

只需要装好 Docker 和 Compose 插件。

```bash
mkdir trading-journal && cd trading-journal

# 拉取示例 compose 文件
curl -O https://raw.githubusercontent.com/t-liu93/trading-journal/main/example/docker-compose.yml

# 建好 data 目录（属主是你），并写一个带真实 session secret 的 .env
mkdir -p data
echo "COOKIE_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > .env

# 拉取镜像并启动
docker compose up -d
```

然后打开 **http://localhost:8000**，注册账号，开始记录交易。

## 部署

发布的镜像会同时提供前端 SPA 和 API，在启动时自动跑数据库迁移，并把数据持久化到宿主机上的 bind mount。

**镜像**（GitHub Container Registry，多架构 `linux/amd64` + `linux/arm64`）：

```
ghcr.io/t-liu93/trading-journal:latest   # 也可固定版本，如 :1.0.0
```

**配置**（写在 compose 文件旁边的 `.env`）：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `COOKIE_SECRET` | _（必填）_ | 用于签名 session cookie 的密钥。生成一次后保持不变。 |
| `COOKIE_SECURE` | `false` | 走 HTTPS 时设为 `true`。 |
| `PUID` / `PGID` | `1000` | 容器运行所用的宿主用户/组，确保 `./data` 归你所有。 |
| `DEBUG` | `false` | 后端详细日志。 |

**数据与备份。** SQLite 数据库在宿主机的 `./data/app.db` —— 备份就是复制这个文件。容器以非 root 的宿主用户运行，并设了 `restart: unless-stopped`。

**HTTPS / 远程访问。** 示例只绑定 loopback（`127.0.0.1:8000`），适合配合 SSH 隧道使用。要对外公开，请在前面加一个反向代理来终结 TLS（并把 `COOKIE_SECURE=true`）。

完整的构建与验收指南见 [`docs/walkthrough.zh.md`](walkthrough.zh.md)（[English](walkthrough.md)）。

## 文档

- [Walkthrough](walkthrough.zh.md) —— 构建镜像、运行容器、逐一验证每个功能（[English](walkthrough.md)）。
- [Release notes](release-notes/) —— 各版本更新说明，归档在本仓库内。
- [`docs/design/`](design/) —— 数据模型与设计方案。
