# Trading Journal — Manual Build & Feature Walkthrough

**Language:** English | [中文](./walkthrough.zh.md)

> A hands-on guide to **build the Docker image, run the single container, reach
> it from your laptop over an SSH tunnel, and verify every V1 feature**. This is
> the F6.C acceptance run-through (see
> [v1-implementation-plan-f6.md](./design/v1-implementation-plan-f6.md)).
>
> Setup assumed: you develop on a **remote server over SSH**; the container runs
> on that server; you test from your **laptop's browser via `localhost`**.

---

## 0. Prerequisites

On the **dev server**:
- Docker + the Compose plugin (`docker compose version`).
- This repo checked out; you're on `refactoring/rebuild`.

On your **laptop**:
- An SSH client that can reach the dev server.
- A browser.

---

## 1. Build & run the container (on the dev server)

```bash
# The example compose lives in ./example. Run the container from there so its
# relative ./data bind mount and .env sit next to the compose file.
cd /path/to/trading-journal/example

# 1. Create the data dir FIRST, owned by you. This is the #1 gotcha:
#    the container runs as your UID (1000) and writes ./data/app.db here.
#    If Docker auto-creates ./data it'll be root-owned and the migration fails.
mkdir -p data

# 2. Make a real .env (it's gitignored). The template lives at the repo root.
cp ../.env.example .env
#    Generate a real secret and put it in .env as COOKIE_SECRET=...
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
#    Edit .env: set COOKIE_SECRET=<that value>. Leave COOKIE_SECURE=false
#    (we're on plain HTTP behind an SSH tunnel, not HTTPS yet).

# 3. The example compose pulls ghcr.io/t-liu93/trading-journal:latest. To run
#    YOUR local build for acceptance, build that tag first (context = repo root):
docker build -t ghcr.io/t-liu93/trading-journal:latest ..
#    Then start the container (detached). Skip the build above to just pull the
#    already-published image instead.
docker compose up -d

# 4. Confirm it came up healthy (give it ~10-15s for the healthcheck).
docker compose ps
#    STATUS should read "Up ... (healthy)".
docker compose logs --tail=20 app
#    You should see "alembic upgrade head" run, then uvicorn listening on :8000.
```

If `PUID`/`PGID` on your server aren't 1000, set them in `.env` (`PUID=$(id -u)`,
`PGID=$(id -g)`) before `up`.

**Security note (recommended for SSH dev):** by default Compose publishes
`8000:8000` on the server's `0.0.0.0` (all interfaces). To keep it private and
reachable *only* through your SSH tunnel, change the port line in
`example/docker-compose.yml` to bind loopback:

```yaml
    ports:
      - "127.0.0.1:8000:8000"
```

---

## 2. Reach it from your laptop via an SSH tunnel

The container listens on the **server's** `localhost:8000`. Forward your laptop's
`localhost:8000` to it. In a **laptop terminal**:

```bash
ssh -N -L 8000:localhost:8000 <user>@<dev-server>
# -N: no remote command, just forward. Leave this running.
```

Or make it permanent in `~/.ssh/config` on your laptop:

```
Host devbox
    HostName <dev-server>
    User <user>
    LocalForward 8000 localhost:8000
```

…then `ssh devbox`. (VS Code Remote-SSH forwards ports automatically — check the
**PORTS** panel — so you may not need this at all.)

Now open **http://localhost:8000** on your laptop.

**Why `localhost` and not the server's IP:** cookies are keyed on the exact
hostname, and `COOKIE_SECURE=false` cookies behave consistently on `localhost`
(same hostname the dev setup uses on :5173). Browsers also treat `localhost` as a
secure context. Using the raw server IP works but invites "I logged in but my
session vanished" cookie surprises — stick to `localhost` over the tunnel.

---

## 3. Infrastructure smoke check (do this before features)

With the tunnel up, from your laptop browser:

| Check | URL / action | Expected |
|---|---|---|
| SPA loads | `http://localhost:8000` | The app UI (login screen), not JSON |
| API alive | `http://localhost:8000/api/health` | `{"status":"ok"}` |
| API docs | `http://localhost:8000/docs` | Swagger UI |
| **Deep-link refresh** | go to `http://localhost:8000/positions`, then hit **reload** | Still the SPA — **not** a 404. (Proves the catch-all fallback.) |
| Unknown API 404 | `http://localhost:8000/api/nope` | JSON `{"detail":"Not Found"}`, not the SPA shell |

Back on the **server**, confirm data ownership + persistence:

```bash
ls -l data/                       # app.db present, owned by YOU (not root)
docker compose restart app        # bounce it
# reload the browser -> your data is still there (DB survived the restart)
```

If all of the above pass, the image and single-container wiring are correct.
Move on to features.

---

## 4. Feature walkthrough (the acceptance script)

Do these in order from your laptop browser. Each step lists the action and the
**expected result**. (Use throwaway data — this is your real DB.)

1. **Auth.** Register a new account → you're logged in. Log out → back to login.
   Log back in.
   *Expected:* session persists across reloads (cookie works over the tunnel).

2. **Accounts (F1).** Create an account; edit it; archive it.
   *Expected:* list updates after each; archived ones drop from the default view.

3. **Instruments (F2 + F3).** Open `/instruments`. Create a **stock**, an
   **option**, and a **forex** instrument via the form. Then in a Position-create
   flow, use the **InstrumentPicker inline create** (`allowCreate`): type a brand
   new symbol and create it without leaving the form; for an option, confirm the
   **two-step** flow (pick underlying, then strike/expiry/type/multiplier).
   *Expected:* duplicates silently resolve to the existing instrument (get-or-create).

4. **Strategy config.** Go to `/settings/strategies`; set an exposure cap for a
   strategy. *Expected:* value saves and reloads.

5. **Position (F3).** Create a position (using the picker). Open its detail page
   and visit all four tabs:
   - **Overview** — edit manual fields (`capital_used`, `max_risk_at_open`, …);
     derived values (`days_open`, `pnl_total`, ROI, result) display read-only.
   - **Meta** — for a `wheel` position fill funding/loan/interest; for a `pmcc`
     position pick the LEAP; other types show an empty state.
   - **Plan** — append a TradePlan revision; the history table grows.
   - **Trades** — currently a read pane (becomes live in the next step).

6. **Trade entry (F4).** On the Trades tab, add trades:
   - A **single** trade (e.g. a stock buy). *Expected:* it appears; per-row
     `cash_flow` shown.
   - A **Custom multi-leg** submission for each event in the
     [§4.5.2 cheat-sheet](#appendix--multi-leg-event--rows) — iron-condor open
     (4 legs), assignment (2), exercise (2), expiration (1) — all legs of one
     submission sharing a single `order_group_id`.
   *Expected:* legs render grouped by `order_group_id`, with the right
   **pattern badge** (IC-open / Assignment / Exercise / Expiration).

7. **Dashboard (F5).** Open `/dashboard`.
   *Expected:* per-currency PnL cards, the open-positions table, the
   closed-positions table, the **monthly realized-PnL chart**, and the win-rate
   gauge — all reflecting the data you just entered.

8. **Delete paths.** Try to delete a position that has trades/plans attached
   → blocked with a clear 409 message. Soft-delete a trade, then view with
   `?include_archived=true`. *Expected:* exactly as described.

When all eight pass, F6.A + the manual acceptance are done.

---

## 5. Teardown & troubleshooting

```bash
docker compose down        # stops + removes the container; ./data is KEPT
docker compose up -d       # bring it back; your data is still there
```

| Symptom | Likely cause / fix |
|---|---|
| `up` fails: can't write `/data/app.db` / permission denied | `./data` is root-owned. `sudo chown -R $(id -u):$(id -g) data` (or remove it and `mkdir -p data` as yourself before `up`). |
| `COOKIE_SECRET` error on `up` | Not set in `.env`. Generate one (step 1.2) and add it. |
| `localhost:8000` refused on laptop | SSH tunnel not running, or the container isn't up/healthy. Re-check `ssh -N -L …` and `docker compose ps`. |
| Logged in but session keeps dropping | You're hitting the server IP, not `localhost` over the tunnel. Use `localhost`. |
| Port 8000 already in use on the server | Something else is bound. Change the host side of the ports mapping (e.g. `8001:8000`) and forward `8001` instead. |
| Stale frontend after a code change | Rebuild: `docker build -t ghcr.io/t-liu93/trading-journal:latest .. && docker compose up -d` (the SPA is baked into the image at build time). |

Logs: `docker compose logs -f app`.

---

## Appendix — multi-leg event → rows

The exact leg shapes for each synthetic event are defined in
[data-model.md §4.5.2](./design/data-model.md#452-notion-event--atomic-trade-mapping)
(Notion-event ↔ atomic-trade mapping). Quick reference for step 6:

| Event | Rows in one `order_group_id` |
|---|---|
| Iron-condor open | 4 option legs (sell + buy, both wings) |
| Assignment | 2 (option closed at 0 + the stock fill at strike) |
| Exercise | 2 (option closed at 0 + the stock fill at strike) |
| Expiration | 1 (option closed at price 0) |

Enter all rows of an event as a single multi-leg submission so they share one
`order_group_id` and the Trades tab can detect the pattern.
