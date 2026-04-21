# Trading Journal

[English](./README.md)

这个仓库是一个新的 trading journal 项目。

当前状态：Phase 0。

本阶段目标是先建立清晰、易于小步迭代和评审的仓库骨架，而不是一次性生成完整系统。后续会在分阶段推进中分别搭建 backend 和 frontend。

当前已确认方向：

- Backend: FastAPI
- Database: PostgreSQL
- Frontend v1: Vue 3 + TypeScript + Vite，SPA-first
- Deployment: containerized，至少使用 Docker Compose

当前基础设施占位：

- [docker-compose-example.yaml](./docker-compose-example.yaml) 提供了一个仅包含 PostgreSQL 的本地/开发示例。
- 当前示例为了开发便利，会通过 `0.0.0.0:${POSTGRES_PORT}:5432` 映射到宿主机端口。
- 生产部署时，数据库默认不应暴露宿主机端口，而应只在 Compose 内部网络中被其他服务访问。

仓库分区：

- [backend](./backend/README_zh.md)
- [frontend](./frontend/README_zh.md)
- [docs](./docs/README_zh.md)
