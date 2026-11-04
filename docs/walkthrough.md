# Disposable build and feature walkthrough

> **English** · [中文](walkthrough.zh.md)

This is the current manual verification guide. Use synthetic data in a new temporary environment; it does not start or modify the normal deployment. Passing these checks records only the paths actually exercised, not owner acceptance. See the [roadmap](plan/roadmap.md) and relevant task card for scope.

MCP is implemented in the current source candidate, not in the already published `latest` or `v1.1.0` images. Its isolated walkthrough below uses the section 1 checkout build overlay; it does not publish or deploy the candidate. No existing client configuration or live journal data is reused.

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

## MCP client setup and walkthrough

The server uses the same app and database at exactly `/api/mcp`. Local clients use `http://localhost:18000/api/mcp`. A remote client uses `https://<journal-host>/api/mcp` through the HTTPS reverse proxy; keep the app port bound to loopback. Do not expose port 8000/18000 directly to the network.

For a same-host HTTPS reverse proxy, configure the app's `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` on the `app` service. Preserve the localhost/loopback defaults and add the exact public host (including port if present) and origin. These variables are JSON arrays. For example, in the temporary `local.yml` overlay from section 1:

```yaml
services:
  app:
    environment:
      JOURNAL_TIMEZONE: Europe/Amsterdam
      MCP_ALLOWED_HOSTS: '["127.0.0.1","127.0.0.1:*","localhost","localhost:*","[::1]","[::1]:*","journal.example.net"]'
      MCP_ALLOWED_ORIGINS: '["http://127.0.0.1","http://127.0.0.1:*","http://localhost","http://localhost:*","http://[::1]","http://[::1]:*","https://journal.example.net"]'
```

Replace `journal.example.net` with the actual public hostname. Normal MCP requests without an `Origin` header are allowed; do not add a wildcard. A proxy must terminate TLS, route `/api/mcp` to `http://127.0.0.1:18000/api/mcp` without stripping or rewriting the path, and preserve `Host`, `Authorization`, `Accept`, `Content-Type`, and MCP headers such as `MCP-Protocol-Version`, `MCP-Session-Id`, and `Last-Event-ID`. Disable response buffering for this endpoint. For an illustrative Nginx location on the same host:

```nginx
location = /api/mcp {
    proxy_pass http://127.0.0.1:18000;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header Origin $http_origin;
    proxy_buffering off;
}
```

Create three credentials in the disposable website at Settings → MCP: a `read` credential for a read-only check, plus separate `entry` credentials for Codex and Hermes. Name them to identify the client. The secret appears once; copy it directly into a hidden prompt and never paste it into a command, shell history, tracked file, or chat. Credentials default to 90-day expiry. Revoke the disposable credentials before cleanup if the environment is retained; deleting the temporary database also removes them.

Use the following Bash commands in a terminal that has the temporary service running. They read the secret without echo and only place the variable in the process environment. Codex runs from a new temporary working directory with temporary `log_dir` and `sqlite_home`, command-only MCP settings, `--ignore-user-config`, and `--ephemeral`; `HOME`, `CODEX_HOME`, and existing client config remain unchanged. Since user config is ignored, select any required model/provider settings yourself as additional command-level `-c` overrides and provide required auth through environment variables; do not copy settings from the existing config. No external model call is needed for a protocol preflight.

**Codex read-only query with command-level temporary settings:**

```bash
export TJ_CODEX_TMP="$(mktemp -d /tmp/tj-codex-XXXXXX)"
mkdir -p "$TJ_CODEX_TMP/cwd" "$TJ_CODEX_TMP/logs" "$TJ_CODEX_TMP/sqlite"
read -r -s -p 'Codex read token: ' TJ_CODEX_TOKEN
printf '\n'
export TJ_CODEX_TOKEN
tj_codex() {
  codex exec --ignore-user-config --ephemeral --skip-git-repo-check \
    -C "$TJ_CODEX_TMP/cwd" \
    -c "log_dir=\"$TJ_CODEX_TMP/logs\"" \
    -c "sqlite_home=\"$TJ_CODEX_TMP/sqlite\"" \
    -c 'mcp_servers.trading_journal.url="http://localhost:18000/api/mcp"' \
    -c 'mcp_servers.trading_journal.bearer_token_env_var="TJ_CODEX_TOKEN"' \
    "$@"
}
tj_codex 'Use get_context and list_accounts only. Do not prepare or commit entries.'
```

For a synthetic Codex entry, replace the read credential with its separately issued `entry` credential, then make a first one-shot `exec` that only prepares:

```bash
unset TJ_CODEX_TOKEN
read -r -s -p 'Codex entry token: ' TJ_CODEX_TOKEN
printf '\n'
export TJ_CODEX_TOKEN
tj_codex 'Use the paper account named MCP walkthrough and a synthetic USD stock named MCPTEST (create it if absent). Prepare a new spot_stock Position with one buy leg: quantity 1, price USD 1.00, at the exact execution date/time I provide. If I have not supplied the concrete date/time or any required detail, ask and stop. Show the complete preview and returned request_id and draft_id, then stop. Do not call commit_entry.'
```

Review the preview printed by that command. If it is correct, explicitly approve it in the terminal before starting a second `exec`; the second run can only commit the displayed draft:

```bash
read -r -p 'Displayed draft_id: ' TJ_DRAFT_ID
read -r -p 'After reviewing and explicitly approving that preview, type CONFIRM: ' TJ_APPROVAL
if [ "$TJ_APPROVAL" = CONFIRM ]; then
  tj_codex "The owner explicitly confirmed the displayed preview. Call commit_entry only with this exact draft_id: $TJ_DRAFT_ID. Do not prepare or change the batch."
else
  printf '%s\n' 'Not confirmed; no commit requested.'
fi
```

Each `codex exec` invocation is one-shot. If it asks a clarifying question, answer it in a new `tj_codex` invocation with the complete explicit details; do not approve or commit until you receive the complete preview. The first successful preparation stops after `prepare_entry`; keep its `draft_id` and run the second command only after explicit approval. If a commit response is uncertain, retry `commit_entry` with that same ID. A pending preview expires after 24 hours. Do not create a replacement draft to retry.

**Hermes with an isolated config directory:**

```bash
export TJ_HERMES_HOME="$(mktemp -d /tmp/tj-hermes-XXXXXX)"
mkdir -p "$TJ_HERMES_HOME"
cat > "$TJ_HERMES_HOME/config.yaml" <<'YAML'
mcp_servers:
  trading_journal:
    url: http://localhost:18000/api/mcp
    headers:
      Authorization: "Bearer ${TJ_HERMES_TOKEN}"
YAML
read -r -s -p 'Hermes read token: ' TJ_HERMES_TOKEN
printf '\n'
export TJ_HERMES_TOKEN HERMES_HOME="$TJ_HERMES_HOME"
hermes chat
```

This example uses the separate `read` credential. For entry, replace it at the hidden prompt with Hermes's own `entry` credential. Hermes expands `${VAR}` in string configuration values; the YAML stores the variable reference, not the token. `HERMES_HOME` points at the fresh temporary directory so the existing `~/.hermes/config.yaml` is untouched. See the [Hermes MCP configuration guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), and [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference) for client options and temporary runtime paths. These documented commands are setup instructions, not evidence that either installed client connected successfully.

In either client, a `read` credential must be used only for queries; direct write-tool calls are denied server-side. Only the user's explicit approval of the displayed draft counts as confirmation; the original trade description or ordinary follow-up text is not approval. For entries, have the agent clarify account, instrument/contract, action, quantity, price, execution time and option open/close intent; then show the server preview, including fees/defaults, timezone interpretation and cash flow. The owner must explicitly confirm that draft before the agent commits.

### Seven-step owner walkthrough

These steps follow [M-MCP-01 §4.2](plan/milestone-mcp-entry.md#42-owner-walkthrough). Use only the temporary database and synthetic records created from this checkout:

1. In the temporary website, create a synthetic `paper` account named `MCP walkthrough`, separate Codex and Hermes `entry` credentials, and one `read` credential. Keep each secret only for the hidden prompts above.
2. In Codex, use the first one-shot command to prepare a `spot_stock` Position and first fill for a synthetic USD stock (`MCPTEST`, create it if absent): `buy` one share at USD 1.00, with a concrete execution date/time you supply. Verify preparation alone creates no Position or Trade; inspect the full preview, explicitly approve it, then run a second one-shot command with the exact same `draft_id` and inspect the website records. The agent must ask if any requested value is missing rather than invent it.
3. In Hermes, use its separate `entry` credential to query that Position, add a Trade, and add an earlier-dated fill. Confirm `opened_at` follows the earliest active fill.
4. Prepare a multi-leg entry that creates a missing option. Before confirming, inspect its complete specifications, default multiplier/style, default fees, and per-leg cash flow.
5. Compare a timezone-less fill using the server default with a fill using an explicit IANA timezone. Inspect the preview UTC time and website browser-local display.
6. Retry the same committed `draft_id`; verify Trade counts and returned IDs do not change. Revoke an entry credential and confirm its next MCP request is rejected.
7. With the `read` credential, verify context/list queries work and `prepare_entry` plus `commit_entry` are denied, including direct tool calls.

Record skipped steps as unrun. This is a walkthrough plan; setup instructions and protocol preflight do not imply owner acceptance.

After collecting the walkthrough observations, revoke the three tokens in the website, stop only the temporary Compose project with the cleanup commands in section 4, remove the temporary Codex/Hermes directories and unset the variables:

```bash
rm -r -- "$TJ_HERMES_HOME" "$TJ_CODEX_TMP"
unset -f tj_codex
unset TJ_HERMES_HOME HERMES_HOME TJ_HERMES_TOKEN TJ_CODEX_TOKEN TJ_CODEX_TMP TJ_DRAFT_ID TJ_APPROVAL
```

If the Hermes command exits before connecting because its local dependency environment is unavailable, record the client check as unrun and retain the exact error. Do not repair, install, or alter an existing Hermes installation as part of this walkthrough.

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
