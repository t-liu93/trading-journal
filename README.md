# Trading Journal

> **English** · [中文](docs/README_zh.md)

[![Test and Build](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml/badge.svg)](https://github.com/t-liu93/trading-journal/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/t-liu93/trading-journal?sort=semver)](https://github.com/t-liu93/trading-journal/releases/latest)
[![Container image](https://img.shields.io/badge/ghcr.io-trading--journal-2496ED?logo=docker&logoColor=white)](https://github.com/t-liu93/trading-journal/pkgs/container/trading-journal)

> A self-hosted, single-user trading journal for stocks, forex CFDs, and multi-leg options strategies.

Trading Journal is a web app for logging and analyzing your trades — spot stocks, forex CFDs, and complex options strategies such as the **wheel**, **iron condors**, and **LEAP + PMCC**. It's built around a generic *position / atomic-trade* data model, so supporting new instruments and strategies is additive rather than a rewrite. The whole thing ships as a **single Docker container** that serves both the API and the web UI on one port.

## Features

- **Accounts** — multiple trading accounts (`cash` / `margin` / `paper`) with archiving.
- **Instruments** — stocks, options, and forex pairs; expired-option visibility, paginated candidates, primary-stock filtering and contextual inline creation with deduplication.
- **Positions** — one model for every strategy (`spot_stock`, `spot_forex`, `wheel`, `iron_condor`, `pmcc`); a detail page with **Overview / Meta / Plan / Trades** tabs.
- **Trades** — single or multi-leg entry sharing one order group, server-computed cash flow, and audit-friendly soft-delete with retained history.
- **Agent entry** — Codex/Hermes can use separate MCP read-only or entry credentials at `/api/mcp`; entry batches are previewed before confirmation and committed atomically.
- **Dashboard** — per-currency realized P&L cards, open/closed position tables, a monthly realized-P&L chart, and a win-rate gauge.
- **Deployment** — one container; SQLite by default (PostgreSQL portability is a design goal); cookie-based auth; runs as your host user.

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
# This quick start uses local HTTP; keep secure cookies for HTTPS deployments.
COOKIE_SECURE=false docker compose up -d
```

Then open **http://localhost:8000**, register an account, and start logging trades.

> Cookies are **secure-by-default** (HTTPS-only). If you're reaching the app over plain HTTP and login doesn't stick, set `COOKIE_SECURE=false` in a `.env` next to the compose file, or terminate TLS at a reverse proxy (see Deployment).

## Deployment

The published image serves the SPA and the API together. The compose file runs migrations as a dedicated **`migrate`** service and starts the **`app`** only once it succeeds (fail-closed: a bad migration never reaches a running app). Data persists to a host-owned bind mount.

**Images** (GitHub Container Registry, multi-arch `linux/amd64` + `linux/arm64`):

```
ghcr.io/t-liu93/trading-journal:latest   # or pin a version, e.g. :1.2.0
```

**Configuration** (all optional, via a `.env` next to the compose file):

| Variable | Default | Purpose |
|---|---|---|
| `COOKIE_SECURE` | `true` | Cookies are HTTPS-only by default. Set `false` only for plain-HTTP local access. |
| `PUID` / `PGID` | `1000` | Host user/group the container runs as, so `./data` stays owned by you. |
| `DEBUG` | `false` | Verbose backend logging. |
| `JOURNAL_TIMEZONE` | `UTC` | IANA timezone used for MCP entry times without an offset or per-leg timezone. |
| `MCP_ALLOWED_HOSTS` | Localhost/loopback defaults | JSON array of allowed HTTP Host values for the MCP endpoint. Extend with the exact external proxy Host when using HTTPS. |
| `MCP_ALLOWED_ORIGINS` | Localhost/loopback defaults | JSON array of allowed browser Origin values. Normal MCP requests without Origin are accepted. |

There is **no `COOKIE_SECRET`** to manage: the token-signing secret is generated on first boot and persisted in `app_config`. Login sessions use opaque database tokens. For repeat plain-HTTP starts, keep `COOKIE_SECURE=false` in the deployment directory’s `.env`; HTTPS deployments should keep the secure default.

**Data & backups.** The SQLite database lives at `./data/app.db` on the host. Use a consistent SQLite backup, or stop writes before copying the database; verify restoration in an isolated directory. The container runs as a non-root host user and restarts unless stopped.

**HTTPS / remote access.** The example binds to loopback (`127.0.0.1:8000`), which pairs well with an SSH tunnel. For public access, put a reverse proxy in front to terminate TLS — and leave `COOKIE_SECURE=true` (the default).

**MCP clients (v1.2.0+).** Use the `1.2.0` or newer image; `v1.1.0` does not include MCP. Follow the [MCP walkthrough](docs/walkthrough.md#mcp-client-setup-and-walkthrough) for isolated source verification and temporary client configuration. The endpoint is `https://<journal-host>/api/mcp` behind HTTPS (or `http://localhost:18000/api/mcp` in the isolated local walkthrough). Create separate `read` and `entry` credentials in Settings → MCP; the secret is shown once. `read` can query context and journal records; `entry` can also prepare and commit a batch. A preview expires after 24 hours; retries reuse the original `request_id` during preparation and the original `draft_id` during commit. MCP uses atomic Position-plus-first-Trades creation; the website still creates those through two requests with recovery.

See the full build-and-verify guide in [`docs/walkthrough.md`](docs/walkthrough.md) ([中文](docs/walkthrough.zh.md)).

## Development

Start with the [development guide](docs/development.md) ([中文](docs/development.zh.md)) for architecture, locked dependencies, hot reload with a disposable database, and checks. CI/Docker currently use Python 3.12 and Node 22.

Use the [isolated Compose walkthrough](docs/walkthrough.md) to build from your checkout and verify the full app without using existing trading records or replacing local Compose files. The shared templates live in `example/`; root-level Compose files are ignored local working copies. The committed API types let the frontend/image build without a running backend.

Current scope and acceptance are tracked in the [roadmap](docs/plan/roadmap.md) and task cards. Historical P/F design plans remain references, rather than active checklists.

## Documentation

- [Documentation map](docs/index.md) ([中文](docs/index.zh.md)) — current guidance and historical references.
- [Current roadmap](docs/plan/roadmap.md) ([中文](docs/plan/roadmap.zh.md)) — priorities, task contracts, progress and acceptance.
- [M-MCP-01 milestone](docs/plan/milestone-mcp-entry.md) ([中文](docs/plan/milestone-mcp-entry.zh.md)) — MCP entry contracts, implementation/check/review/owner status; consult the roadmap for current status.
- [M-OPT-01 milestone](docs/plan/milestone-option-entry.md) ([中文](docs/plan/milestone-option-entry.zh.md)) — completed option-entry work, verification and five-step owner acceptance.
- [v1.2.0 release notes](docs/release-notes/v1.2.0.md) ([中文](docs/release-notes/v1.2.0.zh.md)) — changes, upgrade notes and validation scope.
- [Development guide](docs/development.md) ([中文](docs/development.zh.md)) — commands, domain rules, verification and review.
- [Walkthrough](docs/walkthrough.md) ([中文](docs/walkthrough.zh.md)) — disposable build and representative feature checks.
- [Design references](docs/design/README.md) ([中文](docs/design/README.zh.md)) and [release notes](docs/release-notes/) — historical plans and version-specific records.

## License

This project is licensed under the [MIT License](LICENSE).
