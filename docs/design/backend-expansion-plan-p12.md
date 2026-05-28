# Backend Phase P12 — Derived read layer (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p12.zh.md)

> Status: **DONE v0.2** (2026-05-28) — shipped on `refactoring/rebuild` (commit
> `6af39f0`, 406 backend tests passing, `ruff` + `mypy --strict` clean). Detailed
> build plan for **P12** from the macro roadmap
> [backend-expansion-plan.md](./backend-expansion-plan.md).
> Self-contained — an implementer can execute it directly. Companions:
> [v1-release-plan.md](./v1-release-plan.md) (V1 cut + cross-cutting decisions),
> [data-model.md §4.4 / §6](./data-model.md#44-position-universal-strategy-instance)
> (currency placement, "derived — not stored" partition), and the
> P8/P9 service-layer modules
> ([services/positions.py](../../backend/src/trading_journal/services/positions.py),
> [services/trades.py](../../backend/src/trading_journal/services/trades.py))
> that P12 extends.

## 1. Purpose & context

Turn the existing stored data (`Position.pnl_realized` frozen on close +
`Trade.cash_flow` per atomic fill, computed in P9) into the **read-time
aggregations** that make a journal useful:

- **Per-position `net_cash_flow`** on `GET /positions` and `GET /positions/{id}`
  — `SUM(trade.cash_flow)` per position, always present, lets the UI surface a
  meaningful running number for open positions (e.g. for Wheel / PMCC the
  effective cost basis per share that informs covered-call strike selection).
- **`GET /dashboard/summary`** — a single owner-scoped endpoint returning the
  data F5's dashboard needs: per-currency realized P/L for closed positions,
  per-currency net cash flow snapshot for open positions, win rate, monthly
  realized P/L buckets, and counts.

P12 is **pure Pydantic + service-layer SQL + router + tests**. **No DB
migration** — every value is derived, not stored. P12 adds one new field to
existing schemas and one new endpoint family; the wire-compatibility footprint
is small but the test surface is non-trivial (cross-user isolation, currency
splits, archived-trade exclusion, win-rate corner cases, month bucketing).

P12 unblocks **F5** (dashboards) and informs **F3** (Position list / detail
pages display `net_cash_flow` to drive trading decisions). F3/F4 do not
strictly require P12 — single-position `net_cash_flow` could be computed
in the frontend — but having it on the backend list response avoids N+1
trade fetches when N positions exist.

### Settled decisions (do not re-derive)

Five sub-decisions agreed with the user on 2026-05-27, plus by-precedent
choices inherited from P8/P9:

- **Two separate semantic fields, not one.** `Position.pnl_realized`
  (stored, frozen on close, NULL while open) is kept untouched — it
  represents *"realized P/L of a fully closed position."* The new derived
  field `net_cash_flow` (always-present API field, never stored) represents
  *"net cash flow into/out of this position to date"*. On a closed
  position they are mathematically equal; semantically they answer
  different questions. The frontend chooses which to display based on
  status; the backend simply exposes both.
- **`net_cash_flow` is API-only, derived at request time, not stored.**
  No new column on `positions`. No migration. Computed via
  `SUM(trade.cash_flow) GROUP BY position_id` with `Trade.archived_at IS
  NULL` to exclude soft-deleted trades.
- **Always included in list / detail responses, no opt-in flag.** V1
  data volumes are tiny; the SUM-GROUP-BY is cheap and a query-string
  flag would only add a coupling burden to every frontend call site.
- **Dashboard path prefix `/dashboard/*`.** Direct UI-coupled name beats
  premature genericization (`/stats/*`). The endpoint family currently
  has exactly one consumer (F5 dashboard); if a second view ever needs
  the same aggregates we can revisit.
- **V1 dashboard is a single `GET /dashboard/summary` endpoint.** Returns
  closed-position aggregates + open-position snapshot in one payload.
  Splitting into `/per-currency`, `/monthly-pnl`, `/win-rate`, `/counts`
  is V1.x material if a future view needs partial fetches.
- **One P12 detail plan, two sub-phases.** P12.1 = list/detail
  `net_cash_flow`; P12.2 = dashboard summary. Sub-phases share the
  `SUM(trade.cash_flow)` helper, so executing in one pass is more
  efficient than splitting.

By-precedent choices (inherited from earlier phases — confirmed but not
re-debated):

- **Owner-scoped throughout.** Dashboard queries filter
  `position.user_id == current_user.id`; cross-user data is invisible.
  Per-position derived fields piggyback on existing P8 owner-scoping in
  `api/positions.py`.
- **Archived trades excluded from aggregates.** Both `net_cash_flow` and
  the dashboard rollups WHERE `trades.archived_at IS NULL`. Mirrors P9's
  audit-friendly soft-delete contract: archived rows survive but stop
  contributing to live numbers.
- **No new migration.** Confirmed — every value is derived from
  existing tables.
- **Currency aggregation is per-position-currency-only.** No FX
  conversion. Matches [data-model.md §6](./data-model.md#currency-placement)
  ("portfolio reports aggregate per-currency, not into a single converted
  total") and the V1 release plan's V1.x-deferred FX work.
- **Win rate denominator excludes positions with `pnl_realized = 0`?**
  **No** — include them, count toward "loss" side (i.e., win rate =
  `count(pnl_realized > 0) / count(*)` over closed). Breakeven is a
  rounding curiosity, not worth a third category in V1; if it matters
  later, the frontend can compute breakeven from `pnl_realized` it already
  has.
- **Empty data corner cases.** No closed positions → `win_rate` is
  `null` (JSON), counts are 0, per-currency arrays are empty. No open
  positions → open block's per-currency arrays are empty and count is 0.
  Avoid throwing.

## 2. Scope

### In scope (this plan)

- `schemas/position.py` — add `net_cash_flow: Decimal` to `PositionRead`.
- `services/positions.py` — add `compute_net_cash_flows(session, position_ids)`
  helper. Single SQL, batched, returns mapping.
- `api/positions.py` — `GET /positions` and `GET /positions/{id}` both
  populate `net_cash_flow` in responses. List endpoint batches via the
  helper to avoid N+1.
- `schemas/dashboard.py` — `DashboardSummary` response model (nested
  `open` + `closed` blocks with the field shapes in §4).
- `services/dashboard.py` — `compute_summary(session, user)`. One or
  two SQL aggregations + Python regrouping for the response shape.
- `api/dashboard.py` — single endpoint `GET /dashboard/summary`.
- Wire dashboard router in `main.py` (final URL prefix
  `/api/dashboard/summary`).
- Tests:
  - `tests/test_positions.py` — extend existing tests for the
    `net_cash_flow` field on list/detail responses (happy / archived
    trades / multi-trade sum / consistency with closed `pnl_realized` /
    zero on empty position).
  - `tests/test_dashboard.py` — new file, full owner-scoped + currency
    + bucket coverage.
- After backend is green: regenerate `frontend/src/api/schema.d.ts` +
  commit.

### NOT in scope

- **No DB migration.** All values are derived.
- **No `pnl_realized` write changes.** P8's freeze-on-close semantics
  stand untouched; this plan only reads.
- **No `days_open` / `roi_on_capital` / `result` backend endpoints.**
  These remain frontend-computed per V1 release plan Decision 5. Detail
  page fetches the position's trades for the Trades tab and computes
  these from Position fields + `net_cash_flow`.
- **No `pnl_unrealized` / `pnl_total` (mark-to-market).** V1.x — needs
  a market quote source not in V1.
- **No FX conversion.** V1.x — needs `FxRate` table.
- **No `/per-currency` / `/monthly-pnl` / `/win-rate` / `/counts`
  granular endpoints.** Subsume in the single summary endpoint. Split
  only if a future consumer needs partial reads.
- **No date-range filtering on the summary** (e.g.,
  `?from=2026-01-01`). Always returns "all time". Add later if F5 grows
  a time-range picker.
- **No strategy-type filtering on the summary.** Always returns all
  strategies. F5 may surface drill-downs in V1.x.
- **No caching layer.** Recompute on every request — V1 data volumes
  make caching premature; correctness > latency.
- **Frontend F3/F5 implementation.** Separate phases.

## 3. Files

```
backend/src/trading_journal/
├── schemas/position.py             ← CHANGED: add net_cash_flow to PositionRead
├── schemas/dashboard.py            ← NEW
├── services/positions.py           ← CHANGED: add compute_net_cash_flows helper
├── services/dashboard.py           ← NEW
├── api/positions.py                ← CHANGED: populate net_cash_flow in list/detail
├── api/dashboard.py                ← NEW
└── main.py                         ← CHANGED: include dashboard.router
backend/tests/
├── test_positions.py               ← CHANGED: add net_cash_flow coverage
└── test_dashboard.py               ← NEW
frontend/src/api/schema.d.ts        ← REGENERATED at end
```

Module naming follows precedent: schemas singular (`position`, `dashboard`);
services / api plural (`positions`, `dashboard` — kept singular here because
"dashboard" is conceptually a single surface, not a collection).

## 4. Schema shapes (target)

### 4.1 `PositionRead` — added field

Existing P8 schema gains one always-present derived field. No existing field
changes.

```python
class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # ... all existing P8 fields unchanged ...
    pnl_realized: Decimal | None  # existing: NULL while open, frozen on close

    # NEW in P12 — always populated by the API layer (never None).
    # For open positions: SUM(trade.cash_flow) over non-archived trades.
    # For closed positions: equals pnl_realized (mathematically identical).
    net_cash_flow: Decimal
```

`net_cash_flow` is **never `None`** — a position with no trades returns
`Decimal("0.0000")`.

> **API ergonomic note.** `net_cash_flow` is populated by the router (via the
> service helper) before returning the Pydantic model, not by SQLAlchemy
> ORM-side default. The simplest pattern is to keep the ORM model unchanged,
> compute the mapping in the router, and pass `net_cash_flow` explicitly when
> constructing `PositionRead` (Pydantic v2's `model_validate(obj,
> from_attributes=True)` followed by `.model_copy(update={"net_cash_flow":
> ...})`, or a small helper).

### 4.2 `DashboardSummary` — response shape

```python
class CurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    currency: str  # ISO 4217, uppercase
    amount: Decimal  # numeric(18, 4) precision


class MonthCurrencyAmount(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    month: str  # "YYYY-MM" — UTC month bucket from closed_at
    currency: str
    amount: Decimal


class ClosedSummary(BaseModel):
    count: int
    win_rate: Decimal | None  # null when count == 0; else fraction in [0, 1]
    per_currency_pnl: list[CurrencyAmount]
    monthly_pnl: list[MonthCurrencyAmount]


class OpenSummary(BaseModel):
    count: int
    per_currency_net_cash_flow: list[CurrencyAmount]


class DashboardSummary(BaseModel):
    closed: ClosedSummary
    open: OpenSummary
```

**Notes on shapes.**

- Flat `list[CurrencyAmount]` and `list[MonthCurrencyAmount]` rather than
  nested dicts. ECharts (F5's chart lib) consumes flat tuples cleanly;
  nested-dict shapes would force frontend flattening anyway.
- `month` is a string `"YYYY-MM"` (ISO month identifier), not a date —
  the bucket is the abstraction, not a real day. Bucketed by UTC.
- Per-currency arrays sorted by currency alphabetical (stable rendering).
- Monthly array sorted by `(month ASC, currency ASC)`.
- `win_rate` is `Decimal | None`. Six-digit precision is overkill for a
  ratio, but `Decimal` matches every other money field in the API.
  Frontend formats as `%`.

## 5. Service-layer surfaces

### 5.1 `services/positions.py` — addition

```python
import uuid
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.trade import Trade


async def compute_net_cash_flows(
    session: AsyncSession,
    position_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, Decimal]:
    """Return {position_id: SUM(trade.cash_flow)} for the given positions,
    excluding archived trades. Positions with no non-archived trades are
    NOT in the returned dict — callers should default missing entries to
    Decimal("0.0000").

    Single SQL query: SELECT position_id, SUM(cash_flow) FROM trades
    WHERE position_id IN (...) AND archived_at IS NULL GROUP BY position_id.

    Caller is responsible for materialising the iterable into a list/set
    before passing — the function does not iterate twice. An empty input
    returns {} without hitting the DB.
    """
    ids = list(position_ids)
    if not ids:
        return {}

    stmt = (
        select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
        .where(Trade.position_id.in_(ids), Trade.archived_at.is_(None))
        .group_by(Trade.position_id)
    )
    rows = (await session.execute(stmt)).all()
    return {row.position_id: row.total for row in rows}
```

A single batched function covers both the list endpoint (`compute_net_cash_flows(session,
[p.id for p in positions])`) and the detail endpoint
(`compute_net_cash_flows(session, [position.id])`).

### 5.2 `services/dashboard.py` — full surface

```python
import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.position import Position, PositionStatus
from trading_journal.models.trade import Trade
from trading_journal.schemas.dashboard import (
    ClosedSummary,
    CurrencyAmount,
    DashboardSummary,
    MonthCurrencyAmount,
    OpenSummary,
)


async def compute_summary(
    session: AsyncSession, user_id: uuid.UUID
) -> DashboardSummary:
    """Return the V1 dashboard summary for a given user.

    All queries scope by `Position.user_id == user_id`. Archived trades
    are excluded from open-side net_cash_flow rollups (closed-side uses
    Position.pnl_realized directly, which was already computed with the
    correct trade set frozen at close).
    """
    # closed: count + win_rate + per_currency_pnl + monthly_pnl
    closed_stmt = (
        select(
            Position.currency,
            Position.pnl_realized,
            Position.closed_at,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.CLOSED,
        )
    )
    closed_rows = (await session.execute(closed_stmt)).all()

    closed_count = len(closed_rows)
    wins = sum(1 for r in closed_rows if (r.pnl_realized or 0) > 0)
    win_rate = (
        Decimal(wins) / Decimal(closed_count) if closed_count > 0 else None
    )

    per_currency_pnl: dict[str, Decimal] = {}
    monthly_pnl: dict[tuple[str, str], Decimal] = {}
    for r in closed_rows:
        amt = r.pnl_realized or Decimal("0")
        per_currency_pnl[r.currency] = per_currency_pnl.get(r.currency, Decimal("0")) + amt
        month_key = r.closed_at.strftime("%Y-%m")  # UTC; closed_at is timestamptz
        monthly_pnl[(month_key, r.currency)] = (
            monthly_pnl.get((month_key, r.currency), Decimal("0")) + amt
        )

    # open: count + per_currency_net_cash_flow
    open_stmt = (
        select(
            Position.id,
            Position.currency,
        )
        .where(
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
        )
    )
    open_rows = (await session.execute(open_stmt)).all()
    open_count = len(open_rows)
    open_position_ids = [r.id for r in open_rows]
    currency_by_position = {r.id: r.currency for r in open_rows}

    # batch SUM(cash_flow) for all open positions in one query
    open_ncf_map: dict[uuid.UUID, Decimal] = {}
    if open_position_ids:
        ncf_stmt = (
            select(Trade.position_id, func.sum(Trade.cash_flow).label("total"))
            .where(
                Trade.position_id.in_(open_position_ids),
                Trade.archived_at.is_(None),
            )
            .group_by(Trade.position_id)
        )
        open_ncf_map = {
            row.position_id: row.total
            for row in (await session.execute(ncf_stmt)).all()
        }

    open_per_currency: dict[str, Decimal] = {}
    for pid, currency in currency_by_position.items():
        amt = open_ncf_map.get(pid, Decimal("0"))
        open_per_currency[currency] = open_per_currency.get(currency, Decimal("0")) + amt

    return DashboardSummary(
        closed=ClosedSummary(
            count=closed_count,
            win_rate=win_rate,
            per_currency_pnl=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(per_currency_pnl.items())
            ],
            monthly_pnl=[
                MonthCurrencyAmount(month=m, currency=c, amount=a)
                for (m, c), a in sorted(monthly_pnl.items())
            ],
        ),
        open=OpenSummary(
            count=open_count,
            per_currency_net_cash_flow=[
                CurrencyAmount(currency=c, amount=a)
                for c, a in sorted(open_per_currency.items())
            ],
        ),
    )
```

A single function. Closed-side aggregation runs in Python over already-fetched
rows; open-side runs one batched SQL aggregate. Both are O(N) where N is the
user's position count — fine for V1 single-user with at most a few hundred
positions. If scale ever matters, the closed-side regrouping can be pushed
into SQL (`SUM ... GROUP BY currency, strftime('%Y-%m', closed_at)`).

> **SQLite vs Postgres caveat.** `closed_at.strftime("%Y-%m")` happens in
> Python after the row is fetched, so it works identically on both
> backends. If we later move to a SQL-side `GROUP BY` on month, **use
> `func.strftime("%Y-%m", Position.closed_at)` on SQLite** vs
> **`func.to_char(Position.closed_at, "YYYY-MM")` on Postgres** — they
> diverge. The Python approach is portable; keep it for V1.

## 6. Phased plan

Two sub-phases. After each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src`. **Baseline post-P11:** 347 tests passing.

### P12.1 — Position responses gain `net_cash_flow`

**Goal.** `GET /positions` and `GET /positions/{id}` always include
`net_cash_flow`. Frontend (later F3) can render it on the list view and the
detail page Overview tab.

**Tasks.**

1. `schemas/position.py` — add `net_cash_flow: Decimal` to `PositionRead`.
2. `services/positions.py` — add `compute_net_cash_flows` helper (§5.1).
3. `api/positions.py` —
   - In `list_positions`: after fetching positions, call
     `compute_net_cash_flows(session, [p.id for p in positions])` once;
     then construct each `PositionRead` with `net_cash_flow` from the map
     (default `Decimal("0")` for missing entries).
   - In `get_position`: call `compute_net_cash_flows(session, [position.id])`;
     construct `PositionRead` with `net_cash_flow`.
4. Service-layer unit tests in `tests/test_positions.py`
   (extend the existing module):
   - `test_net_cash_flow_zero_when_no_trades` — newly-created position
     has `net_cash_flow == Decimal("0")` in list + detail responses.
   - `test_net_cash_flow_sums_non_archived_trades` — insert 3 trades
     summing to known value; assert match in both list + detail.
   - `test_net_cash_flow_excludes_archived_trades` — soft-delete one
     trade via P9's `DELETE /trades/{id}`; assert the sum drops by that
     trade's cash_flow.
   - `test_net_cash_flow_isolated_per_position` — two positions for the
     same user, trades on each; sums don't bleed across.
   - `test_net_cash_flow_closed_matches_pnl_realized` — close a position
     (PATCH `status=closed`); assert `net_cash_flow == pnl_realized` in
     the response.
   - `test_net_cash_flow_list_endpoint_does_one_query_per_request` —
     load 5 positions each with 3 trades; assert one batched
     SUM-GROUP-BY query, not 5 (use SQLAlchemy event listener / query
     counter in the test fixture).
5. Confirm cross-user isolation still 404s for non-owned positions
   (covered by existing P8 tests; no new ones needed unless the change
   alters behavior).

**Acceptance.** All P8 tests pass with the new field present. New tests
green. Codegen will be re-run at the end of P12.

### P12.2 — `GET /dashboard/summary`

**Goal.** Single owner-scoped endpoint returning the V1 dashboard payload.

**Tasks.**

1. `schemas/dashboard.py` — `CurrencyAmount`, `MonthCurrencyAmount`,
   `ClosedSummary`, `OpenSummary`, `DashboardSummary` (§4.2).
2. `services/dashboard.py` — `compute_summary(session, user_id)` (§5.2).
3. `api/dashboard.py` — single endpoint
   `GET /api/dashboard/summary`, depends on `current_active_user` and
   `get_session`, calls `compute_summary(session, user.id)`, returns
   `DashboardSummary`.
4. Wire `dashboard.router` in `main.py` under `/api`.
5. `tests/test_dashboard.py`:
   - **Empty user (no positions):** all counts 0, win_rate `null`, both
     per-currency arrays empty, monthly array empty.
   - **Only open positions, single currency:** closed block empty,
     open block populated with one currency, count matches.
   - **Only closed positions, single currency:**
     `per_currency_pnl` has one row, `monthly_pnl` rows match
     closed_at months, `win_rate` correctly computed.
   - **Mixed open + closed across two currencies (USD + EUR):**
     - closed.per_currency_pnl has two entries, sorted alphabetically
     - open.per_currency_net_cash_flow has two entries, sorted
     - monthly_pnl rows are per-(month, currency) and sorted ascending
   - **Win rate edge cases:**
     - all closed are wins → `win_rate == Decimal("1.0")`
     - all closed are losses → `Decimal("0")`
     - `pnl_realized == 0` counts as loss → not win
     - no closed positions → `win_rate is None`
   - **Archived trades excluded from open snapshot:** insert open
     position with 2 trades, soft-delete one; the remaining
     `net_cash_flow` reflects only the un-archived trade. (Closed
     side uses `pnl_realized` which is frozen at close before any
     subsequent archive could happen — but archiving a closed
     position's trade should NOT change `pnl_realized` either; verify
     P8/P9 behavior is unchanged.)
   - **Cross-user isolation:** user A's positions invisible to user B
     in user B's dashboard response.
   - **Authentication:** unauthenticated `GET /api/dashboard/summary`
     → 401.
   - **Monthly bucketing UTC:** position with `closed_at`
     "2026-04-30 23:30:00 UTC" buckets to "2026-04", not "2026-05"
     (sanity check that no local-tz drift is happening).

**Acceptance.** Backend test suite green; `ruff` + `mypy --strict` clean;
manual curl walkthrough (§7) succeeds.

### Codegen — at end of P12.2

After P12.2 ships and tests pass:

```bash
cd backend && uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run codegen
git diff --exit-code src/api/schema.d.ts  # expected: diff present (Position +
                                          # DashboardSummary)
git add frontend/src/api/schema.d.ts
```

Commit the regenerated `schema.d.ts` alongside the backend changes.

## 7. Manual verification (curl recipe)

After P12.2 ships, against a logged-in cookie jar:

```bash
BASE=http://localhost:8000
JAR=cookies.txt  # from prior login

# 1. List positions — every row has net_cash_flow
curl -fsSi "$BASE/api/positions" -b "$JAR" | jq '.[0].net_cash_flow'
# Expected: a Decimal string like "12.5000" (or "0" for no-trade positions)

# 2. Detail — same field present
curl -fsSi "$BASE/api/positions/<pid>" -b "$JAR" | jq '.net_cash_flow'

# 3. Dashboard summary
curl -fsSi "$BASE/api/dashboard/summary" -b "$JAR"
# Expected: 200, body matches DashboardSummary schema

# 4. Unauthenticated dashboard
curl -i "$BASE/api/dashboard/summary"
# Expected: 401
```

## 8. After P12

- **F3** Position UI consumes `net_cash_flow` on list rows and detail
  Overview. List column header is **"Net Cash Flow"** for open / **"Realized
  P/L"** for closed (mutually exclusive labels — same column slot, different
  value source).
- **F4** Trade entry doesn't depend on P12.
- **F5** Dashboard consumes `GET /dashboard/summary` directly; the
  monthly-PnL chart sources from `closed.monthly_pnl`.
- **PX** External integrations remain opportunistic.

V1.x extensions, if/when needed:

- Per-strategy drill-down (`GET /dashboard/summary?strategy_type=wheel`).
- Date-range filtering (`?from=2026-01-01`).
- Granular endpoints (`/per-currency`, `/monthly-pnl`, etc.) if a
  consumer needs partial fetches.
- `pnl_unrealized` / `pnl_total` once a market quote provider lands.
- FX-converted aggregates once `FxRate` table lands.

## 9. Risks & considered alternatives

- **N+1 risk on list endpoint.** Mitigation: batch SUM in one query via
  `compute_net_cash_flows`. Test in P12.1 verifies one query, not N.
- **Decimal vs float for `win_rate`.** Decimal chosen for consistency
  with every other money/ratio field. Six-digit precision is overkill
  but cheap; the frontend formats as `%`.
- **Month bucketing in Python vs SQL.** Python chosen for SQLite /
  Postgres portability (see §5.2 caveat). If V1 ever has thousands of
  closed positions per user, push down to SQL — but the breakeven point
  is well above V1 scale.
- **Always-on `net_cash_flow` on list vs. opt-in flag.** Always-on
  chosen — opt-in adds a coupling burden to every frontend caller and
  the cost is small. Revisit at V1.x if list latency becomes an issue.
- **Single endpoint vs. multiple granular endpoints.** Single chosen —
  V1's dashboard is one page, one fetch. Frontend over-fetching of
  unused fields is small (< 10 KB).
- **What if Trade modification semantics change post-V1** (e.g.,
  edit-in-place instead of soft-delete-and-reinsert)? `net_cash_flow`
  would automatically reflect new values, but `pnl_realized` frozen on
  close could diverge. Out of scope here; flagged in
  [data-model.md §7](./data-model.md#open-design-questions-still-need-a-decision-before-implementation).

---

## Changelog

- **v0.2 (2026-05-28)** — Shipped on `refactoring/rebuild` (commit `6af39f0`).
  P12.1 + P12.2 both delivered as planned; **18 new tests** in
  `tests/test_dashboard.py` (13) + `tests/test_positions.py` (5 added);
  total suite **406 passing** (up from 347 post-P11). No deviations from
  the v0.1 plan: schemas, services, routers, and codegen all match the
  spec. `frontend/src/api/schema.d.ts` regenerated and committed. Status
  flipped from DRAFT → DONE.
- **v0.1 (2026-05-27)** — Initial P12 detailed plan. Five sub-decisions
  settled: (1) two separate fields (`pnl_realized` frozen-on-close vs
  derived `net_cash_flow`); (2) `net_cash_flow` is API-only, never
  stored; (3) always present in list/detail (no opt-in flag);
  (4) `/dashboard/*` path prefix; (5) single
  `GET /dashboard/summary` endpoint. Two sub-phases: P12.1 (Position
  responses gain field), P12.2 (dashboard endpoint).
