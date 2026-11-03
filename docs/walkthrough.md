# Disposable build and feature walkthrough

> **English** · [中文](walkthrough.zh.md)

This is the current manual verification guide. Use synthetic data in a new temporary environment; it does not start or modify the normal deployment. Passing these checks records only the paths actually exercised, not acceptance of every deferred feature. See the [roadmap](plan/roadmap.md) and relevant task card for scope.

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

Use a synthetic email such as `walkthrough@example.test`. Record actions and observations; do not mark untested cases as passed.

1. **Auth/theme:** register, log in, reload, log out/in; toggle light/dark and reload. Expect the appropriate session and theme persistence.
2. **Accounts:** create one account to keep for trades and a second to edit/archive. Expect archived accounts to disappear by default and remain visible with “Show archived”; this is not an unarchive action.
3. **Instruments/config:** create stock, option and forex examples; exercise inline creation and duplicate get-or-create. Verify expiry/strike/type distinguish option contracts. Save/reload a strategy configuration.
4. **Position/first Trade:** create a stock Position including its required First Trade. With no costs, buy quantity 10 at price 100; expect cash flow −1000. Visit Overview, Meta, Plan and Trades. Set capital used to 1000. For wheel/PMCC use separate synthetic examples to check their metadata; append two plan revisions and verify both remain.
5. **Trade operations:** add a sell of 10 at 110 with zero costs and a later timestamp; expect +1100, total cash flow 100. In a separate open Position, edit notes, archive a Trade and toggle archived visibility. Archived rows remain stored and are excluded from totals. Record the known notes-placement/date issues from [triage](triage/improvements.md); this guide does not declare them fixed.
6. **Multi-leg:** submit synthetic Iron Condor, assignment, exercise and expiration examples using the appendix. Multiple legs in one submission share an order group; pattern badges should match supported shapes. A one-row event need not have a group ID.
7. **Close/dashboard:** close the stock Position from step 5 with both fills active. Expect frozen realized P&L 100 and the latest fill as default close time. Verify closed Trade actions are unavailable. Dashboard should show the closed result, monthly bucket, win rate and account filtering, keeping currencies separate.
8. **Deletion/persistence:** deleting a Position with Trades/plans is rejected. In the test terminal run `tj_check restart app`; reload and verify the synthetic data remains. Inspect `ls -l "$TJ_CHECK_DIR/data"` for database ownership.

This is a representative walkthrough, not exhaustive regression coverage. For each task add its specific boundary cases and verify them before acceptance; independent review and automated checks have separate records.

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
