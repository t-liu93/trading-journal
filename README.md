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

# Create a data dir (owned by you) and a .env with a real session secret
mkdir -p data
echo "COOKIE_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > .env

# Pull and run
docker compose up -d
```

Then open **http://localhost:8000**, register an account, and start logging trades.

## Deployment

The published image serves the SPA and the API together, runs database migrations on startup, and persists data to a host-owned bind mount.

**Images** (GitHub Container Registry, multi-arch `linux/amd64` + `linux/arm64`):

```
ghcr.io/t-liu93/trading-journal:latest   # or pin a version, e.g. :1.0.0
```

**Configuration** (via `.env` next to the compose file):

| Variable | Default | Purpose |
|---|---|---|
| `COOKIE_SECRET` | _(required)_ | Secret used to sign session cookies. Generate one and keep it stable. |
| `COOKIE_SECURE` | `false` | Set to `true` when serving over HTTPS. |
| `PUID` / `PGID` | `1000` | Host user/group the container runs as, so `./data` stays owned by you. |
| `DEBUG` | `false` | Verbose backend logging. |

**Data & backups.** The SQLite database lives at `./data/app.db` on the host — back it up by copying that file. The container runs as a non-root host user and restarts unless stopped.

**HTTPS / remote access.** The example binds to loopback (`127.0.0.1:8000`), which pairs well with an SSH tunnel. For public access, put a reverse proxy in front to terminate TLS (and set `COOKIE_SECURE=true`).

See the full build-and-verify guide in [`docs/walkthrough.md`](docs/walkthrough.md) ([中文](docs/walkthrough.zh.md)).

## Documentation

- [Walkthrough](docs/walkthrough.md) — build the image, run the container, and verify every feature ([中文](docs/walkthrough.zh.md)).
- [Release notes](docs/release-notes/) — per-version changelog, archived in this repo.
- [`docs/design/`](docs/design/) — data model and design plans.

## License

This project is licensed under the [MIT License](LICENSE).
