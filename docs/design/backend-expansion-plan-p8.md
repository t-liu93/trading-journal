# Backend Phase P8 — Position CRUD (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p8.zh.md)

> Status: **DRAFT v0.1** (2026-05-26). Detailed build plan for **P8** from the macro
> roadmap [backend-expansion-plan.md](./backend-expansion-plan.md). Self-contained —
> an implementer can execute it directly. Companions:
> [data-model.md §4.4](./data-model.md#44-position-universal-strategy-instance),
> the **Account template** (`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`), the recently-shipped
> [backend-expansion-plan-p7.md](./backend-expansion-plan-p7.md), and the
> settled-decision summary in
> [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions).

## 1. Purpose & context

Turn the already-migrated `positions` table into a typed CRUD API: the universal
strategy-instance aggregate that the user's whole journal hangs off (every
wheel cycle, IC, PMCC, spot trade, forex trade is a row here). No DB migration
is needed — the table exists since Phase 2's `0001_initial_schema`. P8 is
purely Pydantic schemas + a router + tests + a thin `services/positions.py`
seam reserved for future auto close-detection.

### Settled decisions (do not re-derive)

These come from [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions),
copied here in implementer-ready form:

- **Owner-scoped.** Every row has `user_id`; every endpoint filters on
  `current_active_user.id`. Cross-user access → **404** (not 403), same as
  Account / StrategyConfig.
- **Trade-led model (§6②).** A Position is always born alongside the first
  Trade (F4's inline-create flow). `opened_at` is supplied by the client and
  must equal that first Trade's `executed_at`. There is **no NULL "awaiting
  first trade" interim state**. Backend treats `opened_at` as a normal required
  field; backend does **not** look up trades at create time (the F4 flow is
  responsible for sending the right value and for posting the first Trade
  in the same client-side transaction — P9 ships the Trade endpoint).
- **Manual snapshot fields.** `status` (default `"open"`), `closed_at`,
  `capital_used`, `max_risk_at_open`, `max_reward_at_open`, `notes` are user-
  supplied / user-managed. Server-managed: `currency` (derived from
  `primary_instrument.currency`), `pnl_realized` (frozen on close), `created_at`
  / `updated_at` (timestamps).
- **Close transition freezes `pnl_realized`.** PATCH with `status: "closed"`
  triggers the server to (a) require `closed_at` (either present in the
  payload or pre-existing on the row), (b) sum `cash_flow` across all of the
  position's Trades and write the result to `pnl_realized`, and (c) commit
  in one transaction. Once frozen, `pnl_realized` is immutable. The reverse
  transition (`closed → open`) is **rejected** in MVP (would orphan a stale
  `pnl_realized`); change requires `DELETE` + re-create from trades.
- **Hard delete only when no Trades exist.** `DELETE /positions/{id}` returns
  204 only if the position has zero attached Trade rows; otherwise **409**
  with `detail="position has attached trades; delete the trades first or
  archive via PATCH"`. (No soft-delete column; data-model §4.4 has no
  `archived_at`.)
- **Validation = format only at this layer.** `account_id` and
  `primary_instrument_id` must exist and (for account) belong to the current
  user; `strategy_type` must be a valid enum value (Pydantic enforces);
  positive decimals where applicable; no cross-field business validation in
  P8 (e.g., "primary_instrument.kind matches strategy_type" is intentionally
  *not* enforced — wheel can sit on a stock instrument, IC on the underlying
  stock too; the user picks).
- **No cap enforcement against `StrategyConfig.max_exposure`.** Deferred to a
  services layer when more is known about ordering UX.

## 2. Scope

### In scope (this plan)

- `schemas/position.py` — `PositionCreate` / `PositionUpdate` / `PositionRead`
- `api/positions.py` — router with POST / GET (list) / GET (single) / PATCH /
  DELETE
- `services/positions.py` — **new module**; holds `freeze_pnl_realized()` and
  reserves room for a future auto-close detector. Routers call into it; tests
  exercise both layers.
- Wire under `/positions` in `main.py` (final URL: `/api/positions`)
- `tests/test_positions.py`
- After backend is green: regenerate `frontend/src/api/schema.d.ts`
  (`npm run codegen`) + commit

### NOT in scope

- **Auto close-detection** (net-qty / leg-state inspection). The `services/`
  module reserves the seam; no detector implementation in P8.
- **`StrategyConfig.max_exposure` enforcement** at Position create time.
- **Soft-delete / archive.** Hard delete only, and only with zero trades.
- **Derived read fields** (`days_open`, `pnl_unrealized`, `pnl_total`,
  `roi_on_capital`). Land with P12.
- **Wheel / PMCC strategy-specific snapshots** (`WheelCycleMeta` /
  `PmccCycleMeta`). Land with P10.
- **TradePlan** (P11).
- **`pnl_realized` recompute helpers exposed via API.** Internal only — the
  only public surface is the `status: open → closed` PATCH.

## 3. Files

```
backend/src/trading_journal/
├── schemas/position.py                  ← NEW
├── api/positions.py                     ← NEW
├── services/                            ← NEW package
│   ├── __init__.py                      ← NEW (empty marker)
│   └── positions.py                     ← NEW
└── main.py                              ← CHANGED: include positions.router
backend/tests/test_positions.py          ← NEW
frontend/src/api/schema.d.ts             ← REGENERATED at the end
```

> `services/` is a new top-level package under `trading_journal/`. Routers
> become thin adapters; the close-transition logic lives in the service so a
> future auto-close detector can plug in without router changes.

## 4. Schema shapes (target)

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import PositionStatus, StrategyType


class PositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    opened_at: datetime  # must equal first Trade's executed_at (F4 sends it)

    # Optional manual snapshot fields
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # IMMUTABLE (rejected by extra="forbid"):
    #   account_id, primary_instrument_id, strategy_type, opened_at,
    #   currency, pnl_realized, created_at, updated_at

    status: PositionStatus | None = None  # only "closed" is meaningful here
    closed_at: datetime | None = None
    capital_used: Decimal | None = Field(default=None, gt=0)
    max_risk_at_open: Decimal | None = Field(default=None, gt=0)
    max_reward_at_open: Decimal | None = Field(default=None, gt=0)
    notes: str | None = None


class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    primary_instrument_id: uuid.UUID
    strategy_type: StrategyType
    status: PositionStatus
    opened_at: datetime
    closed_at: datetime | None
    capital_used: Decimal | None
    max_risk_at_open: Decimal | None
    max_reward_at_open: Decimal | None
    pnl_realized: Decimal | None
    currency: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

**Notes on the shapes.**

- `extra="forbid"` on both write schemas means any attempt to set immutable
  fields via PATCH returns 422 with a specific field error — no silent
  ignore.
- `opened_at: datetime` is **required** on create — there is no
  `default_factory=datetime.utcnow`. The F4 client computes it from the
  first Trade payload before posting Position-then-Trade.
- `closed_at` on `PositionUpdate` is only honored when the same PATCH also
  carries `status: "closed"`, OR `status` is already `"closed"` and the user
  wants to amend the close timestamp. Setting `closed_at` on an open
  position without `status: "closed"` → 422.
- `currency` is **absent** from both write schemas; server derives from
  `primary_instrument.currency` and returns it on read.
- `pnl_realized` is **absent** from both write schemas; server-managed only.

## 5. Service-layer surface (`services/positions.py`)

```python
async def freeze_pnl_realized(
    session: AsyncSession,
    position: Position,
) -> Decimal:
    """Sum `cash_flow` over all Trade rows for this position; assign to
    position.pnl_realized; return the value. Caller commits."""
```

In P8 there are no Trade rows yet (P9 ships them), so `SUM(cash_flow)`
evaluates to `0` on real data. The function is still wired into the close
transition so that once P9 lands, close behavior is correct without router
changes. Tests for the freezing path use direct `Trade.__table__.insert()`
(bypassing the not-yet-existent P9 router) to fixture-create a trade row,
proving end-to-end behavior — see §6.

Future expansion slot (no code in P8, just the docstring):

```python
async def detect_auto_close(
    session: AsyncSession,
    position: Position,
) -> bool:
    """Reserved for a future auto-close detector. P8 does not implement.
    Routers do not call this yet."""
```

## 6. Phased plan

Three sub-phases. After each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src` — baseline is **127 tests** after F2 codegen / current main.

### P8.1 — Schemas + service skeleton

**Goal.** All the typed surfaces exist; no router wired yet.

**Tasks.**

1. **`schemas/position.py`** — the three classes above.
2. **`services/__init__.py`** — empty marker.
3. **`services/positions.py`** — `freeze_pnl_realized` (implemented),
   `detect_auto_close` (docstring stub raising `NotImplementedError`).
4. Unit tests for `freeze_pnl_realized` directly (no HTTP layer):
   `tests/test_positions.py::test_freeze_pnl_realized_sums_cash_flow`
   inserts a position + 3 trades via raw SQL `INSERT`, calls the function,
   asserts the position's `pnl_realized` matches `sum(cash_flow)`.

**Acceptance.** Schemas import cleanly; service unit test green; no API
surface yet.

### P8.2 — Router + create / read / list / patch / delete

**Goal.** Full CRUD pipeline working over HTTP.

**Tasks.**

1. **`api/positions.py`** — router under `/positions`. Private helpers:

   ```python
   async def _get_owned_position(
       session: AsyncSession, user: User, position_id: uuid.UUID
   ) -> Position:
       stmt = select(Position).where(
           Position.id == position_id, Position.user_id == user.id
       )
       pos = (await session.execute(stmt)).scalar_one_or_none()
       if pos is None:
           raise HTTPException(404, "Position not found")
       return pos

   async def _resolve_account(
       session: AsyncSession, user: User, account_id: uuid.UUID
   ) -> Account:
       stmt = select(Account).where(
           Account.id == account_id,
           Account.user_id == user.id,
           Account.archived_at.is_(None),
       )
       acct = (await session.execute(stmt)).scalar_one_or_none()
       if acct is None:
           raise HTTPException(422, "Account not found or archived")
       return acct

   async def _resolve_instrument(
       session: AsyncSession, instrument_id: uuid.UUID
   ) -> Instrument:
       inst = await session.get(Instrument, instrument_id)
       if inst is None:
           raise HTTPException(422, "Instrument not found")
       return inst
   ```

2. Endpoints:

   | Method | Path | Behavior |
   |---|---|---|
   | `POST` | `""` | Resolve account (owner + not archived) → 422 if not. Resolve instrument → 422 if not. Insert `Position` with server-set `user_id`, `currency = instrument.currency`, `status = "open"`. Return 201. |
   | `GET` | `""` | Owner-scoped. Optional query: `status=open\|closed`, `strategy_type=<enum>`. Order: `opened_at DESC, created_at DESC`. |
   | `GET` | `"/{id}"` | Single; 404 on cross-user or missing. |
   | `PATCH` | `"/{id}"` | Partial update with `exclude_unset`. **Close-transition branch** (see below). Returns 200 with updated row. |
   | `DELETE` | `"/{id}"` | 204 if no Trade rows exist; 409 otherwise. |

3. **PATCH close-transition branch.** Pseudocode:

   ```python
   data = payload.model_dump(exclude_unset=True)

   # Reject closed_at without status flip (and not already closed).
   if "closed_at" in data and data.get("status") != PositionStatus.CLOSED \
           and position.status != PositionStatus.CLOSED:
       raise HTTPException(422, "closed_at can only be set on closed positions")

   # Reject closed → open.
   if "status" in data and position.status == PositionStatus.CLOSED \
           and data["status"] == PositionStatus.OPEN:
       raise HTTPException(422, "reopening a closed position is not supported")

   transitioning_to_closed = (
       "status" in data
       and data["status"] == PositionStatus.CLOSED
       and position.status != PositionStatus.CLOSED
   )

   # Apply the simple fields first.
   for field, value in data.items():
       setattr(position, field, value)

   if transitioning_to_closed:
       if position.closed_at is None:
           # require closed_at in this same PATCH or on the row already
           raise HTTPException(422, "closed_at is required when closing")
       await freeze_pnl_realized(session, position)

   await session.commit()
   await session.refresh(position)
   ```

4. **`main.py`** — register the router (`api.include_router(positions.router)`
   with a one-line comment), mirroring how `instruments.router` and
   `strategy_configs.router` are wired.

5. **`tests/test_positions.py`** — see §7 below for the full matrix.

**Acceptance.** All P8 tests green; backend green.

### P8.3 — Regression + codegen + brief

**Goal.** Lock the baseline and propagate types to the frontend.

**Tasks.**

1. Backend: `uv run pytest -q && uv run ruff check . && uv run mypy src` —
   all green. Expected total ≈ **127 + ~30 P8 tests = ~157 tests**.
2. Frontend codegen: backend up on `:8000`, then
   `cd frontend && npm run codegen` → `git diff src/api/schema.d.ts` should
   show new `PositionCreate / Update / Read` schemas plus the `PositionStatus`
   enum. `npm run build` passes; **commit the regenerated `schema.d.ts`**.
3. Walk the §8 curl recipe end-to-end.
4. Leave an implementation brief in `review-notes/p8_implementation_brief.md`
   (mirror P6 / P7 briefs).

**Acceptance.** All green; `schema.d.ts` committed; recipe passes; brief in
place.

## 7. Test matrix

`tests/test_positions.py`, reusing `auth_client`, `second_user_client`, and
the migrated tempfile fixture from `conftest.py`. Add a small helper to
seed `Account` and `Instrument` rows in the fresh DB (current tests already
do this for accounts; reuse the pattern).

### Service-layer tests

| Test | Validates |
|---|---|
| `test_freeze_pnl_realized_zero_trades` | Position with no trades → `pnl_realized = 0` |
| `test_freeze_pnl_realized_sums_cash_flow` | 3 inserted trades with mixed signs → sum is exact |

### POST `/positions`

| Test | Validates |
|---|---|
| `test_create_201_with_required_fields` | Minimum payload (account, instrument, strategy_type, opened_at) → 201 with `status="open"`, `currency` derived |
| `test_create_with_optional_fields` | All optional snapshots populated round-trip |
| `test_create_rejects_unknown_field_422` | `extra="forbid"` works |
| `test_create_rejects_missing_opened_at_422` | required field check |
| `test_create_rejects_status_in_body_422` | `status` is immutable via create — server sets it |
| `test_create_rejects_currency_in_body_422` | `currency` is derived — server sets it |
| `test_create_rejects_pnl_realized_in_body_422` | server-managed |
| `test_create_rejects_unknown_account_422` | non-existent account_id → 422 |
| `test_create_rejects_other_users_account_422` | account belongs to another user → 422 |
| `test_create_rejects_archived_account_422` | archived account → 422 |
| `test_create_rejects_unknown_instrument_422` | non-existent instrument_id → 422 |
| `test_create_rejects_bad_strategy_type_422` | invalid enum → 422 |
| `test_create_rejects_nonpositive_capital_used_422` | `gt=0` works |
| `test_create_derives_currency_from_instrument` | stock USD → position currency USD; forex EURUSD → position currency USD |

### GET `/positions` (list)

| Test | Validates |
|---|---|
| `test_list_returns_only_current_user_rows` | Cross-user isolation |
| `test_list_orders_by_opened_at_desc` | Most-recently-opened first |
| `test_list_filter_status_open` | `?status=open` filter |
| `test_list_filter_status_closed` | `?status=closed` filter |
| `test_list_filter_strategy_type` | `?strategy_type=wheel` filter |
| `test_list_filter_combined` | both filters together |
| `test_list_rejects_bad_filter_422` | `?status=cowabunga` → 422 |

### GET `/positions/{id}`

| Test | Validates |
|---|---|
| `test_get_200` | own row → 200 |
| `test_get_404_unknown` | random UUID → 404 |
| `test_get_404_cross_user` | other user's id → 404 (not 403) |

### PATCH `/positions/{id}`

| Test | Validates |
|---|---|
| `test_patch_updates_notes` | basic partial update |
| `test_patch_updates_snapshot_fields` | capital_used / max_risk / max_reward |
| `test_patch_rejects_account_id_change_422` | `extra="forbid"` |
| `test_patch_rejects_primary_instrument_id_change_422` | immutable |
| `test_patch_rejects_strategy_type_change_422` | immutable |
| `test_patch_rejects_opened_at_change_422` | immutable |
| `test_patch_rejects_currency_change_422` | immutable |
| `test_patch_rejects_pnl_realized_change_422` | immutable |
| `test_patch_close_transition_freezes_pnl_realized` | with 3 seeded trades, PATCH `{status: closed, closed_at: ...}` → row's `pnl_realized == sum(cash_flow)` |
| `test_patch_close_transition_with_zero_trades` | `pnl_realized = 0` after close |
| `test_patch_close_rejects_missing_closed_at_422` | closing without `closed_at` → 422 |
| `test_patch_rejects_closed_at_on_open_position_422` | setting `closed_at` without `status: closed` while open → 422 |
| `test_patch_allows_closed_at_amend_when_already_closed` | already-closed → can amend `closed_at` |
| `test_patch_rejects_reopen_422` | closed → open transition → 422 |
| `test_patch_pnl_realized_immutable_after_close` | second PATCH to a closed position never changes `pnl_realized` |
| `test_patch_advances_updated_at` | `updated_at` strictly increases |
| `test_patch_404_cross_user` | other user's id → 404 |

### DELETE `/positions/{id}`

| Test | Validates |
|---|---|
| `test_delete_204_when_no_trades` | hard-delete succeeds; row gone |
| `test_delete_409_when_trades_exist` | seeded trade row → 409 with the documented detail |
| `test_delete_404_cross_user` | other user's id → 404 |

### Auth

| Test | Validates |
|---|---|
| `test_requires_auth` | parametrized POST/GET/PATCH/DELETE without cookie → 401 |

## 8. Manual verification reference (full P8 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# Register + login
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed: an account + an instrument
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR Margin","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)

INSTR=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)

# 1. Create position → 201; currency derived as USD
curl -fsSi -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$INSTR\",\"strategy_type\":\"spot_stock\",\"opened_at\":\"2026-05-20T14:30:00Z\",\"capital_used\":\"5000\"}"

POS=$(curl -fsS "$BASE/api/positions" -b "$JAR" | jq -r '.[0].id')

# 2. PATCH notes
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"Initial 100 shares; target 220."}'

# 3. Try to mutate an immutable field → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel"}'

# 4. Try to close without closed_at → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed"}'

# 5. Close properly → 200; pnl_realized = 0 (no trades yet); closed_at set
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-15T20:00:00Z"}'

# 6. Try to reopen → 422
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"open"}'

# 7. List, filter
curl -fsS "$BASE/api/positions" -b "$JAR"
curl -fsS "$BASE/api/positions?status=closed&strategy_type=spot_stock" -b "$JAR"

# 8. Delete (no trades attached) → 204
curl -fsSi -X DELETE "$BASE/api/positions/$POS" -b "$JAR"
curl -fsSi "$BASE/api/positions/$POS" -b "$JAR"   # → 404
```

## 9. Implementer quickstart

```bash
cd backend
# build P8.1 → P8.2 → P8.3; after each:
uv run pytest -q && uv run ruff check . && uv run mypy src

# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

After P8 lands, the next backend gates are P10 (strategy-meta extensions)
and P11 (TradePlan event stream) — both ride on a Position and unblock
frontend F3. P9 (Trade CRUD with server-computed `cash_flow`) unblocks F4
and is where the inline Position-create flow actually exercises the P8
schemas end-to-end.

## 10. Future-proofing notes (don't implement, just don't preclude)

- **Auto close-detection** plugs into `services/positions.py::detect_auto_close`.
  P12 (derived layer) is the natural place to start invoking it — e.g., a
  background job or a hook after `Trade.create`.
- **Soft-delete / archive** can be added later by introducing an
  `archived_at` column + filter in list; routers would extend not replace.
- **Cap enforcement** (refusing creates when
  `sum(open.max_risk_at_open) + new ≥ StrategyConfig.max_exposure`) belongs
  in `services/positions.py` and would be invoked from POST. Keep the
  router thin so this addition is purely additive.

---

## Changelog

- **v0.1 (2026-05-26)** — Initial P8 build plan under the settled Trade-led
  model: `opened_at` client-supplied at create, `status`/`closed_at` manual,
  `pnl_realized` server-frozen at close, hard-delete only with zero trades.
  Three sub-phases: P8.1 schemas+service, P8.2 router+tests, P8.3
  regression+codegen+brief. `services/positions.py` introduced as the seam
  for future auto-close detection and cap enforcement.
