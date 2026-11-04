# Disposable build and feature walkthrough

> **English** · [中文](walkthrough.zh.md)

This is the current manual verification guide. Use synthetic data in a new temporary environment; it does not start or modify the normal deployment. Passing these checks records only the paths actually exercised, not owner acceptance. See the [roadmap](plan/roadmap.md) and relevant task card for scope.

Future MCP verification is specified in [M-MCP-01 section 4](plan/milestone-mcp-entry.md#4-verification-walkthrough-and-cleanup). MCP is not implemented yet. Its T7 phase B will add executable client/credential/timezone steps after the application cards; this documentation delivery does not change the current setup commands.

## 1. Create an isolated environment

Prerequisites: Docker with Compose, a checkout of the candidate to verify, a browser, and SSH only when testing a remote machine. Start a dedicated terminal at the repository root. Port 18000 must be free; if occupied, choose a different unused port in the copied mapping and tunnel. Do not stop the existing listener.

The commands copy the deployment template into a newly created directory, build from the candidate source, and give this run its own project/image name. They use neither the repo's `data/` nor its root Compose/`.env` files. The template already binds loopback. No manual `COOKIE_SECRET` is required; this local HTTP run explicitly sets `COOKIE_SECURE=false`.

```bash
export TJ_SOURCE_DIR="$(pwd)"
export TJ_CHECK_DIR="$(mktemp -d /tmp/tj-check-XXXXXX)"
export TJ_CHECK_ID="$(basename "$TJ_CHECK_DIR" | tr '[:upper:]' '[:lower:]')"
export PUID="$(id -u)"
export PGID="$(id -g)"
export COOKIE_SECURE=false
export DEBUG=false
mkdir "$TJ_CHECK_DIR/data"

sed 's/127.0.0.1:8000:8000/127.0.0.1:18000:8000/' \
  example/docker-compose.yml > "$TJ_CHECK_DIR/compose.yml"

cat > "$TJ_CHECK_DIR/local.yml" <<'YAML'
services:
  migrate:
    build:
      context: $TJ_SOURCE_DIR
      dockerfile: Dockerfile
    image: trading-journal:$TJ_CHECK_ID
  app:
    build:
      context: $TJ_SOURCE_DIR
      dockerfile: Dockerfile
    image: trading-journal:$TJ_CHECK_ID
YAML

tj_check() {
  docker compose --env-file /dev/null -p "$TJ_CHECK_ID" \
    -f "$TJ_CHECK_DIR/compose.yml" -f "$TJ_CHECK_DIR/local.yml" "$@"
}

tj_check config
```

Before `up`, inspect `config`: both database mounts must resolve inside `$TJ_CHECK_DIR/data`, the build context must be your checkout, and the only host binding must be `127.0.0.1:18000`. If they do not, stop and correct the temporary configuration.

```bash
tj_check up -d --build
tj_check ps -a
tj_check logs --tail=30 migrate app
```

Expected: `migrate` exits successfully, then `app` becomes healthy. Migration logs belong to `migrate`; the app's `RUN_MIGRATIONS=false` skips a second migration. A failed migration must prevent app startup. The database/secret is created in the temporary data directory, owned by the selected host UID/GID. Never fix a permission issue by deleting an existing database.

## 2. Browser access and infrastructure

Locally, open `http://localhost:18000`. For a remote dev machine, forward from the laptop:

```bash
ssh -N -L 18000:127.0.0.1:18000 <user>@<dev-server>
```

Use a separate browser profile/container for synthetic accounts. Cookies are keyed by hostname, not port, so another app/test on `localhost` can share the cookie namespace.

| Check | Expected |
|---|---|
| `http://localhost:18000/` | Login/register UI |
| `http://localhost:18000/api/health` | JSON `{"status":"ok"}` |
| `http://localhost:18000/docs` | Swagger UI |
| Authenticated `/positions` deep-link refresh | SPA route loads, rather than JSON or 404 |
| `/api/nope` | JSON 404, not the SPA shell |

## 3. Representative feature checks

Use a synthetic email such as `walkthrough@example.com`. Registration validates normal email syntax; the app does not send email. Record actions and observations; do not mark untested cases as passed.

1. **Auth/theme:** register, log in, reload, log out/in; toggle light/dark and reload. Expect the session and theme to persist. Email is syntax-checked, but no email is sent.
2. **Accounts:** create one account to keep for trades and a second to edit/archive. Expect archived accounts to disappear by default and remain visible with “Show archived”; this is not an unarchive action.
3. **Option expiry and history:** create two stocks with different IDs (for example AAPL and TSLA), including same-symbol stocks on different exchanges if available. For the first stock, add options expiring yesterday, today and tomorrow using the current **UTC date**; add another option for the second stock. In Instruments, expect yesterday's option hidden by default and today's/tomorrow's visible. Enable “Show expired options”; yesterday's option should appear while search and kind filters still apply. Underlying filtering is checked through the API and context-aware pickers, not the management page.
4. **Older API compatibility and pagination:** with an authenticated account, use the browser Network panel or Swagger at `/docs` to request `GET /api/instruments?kind=option` and confirm the legacy default includes expired rows. Then request `include_expired=false`; expired options should be excluded. Create or seed more than 50 expired options and more than 50 matching unexpired options for one underlying. Confirm the UI can reach matching results past row 50 and expired rows do not consume the first page when hidden. `offset=50` should return the next page; filtering happens before the 50-row page limit. An unmatched underlying returns no options. If creating that many records manually is impractical, use the automated fixture and record that method.
5. **Context and inline creation:** create a Position with the first stock as Primary Instrument. In First Trade, both Add Trade entry points and each added Trade leg, expect only that exact stock ID and its options; other stocks (including same-symbol/different-ID stocks) and forex must be absent. PMCC LEAP remains option-only. Search for an option on stock A and select it, then change Primary to stock B: the visible query and next request must be empty, B's stock and options must be reachable, and A's options must be absent. Repeat with no prior search; expect the same B candidates. Switch between stock and option primaries on the same underlying: the selected contract and leg fields remain, while search is cleared. Clearing Primary restores unscoped general candidates and clears the search. Change to a different stock: incompatible option legs should clear with an explanation, while quantity, price, date, costs and notes remain. Use “create option for this underlying” with both matching and empty search results; expect underlying/currency/exchange prefilled and underlying locked. A created result outside the current context must not be selected. Duplicate natural-key creation should return the existing contract. Explicitly create a historical option: expired visibility should turn on for that picker and the new contract should become selected. Turning the switch off keeps the selected historical contract's label; clearing it requires enabling history to select it again. Reopening the picker within the same form keeps the switch; starting a new Trade form restores the default.
6. **Basic instruments and configuration:** create a stock and forex example from general instrument management, then save/reload a strategy configuration. Confirm the general Trade form still permits stock and forex.
7. **Dates and cash flow:** through Swagger at `/docs`, create an empty Position with opening date D3; the Position form requires a First Trade, so this empty setup is API-only. Add a zero-cost buy of 10 shares at 100 executed at D1, then a zero-cost sell of 10 at 110 executed at D2 (D1 < D2 < D3). Expect `opened_at` to become D1 and cash flow to be 100. Archive the D1 Trade: opening should become D2. Add the D1 fill again: opening returns to D1. Close without an explicit time: expect `closed_at=D2` and frozen realized P&L 100. Archive all fills on a separate open Position: its last opening date remains until a new active fill establishes a new date. Test a close before opening separately: it returns 422 and leaves status, dates, notes and other submitted fields unchanged. A later invalid leg in a multi-leg batch separately returns 422 with no Trades or opening-date change. A close at the exact opening instant is valid. Offset timestamps representing the same instant should compare equally. Closed Positions reject Trade create/archive writes and cannot be reopened. Use the API for boundary cases that the UI does not expose.
8. **Notes and multi-leg:** add two Trades for the same contract with different notes and a four-leg Trade with empty, long, multiline and HTML-looking text (for example `<b>sample</b>`). Notes should appear immediately under their own Trade row, span the table, preserve line breaks and display as plain text; there should be no duplicate group-bottom notes. Edit notes: Enter inserts a newline, Ctrl/Command+Enter or Save submits, Cancel discards, a failed save retains the input, clearing and saving removes the note, and a read-only transition ends editing. Archived and closed Trade restrictions remain. Submit Iron Condor, assignment, exercise and expiration examples from the appendix; legs in one submission share a group where applicable.
9. **Forms and layout:** inspect Position First Trade, Add Trade and four-leg forms at 1280px and 390px in light and dark themes. Below 600px expect one column; wider forms use two columns. Instrument and Notes span the full row, labels sit above fields and help/errors below. Trigger validation and confirm focus reaches the leg/field without losing other inputs or add/remove-leg behavior. Check keyboard navigation and cash-flow preview.
10. **Close/dashboard/deletion/persistence:** for the closed Position, verify Trade actions are unavailable. Dashboard should show the closed result, monthly bucket, win rate and account filtering, keeping currencies separate. Deleting a Position with Trades/plans is rejected. Run `tj_check restart app`; reload and verify synthetic data remains. Inspect `ls -l "$TJ_CHECK_DIR/data"` for database ownership.

Automated Vitest/pytest scenarios exercise request races, field retention, validation, date boundaries, ownership, atomicity and rollback. Record their command results separately; they do not replace paths that only a person can judge. This is representative rather than exhaustive. Record every untested manual step explicitly; browser automation and implementation checks are not owner acceptance.

## 4. Record results and clean up

Record candidate identity, checks actually run, failures, skipped paths and explicit owner acceptance in the task record. Detailed Chinese summary/walkthrough evidence stays local under `development-notes/<run-id>/`. Automated completion is distinct from human acceptance.

In the same test terminal, after collecting the necessary observations:

```bash
tj_check down
docker image rm "trading-journal:$TJ_CHECK_ID"
rm -r -- "$TJ_CHECK_DIR"
unset -f tj_check
unset TJ_SOURCE_DIR TJ_CHECK_DIR TJ_CHECK_ID PUID PGID COOKIE_SECURE DEBUG
```

This removes only the uniquely named test containers/image and directory created above. Close the SSH tunnel and synthetic browser profile. No existing deployment or data directory should be stopped or removed.

## Troubleshooting

| Symptom | Check |
|---|---|
| Migration fails | `tj_check logs migrate`; temporary data directory ownership and selected UID/GID |
| Cannot connect | Free host port, matching SSH tunnel, `tj_check ps -a` |
| Login does not persist | HTTP `COOKIE_SECURE=false`, consistent hostname, separate test browser, `/api/users/me` response |
| Missing secret warning | Current app needs no env secret; check whether an old image/template is being used |
| Stale UI | Re-run `tj_check up -d --build` on the intended candidate checkout |
| A known issue appears | Record it against its triage/task ID; do not silently change data to make the walkthrough pass |

## Appendix — event rows

See [original domain mapping](design/data-model.md#452-notion-event--atomic-trade-mapping) for exact examples.

| Event | Rows submitted together |
|---|---|
| Iron Condor open | Four option legs: both credit-spread wings |
| Assignment | Option closed at zero plus stock fill at strike |
| Exercise | Option closed at zero plus stock fill at strike |
| Expiration | One option closing fill at zero |

The badge is inferred from the recorded shape, not a declaration of strategy or an instruction to execute a real trade.
