# Trading Journal

[![Test and Build](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/t-liu93/trading-journal?sort=semver)](https://github.com/t-liu93/trading-journal/releases/latest)
[![Container image](https://img.shields.io/badge/ghcr.io-trading--journal-2496ED?logo=docker&logoColor=white)](https://github.com/t-liu93/trading-journal/pkgs/container/trading-journal)

**English** | [中文](docs/README_zh.md)

> A self-hosted, single-user trading journal for stocks, forex CFDs, and multi-leg options strategies.

Trading Journal is a web app for logging and analyzing your trades — spot stocks, forex CFDs, and complex options strategies such as the **wheel**, **iron condors**, and **LEAP + PMCC**. It's built around a generic *position / atomic-trade* data model, so supporting new instruments and strategies is additive rather than a rewrite. The whole thing ships as a **single Docker container** that serves both the API and the web UI on one port.

## Features

- **Accounts** — multiple trading accounts (`cash` / `margin` / `paper`) with archiving.
- **Instruments** — stocks, options, and forex pairs, with a typeahead picker and inline create-on-the-fly (duplicates dedupe automatically).
- **Positions** — one model for every strategy (`spot_stock`, `spot_forex`, `wheel`, `iron_condor`, `pmcc`); a detail page with **Overview / Meta / Plan / Trades** tabs.
- **Trades** — single or multi-leg entry sharing one order group, server-computed cash flow, and audit-friendly recoverable soft-delete.
- **Dashboard** — per-currency realized P&L cards, open/closed position tables, a monthly realized-P&L chart, and a win-rate gauge.
- **Deployment** — one container; SQLite by default (Postgres-ready schema); cookie-based auth; runs as your host user.

Built with **FastAPI · SQLAlchemy 2 · Alembic** (backend) and **Vue 3 · Vite · TypeScript · Naive UI** (frontend).

## Quick Start

You only need Docker with the Compose plugin.

```bash
mkdir trading-journal && cd trading-journal

# Grab the example compose file
curl -O https://raw.githubusercontent.com/t-liu93/trading-journal/main/example/docker-compose.yml

# Create a data dir owned by you (holds the SQLite DB)
mkdir -p data

# Pull and run (a one-shot `migrate` service runs first; the app starts only if
# it succeeds). No secret to set up — the app generates and stores one itself.
docker compose up -d
```

Then open **http://localhost:8000**, register an account, and start logging trades.

> Cookies are **secure-by-default** (HTTPS-only). If you're reaching the app over plain HTTP and login doesn't stick, set `COOKIE_SECURE=false` in a `.env` next to the compose file, or terminate TLS at a reverse proxy (see Deployment).

## Deployment

The published image serves the SPA and the API together. The compose file runs migrations as a dedicated **`migrate`** service and starts the **`app`** only once it succeeds (fail-closed: a bad migration never reaches a running app). Data persists to a host-owned bind mount.

**Images** (GitHub Container Registry, multi-arch `linux/amd64` + `linux/arm64`):

```
ghcr.io/t-liu93/trading-journal:latest   # or pin a version, e.g. :1.0.0
```

**Configuration** (all optional, via a `.env` next to the compose file):

| Variable | Default | Purpose |
|---|---|---|
| `COOKIE_SECURE` | `true` | Cookies are HTTPS-only by default. Set `false` only for plain-HTTP local access. |
| `PUID` / `PGID` | `1000` | Host user/group the container runs as, so `./data` stays owned by you. |
| `DEBUG` | `false` | Verbose backend logging. |

There is **no `COOKIE_SECRET`** to manage: the session-signing secret is generated on first boot and persisted in the database (`app_config` table), so it survives restarts without operator involvement.

**Data & backups.** The SQLite database lives at `./data/app.db` on the host — back it up by copying that file. The container runs as a non-root host user and restarts unless stopped.

**HTTPS / remote access.** The example binds to loopback (`127.0.0.1:8000`), which pairs well with an SSH tunnel. For public access, put a reverse proxy in front to terminate TLS — and leave `COOKIE_SECURE=true` (the default).

See the full build-and-verify guide in [`docs/walkthrough.md`](docs/walkthrough.md) ([中文](docs/walkthrough.zh.md)).

## Development

The backend and frontend are both complete and live in this repo, so there are two ways to run it locally — pick by what you're doing.

**Run the full app via docker-compose** (mirrors production, including the `migrate` → `app` fail-closed step). The dev overlay (`docker-compose.dev.yml`) just adds a local `build:` and relaxes `COOKIE_SECURE`, so you build the image from your working tree instead of pulling it. Copy both templates to the repo root (they're git-ignored there) and bring them up together:

```bash
cp example/docker-compose.yml example/docker-compose.dev.yml .
mkdir -p data

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Then open **http://localhost:8000**. Since `frontend/src/api/schema.d.ts` is committed, the Vite build is self-contained — the image builds with **no backend running**. (For a quick throwaway check without compose: `docker build -t trading-journal:dev . && docker run --rm -p 8000:8000 -e COOKIE_SECURE=false trading-journal:dev`.)

**Run the two processes split** when you're actively editing and want hot reload:

```bash
# Backend → http://127.0.0.1:8000  (auto-creates ./dev.db)
cd backend && uv run alembic upgrade head && uv run uvicorn trading_journal.main:app --reload

# Frontend → http://localhost:5173  (Vite proxies /api → :8000)
cd frontend && npm install && npm run dev
```

No `COOKIE_SECRET` to set in any of these — the app generates and persists one on first boot.

## Documentation

- [Walkthrough](docs/walkthrough.md) — build the image, run the container, and verify every feature ([中文](docs/walkthrough.zh.md)).
- [Release notes](docs/release-notes/) — per-version changelog, archived in this repo.
- [`docs/design/`](docs/design/) — data model and design plans.

## License

This project is licensed under the [MIT License](LICENSE).
