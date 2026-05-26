# Backend Phase P10 — Strategy-meta extensions (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p10.zh.md)

> Status: **DRAFT v0.1** (2026-05-26). Detailed build plan for **P10** from
> the macro roadmap [backend-expansion-plan.md](./backend-expansion-plan.md).
> Self-contained — an implementer can execute it directly. Companions:
> [data-model.md §4.8](./data-model.md#48-strategy-specific-extensions)
> (WheelCycleMeta + PmccCycleMeta field definitions and the "no
> IcPositionMeta" rationale), the just-drafted
> [backend-expansion-plan-p9.md](./backend-expansion-plan-p9.md), the
> just-shipped [backend-expansion-plan-p8.md](./backend-expansion-plan-p8.md)
> (Position CRUD + `services/positions.py` seam), and the
> settled-decision summary in
> [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions).

## 1. Purpose & context

Turn the already-migrated `wheel_cycle_metas` and `pmcc_cycle_metas` tables
into typed CRUD APIs: per-strategy 1:1 extensions of Position that carry
configuration/snapshot data the generic `Position` row cannot model
(WheelCycleMeta = funding/loan/interest, PmccCycleMeta = the specific LEAP
OptionContract). Strategies whose snapshots are generic (IC's
`max_risk_at_open`) use `Position` directly and need no extension —
data-model §4.8 explains why `IcPositionMeta` does not exist.

P10 is **pure Pydantic + router + service + tests + a small cross-table
validation guard for PMCC**. No DB migration — both tables exist since Phase
2's `0001_initial_schema`. The work shape is closer to P8 (single-row
CRUD) than to P9 (multi-row + cash_flow), with one specifically interesting
piece: PMCC requires the linked LEAP `Instrument` to be an `option` *and*
its underlying must match the parent Position's `primary_instrument_id`.

P10 unblocks two of the three tabs on F3's Position detail page (Meta tab
for wheel + Meta tab for PMCC).

### Settled decisions (do not re-derive)

Four sub-decisions agreed with the user on 2026-05-26 while drafting this
plan, plus by-precedent choices inherited from P7/P8/P9:

- **Nested sub-resource URLs.** `GET / POST / PATCH / DELETE
  /positions/{pid}/wheel-meta` and `.../pmcc-meta`. The 1:1 relationship
  with Position is fully expressed by the URL — no listing endpoint, no
  `position_id` in the request body, no `?position_id=` query param. (This
  is a deliberate departure from the flat `/accounts`, `/positions`,
  `/trades` style used elsewhere: those are independent collections; meta
  is not.)
- **Strict `strategy_type` matching.** `WheelCycleMeta` may only attach to
  a Position whose `strategy_type == wheel`; `PmccCycleMeta` only to
  `strategy_type == pmcc`. Mismatch on POST or first-write → **422**. The
  check happens server-side after resolving the Position; clients are not
  trusted to enforce it.
- **PMCC LEAP triple-validation.** `leap_instrument_id` on `PmccCycleMeta`
  must satisfy three conditions, all checked at write time:
  1. The Instrument row exists → else **422** `"leap instrument not found"`.
  2. `instrument.kind == option` → else **422**
     `"leap_instrument_id must reference an option instrument"`.
  3. The corresponding `OptionContract.underlying_instrument_id` equals
     `position.primary_instrument_id` → else **422**
     `"leap option's underlying does not match position's primary instrument"`.
  The third check is the most useful — it catches "wrong-ticker LEAP"
  selection errors that would otherwise silently produce a broken PMCC
  position.
- **Closed-position is NOT a lock for meta.** Unlike P9 (Trade
  POST/PATCH/DELETE all 409 when Position is closed) and unlike P8
  (status `closed → open` rejected), meta writes are **allowed regardless
  of the parent Position's status**. Rationale: meta carries configuration
  / snapshot data (interest accrued, LEAP pointer), not financial events.
  A user often wants to record accrued interest on a wheel position
  *after* closing it; a misselected LEAP pointer should be amendable
  retroactively. `pnl_realized` is not derived from meta, so changing meta
  doesn't risk staleness.
- **POST = create-only, 409 if a row already exists.** Because
  `position_id` is the meta table's primary key, at most one row exists
  per Position. POST does not upsert: a second POST → 409
  `"meta already exists for this position; use PATCH"`. PATCH is the
  amend path. DELETE is hard delete (no soft-delete column on these
  tables, and meta has no audit value compared to Trade).
- **Owner-scoped via Position.** Meta has no direct `user_id`; ownership
  flows through `position.user_id`. Every endpoint resolves the Position
  first; cross-user `position_id` → **404** (matching P6/P7/P8/P9).
- **Format-only field validation in P10.** Pydantic enforces positivity
  on `loan_amount` / `interest_rate_apr` / `interest_accrued` (`ge=0`;
  zero is meaningful — a cash-funded cycle has `loan_amount=0`). No
  cross-field business validation (e.g., "if `funding_source=cash` then
  `loan_amount` must be null") — the user picks. Matches the P8
  "format-only" philosophy.
- **No new migration.** Tables exist since `0001_initial_schema`.
- **No `created_at` / `updated_at` on meta.** The existing ORM doesn't
  carry them; P10 doesn't add them. Audit history isn't a meta concern.

## 2. Scope

### In scope (this plan)

- `schemas/strategy_meta.py` — two schema groups in one module:
  `WheelMetaCreate` / `WheelMetaUpdate` / `WheelMetaRead`,
  `PmccMetaCreate` / `PmccMetaUpdate` / `PmccMetaRead`.
- `services/strategy_meta.py` — cross-table validation helpers:
  `validate_strategy_type_match()`, `validate_leap_instrument()`. Routers
  call into them; tests cover both layers.
- `api/strategy_meta.py` — one router exposing eight endpoints under
  `/positions/{pid}/wheel-meta` (×4) and `/positions/{pid}/pmcc-meta` (×4).
- Wire under `/positions` in `main.py` — the meta router mounts as a
  sibling so its prefix begins with `/positions/{position_id}/...`.
  (Final URLs: `/api/positions/{pid}/wheel-meta` etc.)
- `tests/test_strategy_meta.py`.
- After backend is green: regenerate `frontend/src/api/schema.d.ts`
  (`npm run codegen`) + commit.

### NOT in scope

- **No new meta types.** IC stays without a meta table (data-model §4.8
  rationale: only `max_risk_at_open`, already on `Position`). Future
  spot-stock or spot-forex meta tables are not anticipated for MVP.
- **No cross-field business validation** on wheel funding (e.g., margin
  ⇒ loan_amount required). Format-only.
- **No `interest_accrued` recompute / daily-accrual job.** Per
  data-model §4.8: "manually entered total for MVP; future modeling
  discussed in §7". P10 stores what the user types.
- **No PATCH of `leap_instrument_id` cascade to anything.** Changing
  the LEAP pointer is just a row update; it does not re-target trades,
  recompute anything, or alert the user that historical trades may now
  point to a different option than the meta claims.
- **No new migration.**
- Frontend F3 implementation.
- Aggregate / derived endpoints (P12).

## 3. Files

```
backend/src/trading_journal/
├── schemas/strategy_meta.py                ← NEW
├── services/strategy_meta.py               ← NEW
├── api/strategy_meta.py                    ← NEW
└── main.py                                 ← CHANGED: include strategy_meta.router
backend/tests/test_strategy_meta.py         ← NEW
frontend/src/api/schema.d.ts                ← REGENERATED at end
```

Both `schemas/` and `services/` already exist as packages; P10 just adds
one module each. The new `api/strategy_meta.py` is one file with a single
`APIRouter` instance — the two meta types share the router so the path
prefix can be `/positions/{position_id}`.

## 4. Schema shapes (target)

```python
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import FundingSource


# ─────────────────── WheelCycleMeta ───────────────────

class WheelMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)
    # NOT accepted: position_id (URL-bound), no other fields


class WheelMetaUpdate(BaseModel):
    """Partial update; all fields optional. Numeric fields stay `ge=0`."""
    model_config = ConfigDict(extra="forbid")

    funding_source: FundingSource | None = None
    loan_amount: Decimal | None = Field(default=None, ge=0)
    interest_rate_apr: Decimal | None = Field(default=None, ge=0)
    interest_accrued: Decimal | None = Field(default=None, ge=0)


class WheelMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    funding_source: FundingSource
    loan_amount: Decimal | None
    interest_rate_apr: Decimal | None
    interest_accrued: Decimal | None


# ─────────────────── PmccCycleMeta ───────────────────

class PmccMetaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID
    # NOT accepted: position_id (URL-bound)


class PmccMetaUpdate(BaseModel):
    """Partial update — leap_instrument_id is the only field."""
    model_config = ConfigDict(extra="forbid")

    leap_instrument_id: uuid.UUID | None = None


class PmccMetaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_id: uuid.UUID
    leap_instrument_id: uuid.UUID
```

**Notes on shapes.**

- `extra="forbid"` on every write schema. `position_id` cannot be supplied
  in body — the URL `/positions/{pid}/...` is the source of truth, and any
  client attempt → 422 `extra_forbidden`.
- `WheelMetaUpdate.funding_source` accepts `None` only in the Pydantic
  type sense (meaning "unset"); since the ORM column is `nullable=False`,
  the router rejects an explicit `null` value in the body
  (`null` reaches `funding_source: FundingSource | None = None` and looks
  like "unset" — same as omission). To clear funding_source the user
  cannot; they must DELETE + re-create. This matches the ORM constraint
  without inventing a phantom "set null" semantics.
- `PmccMetaUpdate.leap_instrument_id: ... = None` similarly — "unset",
  not "set to null". The ORM column is non-null.
- No `created_at` / `updated_at` on `*Read` — meta tables don't carry them.

## 5. Service-layer surface (`services/strategy_meta.py`)

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, StrategyType
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position


def validate_strategy_type_match(
    position: Position, expected: StrategyType
) -> None:
    """Raise ValueError if position.strategy_type != expected. Router maps to 422."""
    if position.strategy_type is not expected:
        raise ValueError(
            f"position.strategy_type is '{position.strategy_type.value}', "
            f"meta requires '{expected.value}'"
        )


async def validate_leap_instrument(
    session: AsyncSession,
    position: Position,
    leap_instrument_id: uuid.UUID,
) -> None:
    """Three checks (see §1 settled decisions). All failures raise
    ValueError with a specific message; router maps to 422."""
    instrument = await session.get(Instrument, leap_instrument_id)
    if instrument is None:
        raise ValueError("leap instrument not found")
    if instrument.kind is not InstrumentKind.OPTION:
        raise ValueError(
            "leap_instrument_id must reference an option instrument"
        )
    contract = await session.get(OptionContract, leap_instrument_id)
    if contract is None:
        # Defensive: kind==option without OptionContract row is data corruption.
        raise ValueError(
            f"instrument {leap_instrument_id} is kind=option but has no "
            "OptionContract row"
        )
    if contract.underlying_instrument_id != position.primary_instrument_id:
        raise ValueError(
            "leap option's underlying does not match position's primary instrument"
        )
```

Both helpers are pure functions taking already-resolved ORM rows (or
session + id); no HTTP-layer concerns leak in. Tests exercise them
directly with seeded fixtures.

## 6. Phased plan

Three sub-phases. After each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src` — baseline depends on whether P9 has landed yet. If
**P9 first then P10**: baseline ≈ 243. If P10 first (P9 still pending):
baseline = 183 (post-P8).

### P10.1 — Schemas + service helpers

**Goal.** Typed surfaces and validation helpers exist; no HTTP yet.

**Tasks.**

1. `schemas/strategy_meta.py` — the six classes above.
2. `services/strategy_meta.py` — `validate_strategy_type_match` and
   `validate_leap_instrument`.
3. Service-layer unit tests in `tests/test_strategy_meta.py`:
   - `test_validate_strategy_type_match_ok` — wheel position +
     `expected=wheel` → no raise.
   - `test_validate_strategy_type_match_mismatch_raises` — IC position
     + `expected=wheel` → raises.
   - `test_validate_leap_instrument_ok` — stock + matching LEAP option →
     no raise.
   - `test_validate_leap_instrument_unknown_raises` — random UUID.
   - `test_validate_leap_instrument_not_option_raises` — stock instrument
     id as LEAP.
   - `test_validate_leap_instrument_wrong_underlying_raises` — option on
     a different underlying than the position's primary_instrument.

**Acceptance.** Schemas import; service unit tests green; no API yet.

### P10.2 — Router + full CRUD

**Goal.** Eight endpoints live over HTTP, with correct ownership scoping
and cross-table validation.

**Tasks.**

1. `api/strategy_meta.py` — one `APIRouter` instance. Private helpers:

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

   async def _get_wheel_meta_or_404(
       session: AsyncSession, position_id: uuid.UUID
   ) -> WheelCycleMeta:
       meta = await session.get(WheelCycleMeta, position_id)
       if meta is None:
           raise HTTPException(404, "Wheel meta not found")
       return meta

   async def _get_pmcc_meta_or_404(
       session: AsyncSession, position_id: uuid.UUID
   ) -> PmccCycleMeta:
       meta = await session.get(PmccCycleMeta, position_id)
       if meta is None:
           raise HTTPException(404, "PMCC meta not found")
       return meta
   ```

2. **Endpoints — WheelCycleMeta.**

   | Method | Path | Behavior |
   |---|---|---|
   | `POST` | `/positions/{pid}/wheel-meta` | Resolve position. `validate_strategy_type_match(pos, StrategyType.WHEEL)`. Check no existing meta (else 409). Insert. Return 201 + `WheelMetaRead`. |
   | `GET` | `/positions/{pid}/wheel-meta` | Resolve position (owner). Return 200 + meta, or 404 if not created. |
   | `PATCH` | `/positions/{pid}/wheel-meta` | Resolve position + meta. `exclude_unset` partial apply (do not overwrite missing fields with None). Return 200. |
   | `DELETE` | `/positions/{pid}/wheel-meta` | Resolve position + meta. Hard delete. Return 204. |

3. **Endpoints — PmccCycleMeta.**

   | Method | Path | Behavior |
   |---|---|---|
   | `POST` | `/positions/{pid}/pmcc-meta` | Resolve position. `validate_strategy_type_match(pos, StrategyType.PMCC)`. `validate_leap_instrument(session, pos, payload.leap_instrument_id)`. Check no existing meta (else 409). Insert. Return 201. |
   | `GET` | `/positions/{pid}/pmcc-meta` | Resolve position. Return 200 + meta, or 404. |
   | `PATCH` | `/positions/{pid}/pmcc-meta` | Resolve position + meta. If `leap_instrument_id` is supplied in payload, re-run `validate_leap_instrument`. Apply. Return 200. |
   | `DELETE` | `/positions/{pid}/pmcc-meta` | Hard delete. Return 204. |

4. **Closed-position is intentionally NOT checked.** Settled in §1 —
   meta is not lifecycle-locked. Tests in §7 explicitly exercise
   "PATCH meta on a closed position → 200" to prevent regression.

5. **`main.py`** — register `strategy_meta.router`. The router itself
   sets `prefix="/positions"` so its routes look like
   `/positions/{position_id}/wheel-meta`, and `main.py`'s top-level
   API mount adds the `/api` prefix. Match the wiring style of the
   existing `positions.router`.

6. `tests/test_strategy_meta.py` — full matrix from §7.

**Acceptance.** All P10 tests green; full suite + ruff + mypy clean.
Expected additions: **~45 tests**.

### P10.3 — Regression + codegen + brief

**Goal.** Lock the baseline; propagate to frontend.

**Tasks.**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` — green.
2. Frontend codegen. Backend up on `:8000`, `cd frontend && npm run
   codegen` → expect six new schemas (`WheelMetaCreate/Update/Read` +
   `PmccMetaCreate/Update/Read`); `npm run build` passes; commit
   `schema.d.ts`.
3. Walk the §8 curl recipe end-to-end.
4. Leave `review-notes/p10_implementation_brief.md` (mirror prior briefs).

**Acceptance.** All green; recipe passes; brief filed.

## 7. Test matrix

`tests/test_strategy_meta.py`, reusing `auth_client`, `second_user_client`,
and the migrated tempfile fixture. Seed helper extended to optionally
create both a wheel-strategy Position and a PMCC-strategy Position +
required Instruments (stock + LEAP OptionContract on that stock + a
distractor option on a different stock).

### Service-layer tests (no HTTP)

| Test | Validates |
|---|---|
| `test_validate_strategy_type_match_ok` | wheel position + expected=wheel → no raise |
| `test_validate_strategy_type_match_mismatch_raises` | IC position + expected=wheel raises |
| `test_validate_leap_instrument_ok` | matching underlying → no raise |
| `test_validate_leap_instrument_unknown_raises` | random UUID |
| `test_validate_leap_instrument_not_option_raises` | stock instrument id |
| `test_validate_leap_instrument_wrong_underlying_raises` | option whose underlying ≠ position.primary_instrument |

### POST `/positions/{pid}/wheel-meta`

| Test | Validates |
|---|---|
| `test_create_wheel_meta_201_min_payload` | only `funding_source` → 201; nullable fields are null |
| `test_create_wheel_meta_with_all_fields` | round-trip every field |
| `test_create_wheel_meta_rejects_position_id_in_body_422` | URL-bound |
| `test_create_wheel_meta_rejects_unknown_field_422` | extra="forbid" |
| `test_create_wheel_meta_rejects_negative_loan_amount_422` | ge=0 |
| `test_create_wheel_meta_rejects_negative_interest_rate_422` | ge=0 |
| `test_create_wheel_meta_rejects_negative_interest_accrued_422` | ge=0 |
| `test_create_wheel_meta_allows_zero_loan_amount` | cash-funded cycle |
| `test_create_wheel_meta_rejects_bad_funding_source_422` | enum validation |
| `test_create_wheel_meta_rejects_missing_funding_source_422` | required |
| `test_create_wheel_meta_rejects_on_non_wheel_position_422` | strategy_type strict check |
| `test_create_wheel_meta_409_if_already_exists` | second POST |
| `test_create_wheel_meta_404_unknown_position` | random pid |
| `test_create_wheel_meta_404_cross_user` | other user's pid |

### GET `/positions/{pid}/wheel-meta`

| Test | Validates |
|---|---|
| `test_get_wheel_meta_200` | own row |
| `test_get_wheel_meta_404_when_not_created` | position exists but no meta yet |
| `test_get_wheel_meta_404_unknown_position` | random pid |
| `test_get_wheel_meta_404_cross_user` | other user → 404 (not 403) |

### PATCH `/positions/{pid}/wheel-meta`

| Test | Validates |
|---|---|
| `test_patch_wheel_meta_partial_update` | one field at a time |
| `test_patch_wheel_meta_multiple_fields` | combined |
| `test_patch_wheel_meta_unset_means_no_change` | exclude_unset honored — omitted fields keep prior values |
| `test_patch_wheel_meta_rejects_negative_value_422` | ge=0 still applies |
| `test_patch_wheel_meta_rejects_position_id_in_body_422` | URL-bound |
| `test_patch_wheel_meta_404_when_meta_not_created` | POST first |
| `test_patch_wheel_meta_404_cross_user` | |
| `test_patch_wheel_meta_allowed_on_closed_position` | closed-position is NOT locked (settled decision) |

### DELETE `/positions/{pid}/wheel-meta`

| Test | Validates |
|---|---|
| `test_delete_wheel_meta_204` | hard delete |
| `test_delete_wheel_meta_404_when_not_created` | idempotency floor: second DELETE → 404 |
| `test_delete_wheel_meta_404_cross_user` | |
| `test_delete_wheel_meta_allowed_on_closed_position` | settled decision |
| `test_delete_wheel_meta_does_not_affect_position` | parent Position survives |

### POST `/positions/{pid}/pmcc-meta`

| Test | Validates |
|---|---|
| `test_create_pmcc_meta_201` | matching LEAP → 201 |
| `test_create_pmcc_meta_rejects_on_non_pmcc_position_422` | strategy_type strict check |
| `test_create_pmcc_meta_rejects_unknown_leap_422` | LEAP triple-check (a) |
| `test_create_pmcc_meta_rejects_non_option_leap_422` | LEAP triple-check (b) (stock id) |
| `test_create_pmcc_meta_rejects_wrong_underlying_leap_422` | LEAP triple-check (c) |
| `test_create_pmcc_meta_409_if_already_exists` | |
| `test_create_pmcc_meta_404_cross_user` | |
| `test_create_pmcc_meta_rejects_position_id_in_body_422` | URL-bound |

### GET `/positions/{pid}/pmcc-meta`

| Test | Validates |
|---|---|
| `test_get_pmcc_meta_200` | own row |
| `test_get_pmcc_meta_404_when_not_created` | |
| `test_get_pmcc_meta_404_cross_user` | |

### PATCH `/positions/{pid}/pmcc-meta`

| Test | Validates |
|---|---|
| `test_patch_pmcc_meta_changes_leap` | retarget — succeeds when new LEAP passes triple-check |
| `test_patch_pmcc_meta_rejects_wrong_underlying_leap_422` | re-run validate_leap_instrument |
| `test_patch_pmcc_meta_rejects_non_option_leap_422` | |
| `test_patch_pmcc_meta_404_when_meta_not_created` | |
| `test_patch_pmcc_meta_allowed_on_closed_position` | settled decision |

### DELETE `/positions/{pid}/pmcc-meta`

| Test | Validates |
|---|---|
| `test_delete_pmcc_meta_204` | |
| `test_delete_pmcc_meta_404_when_not_created` | |
| `test_delete_pmcc_meta_allowed_on_closed_position` | settled decision |

### Auth

| Test | Validates |
|---|---|
| `test_requires_auth` | parametrized POST/GET/PATCH/DELETE for both meta types without cookie → 401 |

## 8. Manual verification reference (full P10 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# Register + login
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"carol@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=carol@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed account + AAPL stock instrument
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)
AAPL=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)

# A wheel position on AAPL
WHEEL_POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$AAPL\",\"strategy_type\":\"wheel\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 1) Create wheel meta — cash-funded, no loan/interest
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 2) PATCH — flip to margin and add loan/interest snapshot
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"funding_source":"margin","loan_amount":"10000","interest_rate_apr":"0.055"}'

# 3) Read back
curl -fsS "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" | jq

# 4) POST a SECOND wheel meta → 409
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 5) Close the position then PATCH meta → still 200 (closed-position is NOT locked)
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS" -b "$JAR" \
  -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-08-01T20:00:00Z"}'
curl -fsSi -X PATCH "$BASE/api/positions/$WHEEL_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"interest_accrued":"250.50"}'

# 6) PMCC track — seed a LEAP option on AAPL + a PMCC position
LEAP=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"kind\":\"option\",\"symbol\":\"AAPL\",\"currency\":\"USD\",\"option_contract\":{\"underlying_instrument_id\":\"$AAPL\",\"opt_type\":\"call\",\"strike\":\"150.00\",\"expiry\":\"2028-01-21\",\"multiplier\":100}}" | jq -r .id)
PMCC_POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$AAPL\",\"strategy_type\":\"pmcc\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 7) Create pmcc meta with the matching LEAP → 201
curl -fsSi -X POST "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$LEAP\"}"

# 8) Try to attach a wheel meta to the PMCC position → 422 (strategy mismatch)
curl -fsSi -X POST "$BASE/api/positions/$PMCC_POS/wheel-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d '{"funding_source":"cash"}'

# 9) Try to attach the LEAP to the WHEEL position's pmcc-meta → 422
#    (strategy mismatch wins before LEAP validation runs)
curl -fsSi -X POST "$BASE/api/positions/$WHEEL_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$LEAP\"}"

# 10) Try to PATCH the PMCC meta to a stock id as LEAP → 422
curl -fsSi -X PATCH "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR" \
  -H 'Content-Type: application/json' -d "{\"leap_instrument_id\":\"$AAPL\"}"

# 11) DELETE pmcc meta → 204; second DELETE → 404
curl -fsSi -X DELETE "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR"
curl -fsSi -X DELETE "$BASE/api/positions/$PMCC_POS/pmcc-meta" -b "$JAR"
```

## 9. Implementer quickstart

```bash
cd backend
# build P10.1 → P10.2 → P10.3; after each:
uv run pytest -q && uv run ruff check . && uv run mypy src

# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

After P10 lands, the next backend gate is **P11** (TradePlan event stream),
which together with P10 unblocks F3's full Position-detail page (Meta tab
for wheel/PMCC + Plan tab for forex).

## 10. Future-proofing notes (don't implement, just don't preclude)

- **IcPositionMeta (or any new meta type)** — adding one is purely
  additive: a new ORM model, a new alembic migration for the new table,
  and a new schema-group + endpoint-group inside `schemas/strategy_meta.py`
  / `api/strategy_meta.py`. No router-level pattern changes. Strategy-type
  matching enum will need a new branch.
- **Daily interest accrual job** — when broker API integration matures,
  a background job can call back into `services/strategy_meta.py` to
  bump `interest_accrued`. P10 leaves the column writable, so no schema
  change needed.
- **Cross-field business validation** (margin ⇒ loan_amount required,
  etc.) — adds cleanly as additional `services/strategy_meta.py`
  helpers without touching schemas.
- **`leap_instrument_id` change-detection** — if the user retargets the
  LEAP via PATCH, a future "trade-vs-meta consistency check" can flag
  historical trades on the now-orphaned previous LEAP. Lives in P12 /
  derived layer, not here.
- **Soft-delete on meta** — declined in P10 because meta carries no
  audit value. If audit needs emerge, the pattern from P9
  (`archived_at` + filter on list) lifts cleanly into a future
  migration.

---

## Changelog

- **v0.1 (2026-05-26)** — Initial P10 build plan. Settled four P10
  sub-decisions with the user: (1) nested sub-resource URLs
  `/positions/{pid}/wheel-meta` and `.../pmcc-meta`, no flat collection;
  (2) strict `strategy_type` match — WheelCycleMeta only on
  `strategy_type=wheel` positions, PmccCycleMeta only on `pmcc`;
  (3) LEAP triple-validation — exists + kind=option + underlying matches
  position.primary_instrument; (4) closed-position is NOT a lock for
  meta — PATCH/DELETE allowed regardless (meta is config/snapshot, not
  transactional). Three sub-phases: P10.1 schemas + service helpers,
  P10.2 router (eight endpoints) + tests, P10.3
  regression+codegen+brief. No new migration — both tables exist since
  `0001_initial_schema`. `services/strategy_meta.py` introduced
  alongside `services/positions.py` and (future) `services/trades.py`
  to keep cross-table validation helpers reusable. P10 carries no
  amendment to macro §6 — its sub-decisions are P10-internal.
