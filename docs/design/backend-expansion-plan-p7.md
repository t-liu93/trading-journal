# Backend Phase P7 — StrategyConfig CRUD (implementation plan)

**Language:** English | [中文](./backend-expansion-plan-p7.zh.md)

> Status: **DRAFT v0.1** (2026-05-24). Detailed build plan for **P7** from the macro
> roadmap [backend-expansion-plan.md](./backend-expansion-plan.md). Self-contained —
> an implementer can execute it directly. Companion: [data-model.md §4.7](./data-model.md#47-strategyconfig-strategy-level-configuration),
> the **Account template** (`backend/src/trading_journal/schemas/account.py` +
> `api/accounts.py` + `tests/test_accounts.py`), and the just-shipped
> [backend-expansion-plan-p6.md](./backend-expansion-plan-p6.md) (for the
> get-or-create 200/201 pattern reused here).

## 1. Purpose & context

Turn the already-migrated `strategy_configs` table into a typed CRUD API: a
**per-user**, **per-strategy** configuration row holding the user's aggregate
exposure cap per strategy type (e.g., a $3,000 cap on aggregate
`iron_condor.max_risk_at_open`). No DB migration is needed (the table exists since
Phase 2's `0001_initial_schema`); P7 is purely Pydantic schemas + a router + tests.

### Settled decisions (do not re-derive)

- **Owner-scoped.** Every row has `user_id`; every endpoint filters on
  `current_active_user.id`. Cross-user access returns **404 (not 403)** — same
  rule as Account. The DB unique constraint is `(user_id, strategy_type)`, so the
  same `strategy_type` can coexist across different users.
- **Natural key in the URL = `strategy_type` (the enum value), not `id`.** The
  resource is bounded to ≤5 rows per user (one per `StrategyType` enum value), so
  the human-readable enum is the cleanest path key. The UUID `id` is still on the
  row (for future cross-refs) but never appears in URL paths.
- **Endpoints:**
  - `POST /strategy-configs` — **get-or-create on `(user_id, strategy_type)`**.
    Existing row → **200**; new → **201**. Matches the Instrument 200/201 pattern.
  - `GET /strategy-configs` — list all rows for the current user, ordered by
    `strategy_type`.
  - `GET /strategy-configs/{strategy_type}` — fetch one; 404 if absent.
  - `PATCH /strategy-configs/{strategy_type}` — partial update via
    `exclude_unset`; 404 if absent.
  - `DELETE /strategy-configs/{strategy_type}` — hard delete (no `archived_at`
    on the row); 404 if absent.
- **POST is get-or-create, not pure create.** On dup `(user_id, strategy_type)`
  the existing row is returned with **200** instead of 409. Rationale: matches
  Instrument's pattern (the user already saw it in F2 plan), and the frontend
  doesn't need a "does this exist?" pre-check. `PATCH` remains the way to mutate
  existing fields.
- **`strategy_type` is immutable.** It's the natural key — `PATCH` does not
  accept it; to "change strategy" the user deletes and creates a new row.
- **`updated_at` is server-managed.** SQLAlchemy `onupdate=func.now()` already
  handles it; the router never sets it explicitly.
- **No `created_at`.** Model has only `updated_at`
  ([data-model §4.7](./data-model.md#47-strategyconfig-strategy-level-configuration));
  the read schema reflects this.
- **Validation = format only.** `exposure_currency` matches `^[A-Z]{3}$`;
  `max_exposure` is `> 0` when present (nullable for "no cap yet"); `strategy_type`
  must be a valid `StrategyType` enum value (Pydantic enforces).

## 2. Scope

### In scope (this plan)

- `schemas/strategy_config.py` — `StrategyConfigCreate` / `StrategyConfigUpdate` /
  `StrategyConfigRead`
- `api/strategy_configs.py` — router (`POST` get-or-create, `GET` list, `GET /{type}`,
  `PATCH /{type}`, `DELETE /{type}`)
- Wire under `/strategy-configs` in `main.py` (final URL: `/api/strategy-configs`)
- `tests/test_strategy_configs.py`
- After backend is green: regenerate `frontend/src/api/schema.d.ts` (`npm run codegen`)
  + commit

### NOT in scope

- **Order-time enforcement** of the caps (i.e., refusing to create a Position when
  `sum(open.max_risk_at_open) + new ≥ max_exposure`). That belongs to P8/P9 or a
  later services layer. P7 only stores the cap.
- **Multi-currency cap aggregation.** Each row carries its own `exposure_currency`;
  no FX conversion. Matches [data-model §6](./data-model.md#currency-placement).
- **Audit history of cap changes.** `updated_at` overwrites in place; no event
  stream.
- **Soft-delete.** Not on the model.
- **Bulk endpoints.** With ≤5 rows per user, batching is unnecessary.

## 3. Files

```
backend/src/trading_journal/
├── schemas/strategy_config.py        ← NEW
├── api/strategy_configs.py           ← NEW
└── main.py                           ← CHANGED: include strategy_configs.router
backend/tests/test_strategy_configs.py ← NEW
frontend/src/api/schema.d.ts          ← REGENERATED at the end
```

## 4. Schema shapes (target)

```python
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trading_journal.models._enums import StrategyType

CURRENCY_PATTERN = r"^[A-Z]{3}$"


class StrategyConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_type: StrategyType
    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str = Field(pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # strategy_type is NOT updatable — it's the natural key in the URL.
    max_exposure: Decimal | None = Field(default=None, gt=0)
    exposure_currency: str | None = Field(default=None, pattern=CURRENCY_PATTERN)
    notes: str | None = None


class StrategyConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    strategy_type: StrategyType
    max_exposure: Decimal | None
    exposure_currency: str
    notes: str | None
    updated_at: datetime
```

**Note on `max_exposure: Decimal | None = Field(default=None, gt=0)`.** Pydantic v2
skips the `gt=0` constraint when the value is `None`, so this correctly accepts both
"no cap" (`null` or absent) and a positive cap; non-positive numbers still fail
validation.

**Note on `PATCH` semantics with nullable fields.** With `extra="forbid"` and
`model_dump(exclude_unset=True)`, `{}` is a no-op, `{"max_exposure": null}`
explicitly clears the cap, and `{"max_exposure": "5000"}` sets it. Same pattern as
F1's Account update.

## 5. Phased plan

Two sub-phases. P7 is small enough that the implementer may collapse them into one
session, but the split is preserved so each is independently committable. After
each: `uv run pytest -q && uv run ruff check . && uv run mypy src` — baseline is
**92 tests** after P6.

### P7.1 — Schemas + router + tests

**Goal.** Full CRUD pipeline working.

**Tasks.**

1. **`schemas/strategy_config.py`** — the three classes above. Place
   `CURRENCY_PATTERN` constant near the top (matching `schemas/account.py` and
   `schemas/instrument.py` conventions; do not introduce a shared constants
   module just for this).

2. **`api/strategy_configs.py`**:
   - `router = APIRouter(prefix="/strategy-configs", tags=["strategy-configs"])`
   - Private helper:
     ```python
     async def _get_owned_config(
         session: AsyncSession,
         user: User,
         strategy_type: StrategyType,
     ) -> StrategyConfig:
         stmt = select(StrategyConfig).where(
             StrategyConfig.user_id == user.id,
             StrategyConfig.strategy_type == strategy_type,
         )
         cfg = (await session.execute(stmt)).scalar_one_or_none()
         if cfg is None:
             raise HTTPException(status_code=404, detail="Strategy config not found")
         return cfg
     ```
   - `POST ""` → `StrategyConfigRead`, **get-or-create**. Take FastAPI
     `response: Response` to set **200 (existed) vs 201 (created)** dynamically:
     query first by `(user_id, strategy_type)`; if present, return existing
     unchanged + 200; else insert + 201.
   - `GET ""` → `list[StrategyConfigRead]`, owner-scoped, ordered by
     `strategy_type`.
   - `GET /{strategy_type}` → `StrategyConfigRead`; 404 via `_get_owned_config`.
   - `PATCH /{strategy_type}` → `StrategyConfigRead`; `model_dump(exclude_unset=True)`
     + `setattr` loop, same pattern as `update_account` in
     `api/accounts.py:95-108`. Commit + refresh. `updated_at` advances via
     `onupdate=func.now()` automatically.
   - `DELETE /{strategy_type}` → 204; `_get_owned_config` then
     `session.delete(cfg)` + commit. **Hard delete** — no `archived_at` field.
   - All routes depend on `current_active_user` + `get_session` (DI parity with
     Account router).

3. **`main.py`** — add `from trading_journal.api import ..., strategy_configs`
   and `api.include_router(strategy_configs.router)` in `create_app()` (matching
   how `accounts.router` and `instruments.router` are wired). Add a one-line
   comment: `# Domain: per-user StrategyConfig under /api/strategy-configs.`

4. **`tests/test_strategy_configs.py`** — reuse `auth_client` and
   `second_user_client` from `tests/conftest.py`.

**Manual verification.**
```bash
BASE=http://localhost:8000; JAR=cookies.txt
# (after register + login)

# 1. create wheel config → 201
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"50000","exposure_currency":"USD"}'
# → 201; max_exposure="50000.0000"; updated_at set

# 2. POST again with same strategy_type → 200, same id (get-or-create)
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"99999","exposure_currency":"EUR"}'
# → 200; ORIGINAL row returned (max_exposure still 50000) — POST does not overwrite

# 3. PATCH to update cap and add notes
curl -fsSi -X PATCH "$BASE/api/strategy-configs/wheel" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":"60000","notes":"Bull market only"}'
# → 200; max_exposure=60000, notes set, updated_at advanced

# 4. PATCH to clear cap (explicit null)
curl -fsSi -X PATCH "$BASE/api/strategy-configs/wheel" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":null}'
# → 200; max_exposure=null

# 5. List
curl -fsS "$BASE/api/strategy-configs" -b "$JAR"   # → [{wheel, ...}]

# 6. GET 404
curl -fsSi "$BASE/api/strategy-configs/pmcc" -b "$JAR"   # → 404

# 7. DELETE → 204; subsequent GET → 404
curl -fsSi -X DELETE "$BASE/api/strategy-configs/wheel" -b "$JAR"   # → 204
curl -fsSi "$BASE/api/strategy-configs/wheel" -b "$JAR"             # → 404
```

**Automated tests.**

| Test | Validates |
|---|---|
| `test_create_strategy_config_201` | POST returns 201 with serialized read shape |
| `test_create_returns_200_when_existing` | Second POST with same strategy_type → 200 + same id; **original values preserved** (POST is read-only on existing) |
| `test_create_rejects_unknown_strategy_type_422` | `strategy_type="cowabunga"` → 422 |
| `test_create_rejects_bad_currency_422` | `exposure_currency="usd"` → 422 |
| `test_create_rejects_nonpositive_max_exposure_422` | `max_exposure="-1"` → 422; `"0"` → 422 |
| `test_create_accepts_null_max_exposure` | omitting `max_exposure` or explicit `null` → 201 with stored null |
| `test_create_rejects_unknown_field_422` | extra fields rejected |
| `test_list_returns_only_current_user_rows` | user A creates wheel; user B's list is empty |
| `test_list_ordered_by_strategy_type` | rows returned in stable enum-value order |
| `test_get_by_strategy_type_200` | GET `/wheel` returns the row |
| `test_get_unknown_strategy_type_404` | GET unset strategy → 404 |
| `test_patch_updates_only_provided_fields` | PATCH with `{notes}` leaves max_exposure unchanged |
| `test_patch_clears_max_exposure_with_explicit_null` | PATCH with `{max_exposure: null}` clears |
| `test_patch_unknown_strategy_type_404` | PATCH a non-existent config → 404 |
| `test_patch_rejects_strategy_type_in_body_422` | sending `strategy_type` in PATCH body → 422 (extra="forbid") |
| `test_patch_advances_updated_at` | updated_at strictly increases after a successful PATCH |
| `test_delete_strategy_config_204` | DELETE returns 204; row gone |
| `test_delete_unknown_strategy_type_404` | DELETE missing → 404 |
| `test_requires_auth` | parametrized: POST/GET/PATCH/DELETE without cookie → 401 |
| `test_same_strategy_isolated_across_users` | user A creates `iron_condor`; user B creates `iron_condor`; both succeed, distinct rows, neither sees the other |

**Acceptance.** All tests pass; backend green; manual recipe matches.

### P7.2 — Regression + codegen + brief

**Goal.** Lock the baseline and propagate types to the frontend.

**Tasks.**

1. Backend: `uv run pytest -q && uv run ruff check . && uv run mypy src` — all
   green. Expected total: 92 (P6 baseline) + ~20 (P7 above) ≈ **112 tests**.
2. Frontend codegen: backend up on `:8000`, then `cd frontend && npm run codegen`
   → `git diff src/api/schema.d.ts` should show the new `StrategyConfigCreate /
   Update / Read` schemas plus `StrategyType` enum. `npm run build` passes;
   **commit the regenerated `schema.d.ts`**.
3. Walk the §7 curl recipe end-to-end.
4. Leave an implementation brief in `review-notes/p7_implementation_brief.md`
   (mirror the F1 / P6 briefs).
5. (Optional, if not bundled with F2) Land the CI codegen-freshness gate flagged
   in [backend-expansion-plan.md §5](./backend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked).

**Acceptance.** All green; `schema.d.ts` committed; recipe passes; brief in place.

## 6. Test approach

Same harness as P4 + P6 (`tests/conftest.py`: `auth_client`, `second_user_client`,
migrated tempfile SQLite, dependency-overridden session). StrategyConfig being
owner-scoped means the cross-user tests focus on **isolation** (same as Account),
**plus** confirming that the `(user_id, strategy_type)` unique constraint
**doesn't** prevent two different users from each having their own `iron_condor`
config. No new fixtures needed.

## 7. Manual verification reference (full P7 walkthrough)

```bash
BASE=http://localhost:8000; JAR=cookies.txt; rm -f "$JAR"
curl -fsS -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"correct horse battery"}' >/dev/null
curl -fsS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=alice@example.com&password=correct horse battery' -c "$JAR" >/dev/null

# create → 201
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"iron_condor","max_exposure":"3000","exposure_currency":"USD","notes":"MVP cap"}'

# idempotent get-or-create → 200, same id, original payload preserved
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"iron_condor","max_exposure":"99999","exposure_currency":"EUR"}'

# create a second strategy
curl -fsSi -X POST "$BASE/api/strategy-configs" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"strategy_type":"wheel","max_exposure":"50000","exposure_currency":"USD"}'

# list → 2 rows, ordered by strategy_type
curl -fsS "$BASE/api/strategy-configs" -b "$JAR"

# PATCH — partial update + explicit null
curl -fsSi -X PATCH "$BASE/api/strategy-configs/iron_condor" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"notes":"Updated for Q3"}'                                              # only notes changes
curl -fsSi -X PATCH "$BASE/api/strategy-configs/iron_condor" -b "$JAR" -H 'Content-Type: application/json' \
  -d '{"max_exposure":null}'                                                   # clears cap

# GET 404
curl -fsSi "$BASE/api/strategy-configs/pmcc" -b "$JAR"                          # → 404

# DELETE → 204
curl -fsSi -X DELETE "$BASE/api/strategy-configs/iron_condor" -b "$JAR"         # → 204
curl -fsSi "$BASE/api/strategy-configs/iron_condor" -b "$JAR"                   # → 404
```

## 8. Implementer quickstart

```bash
cd backend
# build P7.1 → P7.2; after each:
uv run pytest -q && uv run ruff check . && uv run mypy src
# run the API for manual checks:
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
```

After P7 is green, frontend F2 can immediately consume both P6 + P7 — see
[frontend-implementation-plan-f2.md](./frontend-implementation-plan-f2.md).

---

## Changelog

- **v0.1 (2026-05-24)** — Initial P7 build plan: owner-scoped CRUD with
  `strategy_type` as the path key and `POST` as get-or-create (200/201, matching
  P6 Instrument pattern). Two sub-phases: P7.1 schemas+router+tests, P7.2
  regression+codegen+brief.
