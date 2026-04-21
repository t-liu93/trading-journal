# Trading Journal

[中文说明](./README_zh.md)

This repository is a new trading journal project.

Current status: Phase 0.

The current goal is to establish a clean repo shape for small, reviewable iterations. Backend and frontend will be built in later phases instead of generating the full system in one pass.

Planned direction:

- Backend: FastAPI
- Database: PostgreSQL
- Frontend v1: Vue 3 + TypeScript + Vite, SPA-first
- Deployment: containerized, with Docker Compose at minimum

Current infrastructure placeholder:

- [docker-compose-example.yaml](./docker-compose-example.yaml) provides a PostgreSQL-only example for local and development use.
- The current example maps Postgres to the host with `0.0.0.0:${POSTGRES_PORT}:5432` for development convenience.
- For production deployment, Postgres should not be exposed on a host port by default and should stay reachable only on the internal Compose network.

Repository areas:

- [backend](./backend/README.md)
- [frontend](./frontend/README.md)
- [docs](./docs/README.md)
