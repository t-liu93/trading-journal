# Backend Phase P9 — Trade CRUD (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p9.zh.md)

> Status: **DRAFT v0.1** (2026-05-26). Detailed build plan for **P9** from the
> macro roadmap [backend-expansion-plan.md](./backend-expansion-plan.md).
> Self-contained — an implementer can execute it directly. Companions:
> [data-model.md §4.5](./data-model.md#45-trade-atomic-event) (Trade fields +
> §4.5.2 Notion-event → atomic-Trade mapping), the just-shipped
> [backend-expansion-plan-p8.md](./backend-expansion-plan-p8.md) (Position
> CRUD + `services/positions.py` seam this plan extends), the **StrategyConfig
> template** (`api/strategy_configs.py` + `tests/test_strategy_configs.py`),
> and the settled-decision summary in
> [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions).

## 1. Purpose & context

Turn the already-migrated `trades` table into a typed CRUD API: the atomic
broker-level fill that is the user's daily data-entry surface. P9 is the
biggest single backend gate left — it unblocks F4 (Trade entry) and, by the
Trade-led Position model settled in P8, the inline-Position-create flow that
makes F3 honest. P9 also retroactively gives P8's `freeze_pnl_realized()`
real Trade rows to sum, closing the only validation gap that path had.

P9 ships one small DB migration (`Trade.archived_at`), a service module
(`services/trades.py`) holding the `cash_flow` formula and the action↔kind
guard, a router that accepts both single-row and multi-row submissions, and
a test suite mirroring §4.5.2's Notion-event vocabulary.

### Settled decisions (do not re-derive)

These extend [backend-expansion-plan.md §6](./backend-expansion-plan.md#6-design-decisions)
④ (Trade validation) with the P9-specific sub-decisions agreed
2026-05-26 with the user. Where this plan amends macro §6④, it is called out.

- **Owner-scoped via Position.** Trade has no direct `user_id`; ownership
  flows through `position.user_id`. Every endpoint resolves the Position
  first; cross-user `position_id` → **404** (matching P6/P7/P8 — info-leak
  avoidance).
- **`account_id` is server-derived.** Copied from `position.account_id` at
  create time; **not** accepted from the client. The denormalization invariant
  (data-model §4.5: "Denormalized; matches position.account_id") is enforced
  by code, not by trust.
- **`price >= 0` (AMENDS macro §6④).** The original §6④ wording was
  `price > 0`. Data-model §4.5.2 *requires* `price = 0.00` on the
  worthless-expire / assignment / exercise option close legs (these are the
  broker's actual fills). The literal `>0` rule would reject those flows. P9
  enforces `price >= 0`; sign still lives entirely in `cash_flow` via the
  action sign. **P9.3 task: update macro §6④ + changelog of both
  `backend-expansion-plan.md` and `.zh.md`.**
- **`cash_flow` is server-computed.** Formula per macro §6④:
  ```
  cash_flow = sign(action) × price × quantity × multiplier
              − commission − fees
  where sign(action) = -1 for buy / bto / btc,
                       +1 for sell / sto / stc,
        multiplier  = OptionContract.multiplier for options,
                    = 1 otherwise.
  ```
  `TradeCreate` does **not** include `cash_flow`. Any client-supplied value
  in the POST body → 422 `extra_forbidden`.
- **`action ↔ instrument.kind` consistency.** `bto / sto / btc / stc` ⇒
  `kind == option`; `buy / sell` ⇒ `kind in (stock, forex)`. Server resolves
  the Instrument, then checks. Mismatch → **422**.
- **Quantity rules.**
  - `quantity > 0` always.
  - Options (`instrument.kind == option`): **integer required** (i.e.
    `quantity % 1 == 0` after Decimal coercion). Fractional contracts are not
    a thing.
  - Stock / forex: fractional allowed (fractional shares + forex micro-lots).
  - The positivity check is at the Pydantic layer (`gt=0`); the integer
    constraint is in the service layer (it requires the resolved Instrument).
- **Cost field defaults.** `commission` and `fees` default to `Decimal("0")`
  when omitted by the client; both `>= 0` (Pydantic `ge=0`).
- **Multi-leg POST = single endpoint accepts single OR array.** `POST
  /trades` body is either a `TradeCreate` object or a non-empty list of
  them. **Rules for arrays:**
  - All rows must reference the **same `position_id`** (else 422).
  - If client supplies `order_group_id` on any row, **all rows must share it**
    (else 422). If client omits it on a multi-row submission, server
    generates one fresh UUID and assigns to every row.
  - Single-row submission: `order_group_id` defaults to NULL unless client
    supplies it.
  - Atomic transaction — any row's validation failure rolls all back.
  - Response: 201 with a JSON array of all created rows (preserving submit
    order), even for single-row submission (so clients don't branch on shape).
- **Audit-friendly soft-delete (NEW migration).** Trade gains
  `archived_at: timestamptz nullable, indexed` via `0002_trade_archived_at.py`.
  `DELETE /trades/{id}` sets `archived_at = now()`, returns 204. List default
  filters archived rows out. **`?include_archived=true`** opt-in flag
  surfaces them for audit views.
- **Trade is otherwise immutable.** `PATCH /trades/{id}` may modify **only**
  `notes`. Any other field in the PATCH body → 422 `extra_forbidden`. To
  amend numeric data the user must DELETE (= archive) the row and POST a
  new replacement Trade. Rationale: audit safety + zero `cash_flow`
  recompute branches in MVP.
- **Closed-position lock.** When the parent `Position.status == "closed"`,
  all of `POST` (any row referencing it), `PATCH`, `DELETE` → **409** with
  detail `"parent position is closed; trades on closed positions are
  immutable"`. Mirrors P8's reopen-rejection: anything frozen stays frozen.
- **Position-DELETE compatibility (no change to P8 code).** P8's "no
  attached trades" check counts **all** Trade rows including archived ones.
  Archiving every trade does **not** unlock `DELETE /positions/{id}` —
  preserves audit invariant. Reversing this is a one-filter change later;
  documented in §10.
- **`broker_trade_id` not exposed in P9.** All P9 Trades are manual entries;
  the column remains NULL. The future PX integrations phase can additively
  expose it on `TradeRead` and accept it on import-only endpoints.
- **No auto-close detection from Trade events.** Position auto-close (net-qty
  → 0 ⇒ closed) remains the P12 / `services/positions.py::detect_auto_close`
  responsibility. P9's POST/PATCH/DELETE do **not** mutate Position state.

## 2. Scope

### In scope (this plan)

- `alembic/versions/0002_trade_archived_at.py` — adds `archived_at` to
  `trades`; index on the new column.
- `schemas/trade.py` — `TradeCreate` / `TradeUpdate` / `TradeRead`; the
  POST body type alias for single-or-list discrimination.
- `services/trades.py` — `compute_cash_flow()`, `validate_action_kind()`,
  `create_trades_atomic()` (transactionally creates one or many rows).
- `api/trades.py` — router with `POST /trades`, `GET /trades`,
  `GET /trades/{id}`, `PATCH /trades/{id}`, `DELETE /trades/{id}`.
- Wire under `/trades` in `main.py` (final URL prefix: `/api/trades`).
- `tests/test_trades.py` — full matrix per §7.
- Frontend: regenerate `frontend/src/api/schema.d.ts` after backend green.
- **Docs amendment**: update macro `backend-expansion-plan.md` §6④
  `price > 0` → `price >= 0` (+ `.zh.md`) and add a changelog line in both.

### NOT in scope

- Position auto-close detection (P12 / `services/positions.py` stub).
- **Mutable numeric Trade fields.** No `cash_flow` recompute logic in P9.
- `broker_trade_id` API surface (PX External Integrations).
- Strategy-meta extensions (P10) and TradePlan (P11).
- Derived aggregates over Trade rows beyond P8's `freeze_pnl_realized`
  (e.g., open-position running PnL) — P12.
- Pagination on `GET /trades` (matches Account / Position MVP — add later
  when row counts justify it).
- Frontend F4 implementation (mapped in `frontend-expansion-plan.md`).
- Allowing Position-DELETE when all attached trades are archived — kept
  consistent with current P8 invariant.

## 3. Files

```
backend/alembic/versions/0002_trade_archived_at.py    ← NEW migration
backend/src/trading_journal/
├── schemas/trade.py                                  ← NEW
├── services/trades.py                                ← NEW
├── api/trades.py                                     ← NEW
└── main.py                                           ← CHANGED: include trades.router
backend/tests/test_trades.py                          ← NEW
frontend/src/api/schema.d.ts                          ← REGENERATED at end
docs/design/backend-expansion-plan.md                 ← amend §6④ + changelog
docs/design/backend-expansion-plan.zh.md              ← mirror amendment
```

`services/` already exists from P8 (`services/positions.py`,
`services/__init__.py`). P9 simply adds another module.

## 4. Schema shapes (target)

```python
import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import TradeAction


class TradeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)            # see §1 amendment of macro §6④
    commission: Decimal = Field(default=Decimal("0"), ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    executed_at: datetime
    order_group_id: uuid.UUID | None = None
    notes: str | None = None
    # NOT accepted: account_id (server-derived), cash_flow (server-computed),
    # broker_trade_id (PX), archived_at (server-managed), id (server-generated)


class TradeUpdate(BaseModel):
    """Trade is otherwise immutable — only `notes` may change.

    All other numeric / structural fields are rejected by `extra="forbid"`.
    To amend a Trade's numbers, archive (DELETE) + POST a replacement.
    """
    model_config = ConfigDict(extra="forbid")

    notes: str | None = None


class TradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position_id: uuid.UUID
    account_id: uuid.UUID
    instrument_id: uuid.UUID
    action: TradeAction
    quantity: Decimal
    price: Decimal
    commission: Decimal
    fees: Decimal
    cash_flow: Decimal
    executed_at: datetime
    order_group_id: uuid.UUID | None
    broker_trade_id: str | None
    notes: str | None
    archived_at: datetime | None


# POST body discriminator — TypeAlias on the router layer:
TradeCreatePayload = TradeCreate | list[TradeCreate]
```

**Notes on shapes.**

- `extra="forbid"` on writes means client-supplied `cash_flow`,
  `account_id`, `broker_trade_id`, `archived_at`, `id` all return 422 with a
  specific field error. No silent drops.
- `quantity: Field(gt=0)` enforces positivity; the **option integer rule** is
  enforced in `services/trades.py` after Instrument resolution.
- `commission` / `fees` default to `Decimal("0")` — client can omit; matches
  the manual-entry ergonomic of "no commission tier? just leave it blank."
- `TradeRead` includes `archived_at` so audit views can render it; clients
  filtering archived rows just check `archived_at is None`.
- The single-or-array nature of POST is **not** expressed by a discriminated
  union in Pydantic (FastAPI handles `body: TradeCreate | list[TradeCreate]`
  natively). Router-layer code normalizes to `list[TradeCreate]` internally.

## 5. Service-layer surface (`services/trades.py`)

```python
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models._enums import InstrumentKind, TradeAction
from trading_journal.models.instrument import Instrument, OptionContract
from trading_journal.models.position import Position
from trading_journal.models.trade import Trade


_SELL_SIDE_ACTIONS = {TradeAction.SELL, TradeAction.STO, TradeAction.STC}
_OPTION_ACTIONS = {TradeAction.BTO, TradeAction.STO, TradeAction.BTC, TradeAction.STC}
_NONOPTION_ACTIONS = {TradeAction.BUY, TradeAction.SELL}


def compute_cash_flow(
    action: TradeAction,
    price: Decimal,
    quantity: Decimal,
    multiplier: int,
    commission: Decimal,
    fees: Decimal,
) -> Decimal:
    """Signed net cash impact (per macro §6④).

    sign = -1 for buy/bto/btc, +1 for sell/sto/stc; option multiplier from
    OptionContract.multiplier, else 1. Commission/fees deducted regardless of
    sign (they always cost money).
    """
    sign = Decimal(1) if action in _SELL_SIDE_ACTIONS else Decimal(-1)
    gross = sign * price * quantity * Decimal(multiplier)
    return gross - commission - fees


def validate_action_kind(action: TradeAction, kind: InstrumentKind) -> None:
    """Raise ValueError if action ↔ kind mismatch. Router maps to 422."""
    if action in _OPTION_ACTIONS and kind is not InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires an option instrument, "
            f"got '{kind.value}'"
        )
    if action in _NONOPTION_ACTIONS and kind is InstrumentKind.OPTION:
        raise ValueError(
            f"action '{action.value}' requires a stock or forex instrument, "
            f"got 'option'"
        )


def validate_option_quantity_integer(
    action: TradeAction, kind: InstrumentKind, quantity: Decimal
) -> None:
    """Options must trade in integer contract counts."""
    if kind is InstrumentKind.OPTION and quantity % 1 != 0:
        raise ValueError(
            f"option quantity must be an integer number of contracts, got {quantity}"
        )


async def resolve_multiplier(
    session: AsyncSession, instrument: Instrument
) -> int:
    """For options return `OptionContract.multiplier`; else 1."""
    if instrument.kind is not InstrumentKind.OPTION:
        return 1
    contract = await session.get(OptionContract, instrument.id)
    if contract is None:
        # Should never happen if the data is consistent, but be defensive.
        raise ValueError(
            f"instrument {instrument.id} is kind=option but has no OptionContract row"
        )
    return contract.multiplier


async def create_trades_atomic(
    session: AsyncSession,
    position: Position,
    rows: list["TradeCreate"],
) -> list[Trade]:
    """Validate every row against its resolved Instrument, compute cash_flow,
    insert atomically. Caller is responsible for the surrounding session
    transaction commit. Raises ValueError on any validation failure (router
    converts to 422)."""
    # implementation per P9.2 §6 below
```

Why a service module rather than fat-router code: it keeps the cash-flow
formula in **one** place, lets P12's derived layer call `compute_cash_flow`
directly when reconstructing pre-archive history, and gives the test suite a
sub-HTTP unit-test surface for the formula edge cases (the option
`multiplier`, worthless expires at `price=0`, sell side sign).

## 6. Phased plan

Three sub-phases. After each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src` — baseline **183 tests** at P8 finish.

### P9.1 — Migration + schemas + service module

**Goal.** Persistence and pure-function layer ready; no HTTP yet.

**Tasks.**

1. **Migration `0002_trade_archived_at.py`.**
   ```python
   def upgrade() -> None:
       with op.batch_alter_table("trades", schema=None) as batch_op:
           batch_op.add_column(
               sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
           )
           batch_op.create_index(
               batch_op.f("ix_trades_archived_at"), ["archived_at"], unique=False
           )

   def downgrade() -> None:
       with op.batch_alter_table("trades", schema=None) as batch_op:
           batch_op.drop_index(batch_op.f("ix_trades_archived_at"))
           batch_op.drop_column("archived_at")
   ```
   Add `archived_at: Mapped[datetime | None]` to `models/trade.py`.
2. **`schemas/trade.py`** — three classes from §4.
3. **`services/trades.py`** — `compute_cash_flow`, `validate_action_kind`,
   `validate_option_quantity_integer`, `resolve_multiplier`,
   `create_trades_atomic`. `create_trades_atomic` body:
   - For each row: `instrument = await session.get(Instrument, row.instrument_id)`;
     422-style errors if missing.
   - `validate_action_kind(row.action, instrument.kind)`.
   - `validate_option_quantity_integer(row.action, instrument.kind, row.quantity)`.
   - `multiplier = await resolve_multiplier(session, instrument)`.
   - `cash_flow = compute_cash_flow(...)`.
   - Append `Trade(...)` to a buffer; `session.add_all(buffer)` at the end.
   - `flush()` so caller can `refresh()` for read-back.
4. **Unit tests** (no HTTP yet) in `tests/test_trades.py`:
   - `test_compute_cash_flow_buy_stock` — `-price*qty - commission - fees`.
   - `test_compute_cash_flow_sell_stock` — `+price*qty - commission - fees`.
   - `test_compute_cash_flow_sto_option_multiplier_100` — sign + multiplier.
   - `test_compute_cash_flow_btc_at_zero_price_worthless_expire` — only
     commission+fees come out (≤ 0).
   - `test_compute_cash_flow_btc_at_zero_price_zero_costs_equals_zero`.
   - `test_validate_action_kind_*` — option↔option, stock↔stock OK;
     mismatch raises.
   - `test_validate_option_quantity_integer_*` — fractional option raises;
     fractional stock OK; integer always OK.

**Acceptance.** Migration applies clean (`alembic upgrade head`); schemas
import; service unit tests green; no API yet.

### P9.2 — Router: POST / GET / PATCH / DELETE

**Goal.** Full CRUD over HTTP, including multi-leg array submit.

**Tasks.**

1. **`api/trades.py`** — router under `/trades`. Private helpers:
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

   async def _get_owned_trade(
       session: AsyncSession, user: User, trade_id: uuid.UUID
   ) -> Trade:
       # Join through Position to enforce ownership.
       stmt = (
           select(Trade)
           .join(Position, Trade.position_id == Position.id)
           .where(Trade.id == trade_id, Position.user_id == user.id)
       )
       trade = (await session.execute(stmt)).scalar_one_or_none()
       if trade is None:
           raise HTTPException(404, "Trade not found")
       return trade
   ```

2. **Endpoints.**

   | Method | Path | Behavior |
   |---|---|---|
   | `POST` | `""` | Body is `TradeCreate \| list[TradeCreate]`. Normalize to list. Validate "all rows same `position_id`". Resolve position (owner, must be open — else 409). Apply / generate `order_group_id` per §1. Call `services.create_trades_atomic`. Commit. Return 201 + `list[TradeRead]`. |
   | `GET` | `""` | Owner-scoped via Position join. Query params: `position_id` (optional UUID), `order_group_id` (optional UUID), `include_archived` (bool, default false). Order: `executed_at DESC, id ASC`. |
   | `GET` | `"/{id}"` | Single, owner-scoped (returns archived rows too — audit detail view). 404 cross-user / missing. |
   | `PATCH` | `"/{id}"` | Only `notes` allowed (`extra="forbid"` enforces). Parent-position closed → 409. Already archived → 409 `"cannot modify an archived trade"`. |
   | `DELETE` | `"/{id}"` | Parent-position closed → 409. Already archived → 404. Else set `archived_at = func.now()`. 204. |

3. **POST normalization helper.**
   ```python
   def _normalize_payload(
       body: TradeCreate | list[TradeCreate],
   ) -> tuple[list[TradeCreate], bool]:
       """Return (rows, was_array). Empty array → 422."""
       if isinstance(body, list):
           if not body:
               raise HTTPException(422, "trade array must be non-empty")
           return body, True
       return [body], False
   ```

4. **POST cross-row validation.**
   ```python
   # All rows must share the same position_id.
   distinct_positions = {row.position_id for row in rows}
   if len(distinct_positions) > 1:
       raise HTTPException(
           422, "all rows in a multi-leg POST must share the same position_id"
       )

   # order_group_id: if any row supplies it, all must agree.
   supplied_ogids = {row.order_group_id for row in rows if row.order_group_id}
   if len(supplied_ogids) > 1:
       raise HTTPException(
           422, "rows in a multi-leg POST must share order_group_id"
       )
   if supplied_ogids:
       group_id = supplied_ogids.pop()
   elif was_array and len(rows) > 1:
       group_id = uuid.uuid4()
   else:
       group_id = None  # respect single-row NULL default
   # Apply to every row (None is fine for single-row no-supplied case).
   for row in rows:
       row.order_group_id = group_id
   ```

5. **POST closed-position guard.**
   ```python
   position = await _resolve_position(session, user, rows[0].position_id)
   if position.status is PositionStatus.CLOSED:
       raise HTTPException(
           409,
           "parent position is closed; trades on closed positions are immutable",
       )
   ```
6. **`account_id` denorm** — set from `position.account_id` on every row
   constructed inside `create_trades_atomic`.
7. **`main.py`** — register `trades.router` immediately after `positions.router`.
8. **`tests/test_trades.py`** — full §7 matrix.

**Acceptance.** All P9 tests green; full suite + ruff + mypy clean. Expected
total: **183 (P8) + ~60 P9 = ~243 tests**.

### P9.3 — Regression, codegen, doc amendment, brief

**Goal.** Lock baseline; propagate to frontend; finalize the macro-plan
amendment.

**Tasks.**

1. `uv run pytest -q && uv run ruff check . && uv run mypy src` — all green.
2. **Amend macro plan §6④.** In `docs/design/backend-expansion-plan.md` §6
   item 4, change `price > 0 always (per-unit fill price...)` to `price >= 0
   always (per-unit fill price; sign lives entirely in cash_flow via the
   action sign — see data-model §4.5.2 for worthless-expire / assignment
   flows that legitimately use price=0)`. Mirror change in `.zh.md`. Add a
   line to each file's changelog: `"P9 v0.1 (2026-05-26): price > 0 → price
   >= 0 to honor data-model §4.5.2 broker-fill semantics."`
3. **Frontend codegen.** Backend up on `:8000`,
   `cd frontend && npm run codegen` → expect `TradeCreate`, `TradeUpdate`,
   `TradeRead` schemas added; `npm run build` passes; commit
   `schema.d.ts`.
4. Walk the §8 curl recipe end-to-end.
5. Leave `review-notes/p9_implementation_brief.md` (mirror the P6/P7/P8
   briefs).

**Acceptance.** All green; doc amendment committed; recipe passes; brief
filed.

## 7. Test matrix

`tests/test_trades.py`, reusing `auth_client`, `second_user_client`, and the
migrated tempfile fixture from `conftest.py`. Add a helper to seed
`Account` + `Instrument` (stock USD + a sample option contract) + open
`Position` rows in the fresh DB — similar to the pattern positions tests
already follow.

### Service-layer tests (no HTTP)

| Test | Validates |
|---|---|
| `test_compute_cash_flow_buy_stock` | sign=-1, multiplier=1 |
| `test_compute_cash_flow_sell_stock` | sign=+1, multiplier=1 |
| `test_compute_cash_flow_sto_option_x100` | sign=+1, multiplier=100 |
| `test_compute_cash_flow_btc_at_zero_price` | gross=0, returns -(commission+fees) |
| `test_compute_cash_flow_costs_subtracted_on_both_sides` | sell side still pays costs |
| `test_validate_action_kind_option_ok` | bto on option → ok |
| `test_validate_action_kind_stock_ok` | buy on stock → ok |
| `test_validate_action_kind_bto_on_stock_raises` | mismatch |
| `test_validate_action_kind_buy_on_option_raises` | mismatch |
| `test_validate_option_quantity_integer_fractional_raises` | option qty 1.5 → raises |
| `test_validate_option_quantity_integer_stock_fractional_ok` | stock qty 0.5 → ok |

### POST `/trades` (single)

| Test | Validates |
|---|---|
| `test_create_single_stock_buy_201` | minimum payload → 201 array of length 1; `cash_flow = -price*qty - costs`; `account_id` derived from position; `order_group_id` null |
| `test_create_single_stock_sell_cash_flow_positive` | sign reverses correctly |
| `test_create_single_option_sto_uses_multiplier` | cash_flow includes ×100 |
| `test_create_with_supplied_order_group_id` | server respects client value |
| `test_create_rejects_unknown_position_404` | non-existent position_id |
| `test_create_rejects_other_users_position_404` | cross-user → 404 |
| `test_create_rejects_unknown_instrument_422` | non-existent instrument_id |
| `test_create_rejects_action_kind_mismatch_422` | bto on stock |
| `test_create_rejects_buy_on_option_422` | buy on option |
| `test_create_rejects_fractional_option_qty_422` | option qty 1.5 |
| `test_create_allows_fractional_stock_qty` | 0.25 shares OK |
| `test_create_rejects_negative_quantity_422` | Pydantic gt=0 |
| `test_create_rejects_zero_quantity_422` | gt=0 (not ge=0) |
| `test_create_rejects_negative_price_422` | Pydantic ge=0 |
| `test_create_allows_zero_price_for_btc` | worthless-expire flow |
| `test_create_allows_zero_price_for_stc` | exercise/expire long-leg flow |
| `test_create_rejects_negative_commission_422` | ge=0 |
| `test_create_rejects_negative_fees_422` | ge=0 |
| `test_create_rejects_account_id_in_body_422` | server-derived |
| `test_create_rejects_cash_flow_in_body_422` | server-computed |
| `test_create_rejects_broker_trade_id_in_body_422` | PX, not now |
| `test_create_rejects_archived_at_in_body_422` | server-managed |
| `test_create_409_when_position_closed` | parent closed → 409 with detail |

### POST `/trades` (array / multi-leg)

| Test | Validates |
|---|---|
| `test_create_array_4leg_ic_open_201` | 4 rows shared order_group_id auto-generated; each row's cash_flow correct; account_id derived |
| `test_create_array_2leg_assignment_short_put` | btc put @ 0.00 + buy stock @ strike; both rows persist |
| `test_create_array_with_supplied_shared_ogid` | server respects supplied uuid |
| `test_create_array_rejects_mixed_position_id_422` | all rows must share position_id |
| `test_create_array_rejects_mixed_ogid_422` | client-supplied ogids must agree |
| `test_create_array_rejects_one_row_fails_422_rollback` | row 3 invalid → all 4 rolled back; DB unchanged |
| `test_create_array_rejects_empty_422` | empty list |
| `test_create_array_409_when_position_closed` | one rejection covers all |
| `test_create_array_returns_in_submit_order` | response array preserves input order |

### GET `/trades` (list)

| Test | Validates |
|---|---|
| `test_list_default_excludes_archived` | archived row not returned by default |
| `test_list_include_archived_true_shows_them` | `?include_archived=true` |
| `test_list_filter_position_id` | scopes correctly |
| `test_list_filter_order_group_id` | returns only the 4 IC legs |
| `test_list_filter_combined` | position_id + order_group_id |
| `test_list_unfiltered_returns_all_user_trades` | spans positions |
| `test_list_cross_user_isolation` | other user's rows not visible |
| `test_list_orders_executed_at_desc` | newest first |
| `test_list_rejects_bad_uuid_422` | bad query value |

### GET `/trades/{id}`

| Test | Validates |
|---|---|
| `test_get_200` | own row |
| `test_get_returns_archived_row` | archived still gettable by id (audit) |
| `test_get_404_unknown` | random UUID |
| `test_get_404_cross_user` | other user's id → 404 (not 403) |

### PATCH `/trades/{id}`

| Test | Validates |
|---|---|
| `test_patch_notes_200` | basic notes change |
| `test_patch_notes_to_null_200` | clearing notes |
| `test_patch_rejects_quantity_change_422` | extra_forbidden |
| `test_patch_rejects_price_change_422` | extra_forbidden |
| `test_patch_rejects_action_change_422` | extra_forbidden |
| `test_patch_rejects_cash_flow_change_422` | extra_forbidden |
| `test_patch_rejects_position_id_change_422` | extra_forbidden |
| `test_patch_rejects_account_id_change_422` | extra_forbidden |
| `test_patch_rejects_archived_at_change_422` | extra_forbidden |
| `test_patch_409_when_position_closed` | parent closed |
| `test_patch_409_when_already_archived` | "cannot modify an archived trade" |
| `test_patch_404_cross_user` | |
| `test_patch_does_not_change_cash_flow` | notes-only PATCH leaves cash_flow untouched |

### DELETE `/trades/{id}`

| Test | Validates |
|---|---|
| `test_delete_204_sets_archived_at` | row persists with archived_at populated |
| `test_delete_list_default_excludes_after_delete` | invisible to default list |
| `test_delete_get_by_id_still_works_after_delete` | audit detail readable |
| `test_delete_404_already_archived` | second DELETE → 404 |
| `test_delete_409_when_position_closed` | parent closed |
| `test_delete_404_cross_user` | |
| `test_delete_does_not_unlock_position_delete` | seed trade, archive it, DELETE position → still 409 |

### Cash-flow correctness across data-model §4.5.2 flows (integration)

These prove the §4.5.2 mapping table is faithfully implementable.

| Test | Notion event | Validates |
|---|---|---|
| `test_flow_sell_put` | sell put | 1 row, `sto` put, cash_flow > 0 |
| `test_flow_close_sell_put` | close sell put | 1 row, `btc` put, cash_flow < 0 |
| `test_flow_assignment_short_put` | assignment | 2 rows, shared ogid, `btc` @ 0 + `buy` 100 @ strike; total cash_flow correct |
| `test_flow_worthless_expire_short_option` | expire | 1 row, `btc` @ 0, commission 0, fees 0 → cash_flow == 0 |
| `test_flow_iron_condor_open` | open IC | 4 rows, shared ogid, net credit > 0 |

### Auth

| Test | Validates |
|---|---|
| `test_requires_auth` | parametrized POST/GET/PATCH/DELETE without cookie → 401 |

## 8. Manual verification reference (full P9 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"

# Register + login
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"bob@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=bob@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# Seed: account + stock instrument + position
ACCT=$(curl -fsS -X POST "$BASE/api/accounts" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"name":"IBKR","broker":"IBKR","account_type":"margin","base_currency":"USD"}' | jq -r .id)
STOCK=$(curl -fsS -X POST "$BASE/api/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","currency":"USD"}' | jq -r .id)
POS=$(curl -fsS -X POST "$BASE/api/positions" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"account_id\":\"$ACCT\",\"primary_instrument_id\":\"$STOCK\",\"strategy_type\":\"spot_stock\",\"opened_at\":\"2026-06-01T14:30:00Z\"}" | jq -r .id)

# 1) Single buy → 201, cash_flow = -100*150 - 1 - 0 = -15001
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"buy\",\"quantity\":\"100\",\"price\":\"150.00\",\"commission\":\"1.00\",\"executed_at\":\"2026-06-01T14:30:00Z\"}"

# 2) Multi-leg array (synthetic 2-row "partial sell + sell") → 201 with shared order_group_id
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "[
    {\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"sell\",\"quantity\":\"50\",\"price\":\"160.00\",\"executed_at\":\"2026-06-10T18:00:00Z\"},
    {\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"sell\",\"quantity\":\"50\",\"price\":\"161.00\",\"executed_at\":\"2026-06-10T18:00:01Z\"}
  ]"

# 3) Worthless-expire flow on an option (assumes you've also created an option
#    instrument; omitted here for brevity — the recipe should mirror §7's
#    test_flow_worthless_expire_short_option).

# 4) PATCH notes → 200
TID=$(curl -fsS "$BASE/api/trades?position_id=$POS" -b "$JAR" | jq -r '.[0].id')
curl -fsSi -X PATCH "$BASE/api/trades/$TID" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"Initial entry tranche."}'

# 5) PATCH something other than notes → 422
curl -fsSi -X PATCH "$BASE/api/trades/$TID" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"quantity":"200"}'

# 6) DELETE (archive) → 204; default list excludes it
curl -fsSi -X DELETE "$BASE/api/trades/$TID" -b "$JAR"
curl -fsS "$BASE/api/trades?position_id=$POS" -b "$JAR" | jq 'length'
curl -fsS "$BASE/api/trades?position_id=$POS&include_archived=true" -b "$JAR" | jq 'length'

# 7) Close the position (per P8 §8); then any trade write → 409
curl -fsSi -X PATCH "$BASE/api/positions/$POS" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"status":"closed","closed_at":"2026-06-15T20:00:00Z"}'
curl -fsSi -X POST "$BASE/api/trades" -b "$JAR" -H 'Content-Type: application/json' \
  -d "{\"position_id\":\"$POS\",\"instrument_id\":\"$STOCK\",\"action\":\"buy\",\"quantity\":\"1\",\"price\":\"1\",\"executed_at\":\"2026-06-20T14:00:00Z\"}"
```

## 9. Implementer quickstart

```bash
cd backend
uv run alembic upgrade head   # apply 0002 once P9.1 lands
# build P9.1 → P9.2 → P9.3; after each:
uv run pytest -q && uv run ruff check . && uv run mypy src

# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

After P9 lands, the next backend gates are P10 (strategy-meta extensions)
and P11 (TradePlan event stream), both feeding F3 — F4 (Trade entry UI) can
begin in parallel as soon as P9 ships, using the same `schema.d.ts` types.

## 10. Future-proofing notes (don't implement, just don't preclude)

- **Numeric PATCH (qty/price/commission/fees).** If audit-via-archive proves
  too friction-y, a future phase can add allow-listed mutable fields by
  extending `TradeUpdate` and adding a `recompute_cash_flow_on_change`
  branch in `services/trades.py`. Closed-position lock and archived-row lock
  stay in place.
- **Position-DELETE when all trades archived.** One filter:
  `select(Trade.id).where(Trade.position_id == position.id,
  Trade.archived_at.is_(None)).limit(1)` in `api/positions.py`. Add when
  user demand justifies; until then the strict invariant protects audit.
- **`broker_trade_id` exposure.** PX additively whitelists it on the read
  schema and accepts it on a future import-only endpoint.
- **Auto-close detection.** Plugs into `services/positions.py::detect_auto_close`
  using `services/trades.compute_cash_flow` or net-qty queries. Hook
  location: post-`session.commit()` in Trade POST, before returning to the
  client. Stays opt-in.
- **Pagination.** When list response sizes exceed ~500, add cursor or
  offset; both `executed_at DESC, id ASC` ordering is stable for cursor
  pagination on `(executed_at, id)`.
- **Strategy-aware validation in P10.** P9 deliberately does not check
  things like "wheel position only takes stock + same-underlying option
  trades" — that level of strategy-coupled validation lands when
  `WheelCycleMeta` / `PmccCycleMeta` exist.

---

## Changelog

- **v0.1 (2026-05-26)** — Initial P9 build plan. Settled the five P9
  sub-decisions with the user: (1) `price >= 0` to honor data-model §4.5.2
  worthless-expire / assignment flows (amends macro §6④); (2) Trade is
  immutable except `notes` — DELETE is soft-delete via new `archived_at`
  column for audit; (3) all of POST/PATCH/DELETE return 409 when parent
  Position is closed (mirrors P8 reopen-rejection); (4) list is flat
  `GET /trades?position_id=...` with optional filters; (5) multi-leg POST
  is a single endpoint accepting object or array, server auto-generates the
  shared `order_group_id` when the array is unflagged. Three sub-phases:
  P9.1 migration + schemas + service, P9.2 router, P9.3
  regression+codegen+doc-amend+brief. `services/trades.py` introduced
  alongside the existing `services/positions.py` to keep the
  cash-flow formula and the action-kind/qty guards reusable across the
  derived layer in P12.
