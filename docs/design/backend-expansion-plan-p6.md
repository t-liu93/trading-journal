# Backend Phase P6 — Instrument CRUD (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p6.zh.md)

> Status: **DRAFT v0.1** (2026-05-21). Detailed build plan for **P6 core** from the macro
> roadmap [backend-expansion-plan.md](./backend-expansion-plan.md). Self-contained — an
> implementer can execute it directly. Companion: [data-model.md](./data-model.md) §4.3 & §6,
> and the **Account template** (`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`).
>
> **P6.x (external validation) is NOT in this document.** It needs a provider spike +
> decisions and is sequenced after P6 core — see [roadmap §P6.x](./backend-expansion-plan.md).
> Do not start it from this plan.

## 1. Purpose & context

Turn the already-migrated `instruments` / `option_contracts` / `forex_pairs` tables into a
typed CRUD API: a **shared, global instrument dictionary** users attach to their positions
and trades. No DB migration is needed (tables exist since Phase 2's `0001_initial_schema`);
P6 is purely Pydantic schemas + a router + tests.

### Settled decisions (do not re-derive)

- **Global, not owner-scoped.** `Instrument` has **no `user_id`**. All endpoints still
  require auth (`current_active_user`), but there is **no per-user filtering** — every user
  sees and shares the same dictionary. (This is the one place the Account template differs.)
- **Endpoints:** `GET /instruments` (list/search), `GET /instruments/{id}`, `POST /instruments`
  (**get-or-create**). **No PATCH/DELETE** — instruments are referenced by others' positions.
- **get-or-create + dedup** on a natural key (per kind, below). Existing row → **200**;
  newly created → **201**. App-layer dedup (query-first); a DB unique constraint is deferred
  (would need a migration) — the race window is accepted for MVP.
- **symbol normalization:** `.upper().strip()` before lookup/insert.
- **Validation = format only** (no factual "is this a real ticker" check — that's P6.x).
- **option** auto-creates its underlying stock from `underlying_symbol`; `currency` is shared
  (option currency == underlying currency, data-model §4.3) — supplied once.
- **forex** derives `Instrument.currency` from `quote_currency` so the §4.3 invariant cannot
  be violated.

## 2. Scope

### In scope (this plan)

- `schemas/instrument.py` — discriminated-union create + nested read schemas
- `api/instruments.py` — router (`GET` list/search, `GET /{id}`, `POST` get-or-create)
- Wire under `/instruments` in `main.py`
- `tests/test_instruments.py`
- After backend is green: regenerate `frontend/src/api/schema.d.ts` (`npm run codegen`) + commit

### NOT in scope

- **P6.x external validation / `/instruments/lookup` / caching** — separate, deferred.
- PATCH/DELETE of instruments.
- DB unique constraints / dedup migration.
- Position/Trade wiring (P8/P9) — instruments are created standalone here.

## 3. Files

```
backend/src/trading_journal/
├── schemas/instrument.py        ← NEW
├── api/instruments.py           ← NEW
└── main.py                      ← CHANGED: include instruments.router
backend/tests/test_instruments.py ← NEW
frontend/src/api/schema.d.ts     ← REGENERATED at the end
```

## 4. Schema shapes (target)

`schemas/instrument.py` — a Pydantic **discriminated union** on `kind` for create, and a
single `InstrumentRead` with optional nested extension blocks for read:

```python
CURRENCY = r"^[A-Z]{3}$"

class StockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stock"]
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY)

class OptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["option"]
    underlying_symbol: str = Field(min_length=1, max_length=64)
    underlying_exchange: str | None = Field(default=None, max_length=64)
    currency: str = Field(pattern=CURRENCY)        # shared by option + its underlying
    opt_type: OptType
    strike: Decimal = Field(gt=0)
    expiry: date
    multiplier: int = Field(default=100, gt=0)
    style: OptionStyle = OptionStyle.AMERICAN

class ForexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["forex"]
    symbol: str = Field(min_length=1, max_length=64)   # e.g. "EURUSD"
    base_currency: str = Field(pattern=CURRENCY)
    quote_currency: str = Field(pattern=CURRENCY)
    pip_size: Decimal = Field(gt=0)
    contract_size: Decimal | None = Field(default=None, gt=0)
    # Instrument.currency is derived = quote_currency (not in this payload)

InstrumentCreate = Annotated[
    Union[StockCreate, OptionCreate, ForexCreate], Field(discriminator="kind")
]

class OptionContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    underlying_id: uuid.UUID
    opt_type: OptType
    strike: Decimal
    expiry: date
    multiplier: int
    style: OptionStyle

class ForexPairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    base_currency: str
    quote_currency: str
    pip_size: Decimal
    contract_size: Decimal | None

class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: InstrumentKind
    symbol: str
    exchange: str | None
    currency: str
    created_at: datetime
    option: OptionContractRead | None = None   # populated when kind == option
    forex: ForexPairRead | None = None          # populated when kind == forex
```

> `InstrumentRead.option`/`.forex` are not auto-populated by `from_attributes` (different
> relationship names). The router fetches the extension row and constructs the read model
> explicitly (a small helper `_to_read(instrument, session)`).

## 5. Phased plan

Sequential. Keep the backend green after each: `uv run pytest -q && uv run ruff check . &&
uv run mypy src` (Phase 0–4 baseline currently 47/47). Each sub-phase is independently
committable.

### P6.1 — Stock create + get + list/search

**Goal.** Module scaffold + the full read/list/get-or-create pipeline working for `stock`
only. Establishes the patterns the other two kinds slot into.

**Tasks.**
1. `schemas/instrument.py` — add `StockCreate`, `InstrumentRead` (base fields, no extension
   blocks yet), and the `InstrumentCreate` union containing only `StockCreate` for now.
2. `api/instruments.py`:
   - `router = APIRouter(prefix="/instruments", tags=["instruments"])`
   - `POST ""` → `InstrumentRead`, get-or-create. Take FastAPI `response: Response` to set
     **200 (existed) vs 201 (created)** dynamically. Normalize symbol; dedup query on
     `(kind=stock, symbol, currency, exchange)` — **use `.is_(None)` when `exchange` is None**
     (SQL `= NULL` never matches).
   - `GET ""` → `list[InstrumentRead]`. Query params: `kind?`, `q?` (case-insensitive prefix
     on symbol via `ilike(f"{q}%")`), `limit=50`. Order by `symbol`, then `created_at`.
   - `GET /{id}` → `InstrumentRead`; 404 if missing.
   - All depend on `current_active_user` + `get_session` (mirror Account router DI).
3. Wire `app.include_router(instruments.router)` in `main.py` (match how accounts is wired,
   under the same `/api` prefix scheme).
4. `tests/test_instruments.py` — reuse `auth_client` / `second_user_client` fixtures.

**Manual verification.**
```bash
# (after login → cookies.txt, see test_accounts curl recipe)
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"aapl","exchange":"NASDAQ","currency":"USD"}'
# → 201, symbol normalized to "AAPL"
# repeat the exact same POST → 200 (get-or-create returns the same row, no duplicate)
curl -fsS "$BASE/instruments?q=aa" -b cookies.txt        # → [AAPL]
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"X","currency":"usd"}'    # → 422 (currency not ^[A-Z]{3}$)
```

**Automated tests.**
- `test_create_stock_201` (and symbol normalized to upper)
- `test_create_stock_idempotent_returns_200_same_id` (get-or-create)
- `test_create_stock_distinct_exchange_creates_new_row`
- `test_list_filters_by_kind_and_prefix_q`
- `test_get_by_id_200` / `test_get_unknown_404`
- `test_create_rejects_bad_currency_422` / `test_create_rejects_empty_symbol_422`
- `test_requires_auth_401` (POST + GET without cookie)
- **`test_instruments_are_global`**: user A creates AAPL; user B's `GET /instruments`
  returns it, and B's identical `POST` returns **200** with A's row id (shared dictionary).

**Acceptance.** All tests pass; backend green; manual recipe matches.

### P6.2 — Option create + nested read

**Goal.** `POST {kind:"option"}` auto-resolves/creates the underlying stock and writes the
`OptionContract` extension atomically; reads return the nested `option` block.

**Tasks.**
1. Add `OptionCreate` + `OptionContractRead` to schemas; add `OptionCreate` to the union;
   add `option` field to `InstrumentRead`.
2. Router create branch for `option`:
   - get-or-create the **underlying stock** from `(underlying_symbol, currency,
     underlying_exchange)` (reuse the P6.1 stock helper).
   - dedup the contract on `(underlying_id, opt_type, strike, expiry, multiplier)`; existing
     → 200, else create `Instrument(kind=option, symbol=underlying_symbol, currency, ...)`
     **plus** `OptionContract(...)` in **one transaction** (single `commit`).
   - `Instrument.symbol` for the option row = the underlying symbol (data-model §4.3:
     "For options this is the underlying symbol").
3. `_to_read` populates `.option` when `kind == option`.

**Manual verification.**
```bash
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' -d '{
  "kind":"option","underlying_symbol":"AAPL","underlying_exchange":"NASDAQ","currency":"USD",
  "opt_type":"put","strike":"220","expiry":"2026-05-28"}'
# → 201; response has option:{opt_type:"put",strike:"220.000000",expiry:"2026-05-28",
#   multiplier:100,style:"american"}; underlying AAPL stock row exists/reused
# repeat identical → 200 same id; AAPL stock NOT duplicated
```

**Automated tests.**
- `test_create_option_201_and_nested_read`
- `test_create_option_autocreates_underlying_stock` (a stock row with that symbol now exists)
- `test_create_option_reuses_existing_underlying` (pre-create AAPL stock → no second stock row)
- `test_create_option_idempotent_returns_200`
- `test_option_currency_matches_underlying`
- `test_create_option_rejects_nonpositive_strike_422` / `bad opt_type 422`

**Acceptance.** As above; backend green.

### P6.3 — Forex create + nested read

**Goal.** `POST {kind:"forex"}` writes `Instrument` + `ForexPair`, deriving
`Instrument.currency = quote_currency`.

**Tasks.**
1. Add `ForexCreate` + `ForexPairRead`; add to union; add `forex` to `InstrumentRead`.
2. Router create branch for `forex`:
   - normalize `symbol`; set `Instrument.currency = quote_currency` (do **not** read currency
     from the payload — it isn't there).
   - dedup on `(kind=forex, symbol)`; existing → 200, else create `Instrument` + `ForexPair`
     in one transaction.
3. `_to_read` populates `.forex` when `kind == forex`.

**Manual verification.**
```bash
curl -fsSi -X POST $BASE/instruments -b cookies.txt -H 'Content-Type: application/json' -d '{
  "kind":"forex","symbol":"EURUSD","base_currency":"EUR","quote_currency":"USD",
  "pip_size":"0.0001"}'
# → 201; instrument.currency == "USD" (== quote_currency); forex block present
```

**Automated tests.**
- `test_create_forex_201_currency_equals_quote`
- `test_create_forex_idempotent_returns_200`
- `test_create_forex_rejects_bad_quote_currency_422`
- `test_forex_nested_read_has_pip_size`

**Acceptance.** As above; backend green.

### P6.4 — Regression + codegen + smoke

**Goal.** Lock the baseline and propagate types to the frontend.

**Tasks.**
1. Backend: `uv run pytest -q && uv run ruff check . && uv run mypy src` — all green.
2. Frontend codegen: backend up on :8000, then `cd frontend && npm run codegen` →
   `git diff src/api/schema.d.ts` should show the new Instrument schemas; `npm run build`
   passes; **commit the regenerated `schema.d.ts`**.
3. Walk the §7 curl recipe end-to-end.
4. Leave an implementation brief in `review-notes/p6_implementation_brief.md` (mirror the
   F1 briefs).

**Acceptance.** All green; `schema.d.ts` committed; recipe passes.

## 6. Test approach

Same harness as Phase 4 (`tests/conftest.py`: `auth_client`, `second_user_client`,
migrated tempfile SQLite, dependency-overridden session). Instruments being global means the
key extra test is **cross-user sharing** (P6.1 `test_instruments_are_global`) rather than
isolation. No new fixtures needed.

## 7. Manual verification reference (full P6 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"
curl -fsS -X POST "$BASE/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# stock — create, then idempotent
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"aapl","exchange":"NASDAQ","currency":"USD"}'   # 201, AAPL
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"kind":"stock","symbol":"AAPL","exchange":"NASDAQ","currency":"USD"}'   # 200 same id

# option — autocreates underlying, nested read
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' -d '{
  "kind":"option","underlying_symbol":"AAPL","underlying_exchange":"NASDAQ","currency":"USD",
  "opt_type":"put","strike":"220","expiry":"2026-05-28"}'                       # 201 + option{}

# forex — currency derived from quote
curl -fsSi -X POST "$BASE/instruments" -b "$JAR" -H 'Content-Type: application/json' -d '{
  "kind":"forex","symbol":"EURUSD","base_currency":"EUR","quote_currency":"USD",
  "pip_size":"0.0001"}'                                                          # 201, currency USD

curl -fsS "$BASE/instruments?q=aa" -b "$JAR"          # AAPL stock + AAPL option
curl -fsS "$BASE/instruments?kind=forex" -b "$JAR"    # EURUSD
```

## 8. Implementer quickstart

```bash
cd backend
# build sub-phase by sub-phase (P6.1 → P6.2 → P6.3 → P6.4); after each:
uv run pytest -q && uv run ruff check . && uv run mypy src
# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Changelog

- **v0.1 (2026-05-21)** — Initial P6 build plan: stock → option → forex → regression/codegen.
  P6.x external validation explicitly excluded (deferred, needs spike).
