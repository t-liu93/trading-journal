# 后端

> [English](README.md) · **中文**

FastAPI、异步 SQLAlchemy、Alembic 和 SQLite，包名 `trading_journal`。当前 CI 使用 Python 3.12 与 uv。

隔离的本地数据库、启动命令、架构、领域契约和检查看[开发指南](../docs/development.zh.md)。命令在本目录运行，不为验证改动而迁移或重置已有数据库。

- 安装：`uv sync --frozen`。
- 检查：`uv run ruff check .`、`uv run mypy --strict src`、`uv run pytest`。
- API 类型：开发后端运行于 8000，再到 `frontend/` 跑 `npm run codegen`。OpenAPI 为 `/openapi.json`，业务端点使用 `/api`。
- 测试使用实际 Alembic 迁移构建的隔离数据库。
- HTTP 开发需 `COOKIE_SECURE=false`；session 使用数据库 token，签名密钥自动持久化。

实现范围和验收放在[当前路线图](../docs/plan/roadmap.zh.md)与任务卡，不再用历史 P/F 计划调度。
