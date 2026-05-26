# Backend Phase P11 — TradePlan event stream (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p11.zh.md)

> Status: **DRAFT v0.1** (2026-05-26). Detailed build plan for **P11** from
> the macro roadmap [backend-expansion-plan.md](./backend-expansion-plan.md).
> Self-contained — an implementer can execute it directly. Companions:
> [data-model.md §4.6](./data-model.md#46-tradeplan-event-stream) (TradePlan
> field definitions + the "TradePlan only captures intent" partition vs.
> Trade), the just-drafted
> [backend-expansion-plan-p10.md](./backend-expansion-plan-p10.md) (the
> nested-sub-resource URL precedent), and the
> settled-decision summary in
> [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions).

## 1. Purpose & context

Turn the already-migrated `trade_plans` table into a typed API: a per-Position
**event stream** of plan revisions. Each row is one revision; the latest
revision (`MAX(revision_no)`) is the current plan; older rows survive as
history. The original Excel inspiration is forex CFD entries with evolving
SL/TP levels, but the table is strategy-agnostic — wheel thesis notes,
PMCC plans, and IC entry hypotheses all fit.

P11 is **pure Pydantic + router + a tiny service for revision_no
allocation + tests**. No DB migration — the table exists since Phase 2's
`0001_initial_schema` (including the `UNIQUE (position_id, revision_no)`
constraint, which P11 leans on). Endpoint count is small: one write, three
reads, no PATCH, no DELETE. The doc is correspondingly compact.

P11 unblocks the Plan tab on F3's Position detail page and completes the
backend half of the F3 surface (P8 Position + P10 meta + P11 plan).

### Settled decisions (do not re-derive)

Three sub-decisions agreed with the user on 2026-05-26, plus by-precedent
choices inherited from P7/P8/P9/P10:

- **Server-allocated `revision_no`.** `TradePlanCreate` does NOT include
  `revision_no`; client supplying it → 422 `extra_forbidden`. Server
  computes `MAX(revision_no) + 1` per `position_id` (1 for the first
  revision). Unique-constraint collision (concurrent appends) is the only
  failure mode and is essentially impossible in single-user MVP; if it
  ever fires we retry once, then surface 503.
- **Strictly append-only.** **No PATCH, no DELETE endpoint.** A revision,
  once appended, is permanent. To correct a mistake the user appends a
  new revision (often using `reason` to label it "corrects revision N").
  This is the cleanest read of data-model §4.6's "event stream" idiom and
  matches how F3's Plan tab will render — a true history table, not a
  history-with-edits-mixed-in.
- **List sorted oldest-first.** `GET /positions/{pid}/trade-plans` returns
  rows in ascending `revision_no` order — revision 1 → N — so the F3
  Plan tab reads top-to-bottom like a journal. This deliberately differs
  from Position/Trade list endpoints (which are newest-first); event
  streams are read chronologically.
- **No `strategy_type` restriction.** Any Position can carry TradePlan
  revisions regardless of its strategy (`spot_forex` is the primary use
  case per data-model §5.5, but wheel thesis notes and PMCC plans are
  legitimate). Server does not check strategy_type — the user picks
  whether to use this surface.
- **closed-position is NOT a lock for TradePlan writes.** Like P10
  (strategy-meta), TradePlan is intent / journal data, not a financial
  event. Users frequently want to append a post-mortem revision after
  closing a position. `pnl_realized` is not derived from TradePlan so
  there is no staleness risk.
- **Owner-scoped via Position.** TradePlan has no direct `user_id`;
  ownership flows through `position.user_id`. Cross-user `position_id`
  → **404** (matching P6/P7/P8/P9/P10).
- **Nested sub-resource URLs.** `/positions/{pid}/trade-plans/...` —
  mirrors P10's `/positions/{pid}/wheel-meta` precedent. No flat
  collection (no use case for "list all revisions across positions"
  in MVP).
- **`effective_at` is client-supplied and required.** Per data-model §4.6
  "When this revision became the active plan" — semantically distinct
  from server-managed `created_at` (when the row was recorded). The
  client picks. Defaulting to `now()` is a frontend convenience.
- **Format-only field validation.** Numeric fields (`planned_entry`,
  `planned_stop_loss`, `planned_take_profit`, `target_rr`) are all
  optional and, when present, must be `> 0`. No cross-field validation
  (e.g., "for a long plan, stop_loss < entry < take_profit" is **not**
  enforced — direction depends on long/short and the user picks).
- **No new migration.** Table exists since `0001_initial_schema`,
  including the unique constraint.

## 2. Scope

### In scope (this plan)

- `schemas/trade_plan.py` — `TradePlanCreate` / `TradePlanRead`. **No
  Update schema** (no PATCH endpoint).
- `services/trade_plans.py` — `allocate_next_revision_no()`. Single
  function, isolated for direct unit testing of the MAX+1 query.
- `api/trade_plans.py` — router with **four endpoints**: POST,
  GET list, GET current, GET by revision_no.
- Wire under `/positions` in `main.py` (final URL prefix
  `/api/positions/{pid}/trade-plans`).
- `tests/test_trade_plans.py`.
- After backend is green: regenerate `frontend/src/api/schema.d.ts` +
  commit.

### NOT in scope

- **No PATCH / DELETE on revisions.** Strictly append-only — see §1.
- **No `revision_no` rewrite / compaction.** Sequence is whatever
  history produced; never reshuffled.
- **No cross-position queries** (e.g., "all forex positions' current
  plans"). Belongs to F5 dashboards / P12 derived layer.
- **No flat `/trade-plans` collection.**
- **No diff endpoint** ("changed fields between revision N and N+1"). A
  client-side computation; do not over-build.
- **No strategy_type restriction.**
- **No cross-field plan validation.**
- Frontend F3 implementation.

## 3. Files

```
backend/src/trading_journal/
├── schemas/trade_plan.py                  ← NEW
├── services/trade_plans.py                ← NEW
├── api/trade_plans.py                     ← NEW
└── main.py                                ← CHANGED: include trade_plans.router
backend/tests/test_trade_plans.py          ← NEW
frontend/src/api/schema.d.ts               ← REGENERATED at end
```

Naming note: the **schema** module is singular (`trade_plan.py`, matching
`schemas/account.py`, `schemas/position.py`, `schemas/trade.py`); the
**service** module is plural (`services/trade_plans.py`, matching
`services/positions.py`, `services/trades.py`). Same for `api/`.

## 4. Schema shapes (target)

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TradePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_at: datetime  # required — semantically distinct from created_at
    planned_entry: Decimal | None = Field(default=None, gt=0)
    planned_stop_loss: Decimal | None = Field(default=None, gt=0)
    planned_take_profit: Decimal | None = Field(default=None, gt=0)
    target_rr: Decimal | None = Field(default=None, gt=0)
    thesis: str | None = None
    reason: str | None = None
    # NOT accepted (rejected by extra="forbid"):
    #   position_id (URL-bound), revision_no (server-allocated),
    #   id (server-generated), created_at (server-managed)


class TradePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    revision_no: int
    effective_at: datetime
    planned_entry: Decimal | None
    planned_stop_loss: Decimal | None
    planned_take_profit: Decimal | None
    target_rr: Decimal | None
    thesis: str | None
    reason: str | None
    created_at: datetime
```

**Notes on shapes.**

- No `TradePlanUpdate` class. There is no PATCH endpoint; emitting an
  Update schema would be dead code.
- `extra="forbid"` on `TradePlanCreate` enforces all the "not accepted"
  fields. A 422 error from a client-supplied `revision_no` is the
  user-facing reminder that revisions are server-numbered.
- All four numeric fields are independently optional; the user can
  record "just the thesis", or "just entry+SL", etc. — the schema
  doesn't bundle them.
- `effective_at` is **required** on create. There is no
  `default_factory=datetime.utcnow` — F3's UI defaults the field to
  `now()` but the *contract* is "tell me when this plan went live."

## 5. Service-layer surface (`services/trade_plans.py`)

```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.trade_plan import TradePlan


async def allocate_next_revision_no(
    session: AsyncSession, position_id: uuid.UUID
) -> int:
    """Return MAX(revision_no) + 1 for this position, or 1 if no prior
    revisions exist. Caller is responsible for inserting under that
    number inside the same session/transaction.

    Concurrency note: the unique `(position_id, revision_no)` constraint
    on `trade_plans` is the authoritative serializer. If two concurrent
    appends compute the same next number, the second INSERT raises
    IntegrityError; the router catches it and either retries once or
    surfaces 503. Single-user MVP makes this essentially unreachable.
    """
    stmt = select(func.max(TradePlan.revision_no)).where(
        TradePlan.position_id == position_id
    )
    current = (await session.execute(stmt)).scalar()
    return 1 if current is None else current + 1
```

That is the entire service-layer surface. Other route logic (resolve
position, owner check, single-revision-lookup) stays in `api/` since
it doesn't generalize. Future expansion (e.g., a "current plan delta"
helper for P12) can live in this module without disturbing the router.

## 6. Phased plan

Three sub-phases. After each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src` — baseline depends on which phases have already landed.
**With P9 + P10 done before P11**: baseline ≈ 243 + 45 = ~288. **P11 first
after P8**: baseline = 183.

### P11.1 — Schemas + service helper

**Goal.** Typed surfaces and the revision allocator exist; no HTTP yet.

**Tasks.**

1. `schemas/trade_plan.py` — `TradePlanCreate`, `TradePlanRead`.
2. `services/trade_plans.py` — `allocate_next_revision_no`.
3. Service-layer unit tests in `tests/test_trade_plans.py`:
   - `test_allocate_next_revision_no_empty_returns_1` — no prior
     revisions on the position.
   - `test_allocate_next_revision_no_sequential` — insert 3 revisions
     via raw `Trade.__table__` style INSERTs, allocator returns 4.
   - `test_allocate_next_revision_no_isolated_per_position` — two
     positions each at revision 3 don't interfere.

**Acceptance.** Schemas import cleanly; service unit tests green; no API
yet.

### P11.2 — Router + the four endpoints

**Goal.** All four endpoints live over HTTP.

**Tasks.**

1. `api/trade_plans.py` — single `APIRouter` with `prefix="/positions"`.
   Private helpers:

   ```python
   async def _resolve_position(
       session: AsyncSession, user: User, position_id: uuid.UUID
   ) -> Position:
       stmt = select(Position).where(
           Position.id == position_id, Position.user_id == user.id
       )
       pos = (await session.execute(stmt)).scalar_one_or_none()
       if pos is None:
           raise HTTPException(404, "Position not found")
       return pos
   ```

2. **Endpoints.**

   | Method | Path | Behavior |
   |---|---|---|
   | `POST` | `/{pid}/trade-plans` | Resolve position. `revision_no = await allocate_next_revision_no(session, pid)`. Insert. On IntegrityError (unique-constraint conflict): retry once with a fresh allocate; on second failure raise 503 `"concurrent revision allocation failed; please retry"`. Return 201 + `TradePlanRead`. |
   | `GET` | `/{pid}/trade-plans` | Resolve position. List all revisions for this position, **ordered `revision_no ASC`**. Returns 200 + `list[TradePlanRead]` (possibly empty). |
   | `GET` | `/{pid}/trade-plans/current` | Resolve position. Fetch the row with max `revision_no`. **404 if no revisions exist** ("no current plan; append one first"). Returns 200 + `TradePlanRead`. |
   | `GET` | `/{pid}/trade-plans/{revision_no}` | Resolve position. `revision_no` is `int` path param. Fetch by `(position_id, revision_no)`. **404 if missing**. Returns 200. |

3. **Route ordering.** Mount `/current` **before** `/{revision_no:int}` so
   FastAPI route resolution doesn't accidentally try to parse `current`
   as an int. With `revision_no: int` typed, "current" wouldn't match,
   but explicit ordering removes the question. Equivalently, declare
   `/current` as a fixed-path route.

4. **Closed-position is intentionally NOT checked.** Tests in §7
   include `test_append_allowed_on_closed_position` to prevent
   regression.

5. **`main.py`** — register `trade_plans.router` alongside
   `strategy_meta.router`. Both share `prefix="/positions"` and route to
   different sub-paths; FastAPI handles the combined router tree without
   conflict.

6. `tests/test_trade_plans.py` — full matrix from §7.

**Acceptance.** All P11 tests green; full suite + ruff + mypy clean.
Expected additions: **~30 tests**.

### P11.3 — Regression + codegen + brief

**Goal.** Lock the baseline; propagate to frontend.

**Tasks.**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` — green.
2. Frontend codegen. Backend up on `:8000`, `cd frontend && npm run
   codegen` → expect `TradePlanCreate`, `TradePlanRead`; `npm run build`
   passes; commit `schema.d.ts`.
3. Walk the §8 curl recipe end-to-end.
4. Leave `review-notes/p11_implementation_brief.md`.

**Acceptance.** All green; recipe passes; brief filed.

## 7. Test matrix

`tests/test_trade_plans.py`, reusing `auth_client`, `second_user_client`,
and the migrated tempfile fixture. Helper seeds at least one open and
one closed Position so closed-position-allowed tests have a target.

### Service-layer tests (no HTTP)

| Test | Validates |
|---|---|
| `test_allocate_next_revision_no_empty_returns_1` | first revision base case |
| `test_allocate_next_revision_no_sequential` | 3 inserted → returns 4 |
| `test_allocate_next_revision_no_isolated_per_position` | another position's revisions don't bleed in |

### POST `/positions/{pid}/trade-plans`

| Test | Validates |
|---|---|
| `test_create_first_revision_201_revision_no_is_1` | min payload (only `effective_at`) → 201, server sets revision_no=1, created_at populated |
| `test_create_with_all_fields` | every optional field round-trips |
| `test_create_second_revision_revision_no_is_2` | sequential allocation |
| `test_create_third_revision_revision_no_is_3` | further sequencing |
| `test_create_rejects_position_id_in_body_422` | URL-bound |
| `test_create_rejects_revision_no_in_body_422` | server-allocated |
| `test_create_rejects_id_in_body_422` | server-generated |
| `test_create_rejects_created_at_in_body_422` | server-managed |
| `test_create_rejects_missing_effective_at_422` | required |
| `test_create_rejects_negative_planned_entry_422` | gt=0 |
| `test_create_rejects_zero_planned_entry_422` | strict gt (not ge) |
| `test_create_rejects_negative_planned_stop_loss_422` | gt=0 |
| `test_create_rejects_negative_planned_take_profit_422` | gt=0 |
| `test_create_rejects_negative_target_rr_422` | gt=0 |
| `test_create_allows_thesis_only` | minimal narrative revision |
| `test_create_404_unknown_position` | random pid |
| `test_create_404_cross_user` | other user's pid → 404 (not 403) |
| `test_create_append_allowed_on_closed_position` | settled — closed is NOT a lock |
| `test_create_does_not_mutate_position` | parent position row untouched (updated_at, status, etc. unchanged) |

### GET `/positions/{pid}/trade-plans` (list)

| Test | Validates |
|---|---|
| `test_list_empty_returns_empty_array` | no revisions yet → 200, [] |
| `test_list_oldest_first` | revisions appear in revision_no ASC order |
| `test_list_isolated_per_position` | only this position's revisions returned |
| `test_list_404_unknown_position` | |
| `test_list_404_cross_user` | |

### GET `/positions/{pid}/trade-plans/current`

| Test | Validates |
|---|---|
| `test_get_current_404_when_no_revisions` | "no current plan; append one first" |
| `test_get_current_returns_latest_after_one` | revision_no=1 returned |
| `test_get_current_returns_latest_after_multiple` | revision_no=3 returned after 3 appends |
| `test_get_current_404_cross_user` | |

### GET `/positions/{pid}/trade-plans/{revision_no}`

| Test | Validates |
|---|---|
| `test_get_specific_revision_200` | by revision_no path param |
| `test_get_specific_revision_404_unknown` | revision_no=99 when only 3 exist |
| `test_get_specific_revision_404_cross_user` | |
| `test_get_specific_revision_route_does_not_clash_with_current` | request `/{pid}/trade-plans/current` is the dedicated route; `/{pid}/trade-plans/1` returns revision 1; "current" is never parsed as an int |
| `test_get_specific_revision_422_on_non_int` | `/{pid}/trade-plans/abc` → 422 |

### Append-only invariants

| Test | Validates |
|---|---|
| `test_no_patch_endpoint` | `client.patch(f".../trade-plans/1", json={...})` → 405 (Method Not Allowed) |
| `test_no_delete_endpoint` | `client.delete(f".../trade-plans/1")` → 405 |
| `test_no_root_delete_endpoint` | `client.delete(f".../trade-plans")` → 405 |
| `test_no_patch_on_current` | `client.patch(f".../trade-plans/current")` → 405 |

### Auth

| Test | Validates |
|---|---|
| `test_requires_auth` | parametrized POST/GET (×3) without cookie → 401 |

## 8. Manual verification reference (full P11 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# Register + login
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"dave@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=dave@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed: account + a forex pair + a forex position
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"FX","broker":"OANDA","account_type":"margin","base_currency":"USD"}' | jq -r .id)
# EURUSD forex instrument (the kind/symbol exact shape may differ — see your
# instruments router; this is illustrative):
PAIR=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"forex","symbol":"EURUSD","currency":"USD","forex_pair":{"base_currency":"EUR","quote_currency":"USD"}}' | jq -r .id)
POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$PAIR\",\"strategy_type\":\"spot_forex\",\"opened_at\":\"2026-06-01T08:00:00Z\"}" | jq -r .id)

# 1) GET current on empty → 404 with detail
curl -sSi "$BASE/api/positions/$POS/trade-plans/current" -b "$JAR"

# 2) Append revision 1 — initial thesis + levels
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{
    "effective_at":"2026-06-01T08:00:00Z",
    "planned_entry":"1.0850",
    "planned_stop_loss":"1.0800",
    "planned_take_profit":"1.0950",
    "target_rr":"2",
    "thesis":"Breakout retest of weekly resistance turned support."
  }'

# 3) Append revision 2 — move SL to BE after +1R
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{
    "effective_at":"2026-06-03T14:30:00Z",
    "planned_entry":"1.0850",
    "planned_stop_loss":"1.0850",
    "planned_take_profit":"1.0950",
    "target_rr":"2",
    "reason":"Moved SL to BE after +1R."
  }'

# 4) GET current → revision 2
curl -fsS "$BASE/api/positions/$POS/trade-plans/current" -b "$JAR" | jq

# 5) List → oldest first
curl -fsS "$BASE/api/positions/$POS/trade-plans" -b "$JAR" | jq '[.[] | {revision_no, planned_stop_loss, reason}]'

# 6) GET specific revision
curl -fsS "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR" | jq

# 7) Append on a CLOSED position → still 201 (settled decision)
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-10T18:00:00Z"}'
curl -fsSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"effective_at":"2026-06-10T18:00:00Z","reason":"Post-mortem: hit TP after one SL adjustment. Repeat the setup."}'

# 8) PATCH and DELETE both blocked → 405
curl -sSi -X PATCH "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"reason":"oops"}'
curl -sSi -X DELETE "$BASE/api/positions/$POS/trade-plans/1" -b "$JAR"

# 9) Client tries to send revision_no → 422
curl -sSi -X POST "$BASE/api/positions/$POS/trade-plans" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"effective_at":"2026-06-11T00:00:00Z","revision_no":42}'
```

## 9. Implementer quickstart

```bash
cd backend
# build P11.1 → P11.2 → P11.3; after each:
uv run pytest -q && uv run ruff check . && uv run mypy src

# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

After P11 lands, the F3 frontend half (Position detail page = Overview +
Meta + Plan + Trades-placeholder) is fully unblocked on the backend side.
Next backend gate is **P12** (derived read layer), which aggregates Trade
rows across positions for dashboards.

## 10. Future-proofing notes (don't implement, just don't preclude)

- **Diff endpoint** (`GET /positions/{pid}/trade-plans/diff?from=1&to=2`).
  Computable client-side from `TradePlanRead` payloads; server endpoint
  is unnecessary until UI demand justifies it.
- **Cross-position "current plans" list** (e.g., for the F5 dashboard
  "all open forex positions and their current SL/TP"). Lands in P12 as a
  derived read; do not retrofit P11.
- **Soft-delete on revisions.** Declined in P11 (strict append-only).
  If audit needs ever emerge that demand "this revision was wrong, do
  not display", the cleanest path is a separate `hidden` flag column,
  not retrofitting DELETE semantics. Append-only stays sacred.
- **revision_no compaction / renumbering.** Never. The sequence is the
  history; gaps don't happen because there is no DELETE.
- **Concurrency hardening.** Single-user MVP makes the unique-constraint
  retry path essentially unreachable. If P11 ever sees multi-user
  scenarios (broker import jobs writing concurrently?), a `SERIALIZABLE`
  transaction or row-level lock on the parent Position would replace
  the retry-once strategy.
- **Validation hooks** (e.g., long-vs-short directional sanity for
  entry/SL/TP) — could be added as a `services/trade_plans.py` helper
  invoked from POST. Out of scope here because direction is not
  encoded on Position.

---

## Changelog

- **v0.1 (2026-05-26)** — Initial P11 build plan. Settled three P11
  sub-decisions with the user: (1) server-allocated `revision_no` via
  `MAX+1` per position (clients do not supply); (2) **strictly
  append-only** — no PATCH, no DELETE endpoint; revisions are permanent,
  corrections happen by appending; (3) GET list ordered oldest-first
  (revision 1 → N) for event-stream reading order. By-precedent choices:
  nested sub-resource URLs `/positions/{pid}/trade-plans/...`,
  closed-position is NOT a lock (mirrors P10), no `strategy_type`
  restriction (data-model §5.5 says "primarily forex" but does not
  restrict), owner-scoped via Position with cross-user 404. Three
  sub-phases: P11.1 schemas + service helper (one function:
  `allocate_next_revision_no`), P11.2 router + four endpoints
  (POST + GET list + GET current + GET by revision_no), P11.3
  regression + codegen + brief. No new migration — table exists since
  `0001_initial_schema` with the `UNIQUE (position_id, revision_no)`
  constraint that the allocator relies on. `services/trade_plans.py`
  joins `services/positions.py` / `services/trades.py` /
  `services/strategy_meta.py`. P11 carries no amendment to macro §6 —
  sub-decisions are P11-internal.
