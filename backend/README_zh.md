# Backend

[English](./README.md)

[返回根目录](../README_zh.md)

这个目录现在包含 Phase 1 的 backend scaffold。

本阶段已包含：

- FastAPI app factory 与入口
- 基于环境变量的 settings
- SQLAlchemy engine 与 session 基础接线
- Alembic scaffold 和一个空的 baseline revision
- `/api/v1/health` 健康检查接口
- 覆盖 happy flow 与配置错误路径的最小测试

本阶段不包含任何业务 schema 或 domain model。

Runbook：

1. 在仓库根目录创建环境文件：`cp .env.example .env`
2. 在仓库根目录启动本地 PostgreSQL 示例：`docker compose -f docker-compose-example.yaml up -d`
3. 从仓库根目录创建 backend 虚拟环境：`cd backend && python3 -m venv .venv`
4. 安装 backend 依赖：`cd backend && .venv/bin/pip install -e ".[dev]"`
5. 执行 migration：`cd backend && .venv/bin/alembic upgrade head`
6. 以环境变量中的 host 和 port 启动应用：`cd backend && .venv/bin/python -m app.main`
7. 运行测试：`cd backend && .venv/bin/pytest`

说明：

- Backend settings 从环境变量读取，并默认加载仓库根目录下的 `.env`。
- 当前阶段 backend 只要求 `DATABASE_URL` 这个数据库连接变量。
- 当前 Alembic baseline revision 故意保持为空，因为 schema 设计会留到下一阶段。
- 如果更希望直接通过 Uvicorn 启动，也可以使用 `cd backend && .venv/bin/uvicorn app.asgi:app --host 0.0.0.0 --port 8000`。
