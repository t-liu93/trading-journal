# Frontend Phase F2 — Instrument & StrategyConfig Frontend

**Language:** English | [中文](./frontend-implementation-plan-f2.zh.md)

> Status: **DRAFT v0.2** (2026-06-15). Companion to
> [frontend-expansion-plan.md](./frontend-expansion-plan.md) (macro roadmap),
> [frontend-implementation-plan-f1.md](./frontend-implementation-plan-f1.md) (F1
> pattern reference), [data-model.md](./data-model.md), and the backend plans
> [backend-expansion-plan-p6.md](./backend-expansion-plan-p6.md) (P6, done) +
> [backend-expansion-plan-p7.md](./backend-expansion-plan-p7.md) (P7). Iterate
> here before writing code.

## 1. Purpose

F2 sits on top of backend **P6** (Instrument CRUD, ✅ done) and **P7**
(StrategyConfig CRUD). It delivers:

- A browseable instrument catalog at `/instruments` (the user can list, filter,
  search, and create stock/option/forex instruments).
- A reusable `InstrumentPicker` typeahead component — **load-bearing for F3
  Position-create and F4 Trade-create**.
- A strategy exposure-caps settings page at `/settings/strategies` (per-user;
  enforced post-MVP when broker API integration arrives).
- A shared `CurrencySelect` component used by **every** currency field in F2 (and
  future F-phases) — so the dropdown + filterable + tag pattern from
  `AccountFormModal` stops being one-off and becomes the project-wide standard.

This is the smallest coherent UI iteration that completes both P6 and P7 — neither
of them justifies a standalone F-phase, but together they form the "everything
the user touches before opening a Position" surface.

F2 builds entirely on the F1 patterns (codegen → resource API module →
composable → form modal → view + AuthenticatedLayout slot). No fundamentally
new pattern is introduced; the only new shared building block is
`CurrencySelect`.

## 2. Scope

### In scope (this plan)

- **`src/api/instruments.ts`** — typed wrapper for the 3 P6 endpoints
  (`list`, `get`, `create`), returning the 200-vs-201 distinction so the caller
  can show "Selected existing" vs "Created" toasts.
- **`useInstruments()` composable** — list state with `kind` + `q` filters and
  debounced auto-refresh.
- **`CurrencySelect.vue`** — shared currency dropdown wrapping the preset list +
  `filterable` + `tag` pattern from `AccountFormModal`. Used by every currency
  field in F2 (stock currency, option currency, forex base_currency +
  quote_currency, exposure_currency).
- **`InstrumentForm.vue`** — kind-discriminated create modal covering stock /
  option / forex per the
  [P6 schemas](./backend-expansion-plan-p6.md#4-schema-shapes-target). Includes
  **forex symbol auto-split**: typing `EURUSD` auto-fills `base_currency=EUR`
  and `quote_currency=USD`, both still editable for non-standard pairs.
- **`InstrumentPicker.vue`** — reusable typeahead select bound to
  `useInstruments`, with optional `kind` constraint. **Select-only in F2** —
  inline-create is added in F3 when Position-create needs it.
- **`InstrumentsView.vue`** (`/instruments`) — list with kind filter + symbol
  search + row click expand for option/forex extension details + "+ New
  instrument" button.
- **`src/api/strategyConfigs.ts`** — typed wrapper for the P7 endpoints.
- **`useStrategyConfigs()` composable** — list state + `upsert(payload)`.
- **`SettingsStrategiesView.vue`** (`/settings/strategies`) — table with one
  row per `strategy_type` (5 rows: `wheel`, `iron_condor`, `pmcc`, `spot_stock`,
  `spot_forex`), inline edit of `max_exposure` + `exposure_currency` (via
  `CurrencySelect`) + `notes`.
- **`AuthenticatedLayout.vue`** — add `Instruments` and `Settings` to the
  header nav.
- **`DashboardView.vue`** — update placeholder cards: add "Instruments" and
  "Strategy caps" cards; shift "Positions / Trades / Dashboards" placeholders
  to reflect F3/F4/F5.
- **Codegen** — re-run `npm run codegen` after **both** P6 (already done) and
  P7 ship; commit the regenerated `schema.d.ts`.
- **Backend regression** — keep ≥92 backend tests + N P7 tests passing; ruff +
  mypy strict clean.
- **CI codegen gate (cross-cutting, optional bundle)** — see
  [expansion plan §5](./frontend-expansion-plan.md#5-cross-cutting--deferred-deliverables-tracked).

### Explicitly NOT in scope (deferred)

- **Migrating `AccountFormModal.vue` to use `CurrencySelect`** — trivial
  drop-in but deferred to a later cleanup pass; F2 should not touch
  already-shipped code.
- **Persisting user-typed currencies into the preset list.** F2 keeps the
  preset list hardcoded; new currencies typed via the `tag` prop exist only
  for the current form interaction. A "frequently-used currencies" cache is
  a possible follow-up if the re-typing proves annoying.
- **Inline-create on `InstrumentPicker`** — defer to F3 (the natural moment
  is when Position-create flow needs "type new symbol → create + select"
  without leaving the form).
- **External instrument lookup**
  ([P6.x](./backend-expansion-plan.md#p6x--external-instrument-validation-first-external-api-integration-optional-non-blocking))
  — deferred separately; lands as a small enhancement to picker when ready.
- **Position UI / Trade UI / Dashboards / Docker** — F3 / F4 / F5 / F6.
- **Instrument PATCH/DELETE UI** — backend has no PATCH/DELETE for instruments
  (they are globally shared and referenced by others' positions); UI matches.
- **Pinia store for instruments or strategy configs** — page-local composable
  as in F1; promote to a store only when ≥2 components need shared reactivity.
- **Bulk operations** on either resource.
- **Pagination** on `/instruments` — backend caps `limit=200`, more than
  enough for any MVP-scale catalog.
- **Frontend unit tests (Vitest)** — still no qualifying logic; backend
  pytest + `vue-tsc` + manual click-through suffice.

## 3. Tech additions

**None.** Same stack as F1.

If the typeahead search needs debouncing, write a 10-line `useDebouncedRef`
inline rather than pulling in `@vueuse/core` — keep the runtime dep list
minimal.

## 4. Directory structure changes

```
frontend/src/
├── api/
│   ├── schema.d.ts                  ← regenerated after P6 (done) + P7
│   ├── instruments.ts               ← NEW
│   ├── strategyConfigs.ts           ← NEW
│   ├── accounts.ts                  ← unchanged
│   ├── http.ts                      ← unchanged
│   └── types.ts                     ← unchanged
├── composables/
│   ├── useAccounts.ts               ← unchanged
│   ├── useInstruments.ts            ← NEW
│   └── useStrategyConfigs.ts        ← NEW
├── components/
│   ├── AuthenticatedLayout.vue      ← CHANGED: add Instruments + Settings nav
│   ├── AccountFormModal.vue         ← unchanged (CurrencySelect migration deferred)
│   ├── CurrencySelect.vue           ← NEW (shared)
│   ├── InstrumentForm.vue           ← NEW
│   └── InstrumentPicker.vue         ← NEW
├── router/
│   └── index.ts                     ← CHANGED: add /instruments + /settings/strategies routes
└── views/
    ├── LoginView.vue                ← unchanged
    ├── RegisterView.vue             ← unchanged
    ├── DashboardView.vue            ← CHANGED: placeholder cards updated
    ├── AccountsView.vue             ← unchanged
    ├── InstrumentsView.vue          ← NEW
    └── SettingsStrategiesView.vue   ← NEW
```

## 5. Build deliverables

The agent / implementer can sequence these however they like; the only hard
ordering is **`schema.d.ts` regenerated → API clients → composables →
`CurrencySelect` → other components → views → nav wiring**. Below is a
suggested order that keeps `npm run build` green after each chunk.

### 5.1 API clients

**`src/api/instruments.ts`** — typed wrapper around the 3 P6 endpoints.

```ts
import type { components } from './schema'
import { http } from './http'

export type Instrument        = components['schemas']['InstrumentRead']
export type StockCreate       = components['schemas']['StockCreate']
export type OptionCreate      = components['schemas']['OptionCreate']
export type ForexCreate       = components['schemas']['ForexCreate']
export type InstrumentCreate  = StockCreate | OptionCreate | ForexCreate
export type InstrumentKind    = components['schemas']['InstrumentKind']

export interface InstrumentCreateResult {
  instrument: Instrument
  existed: boolean   // true if backend returned 200 (already in catalog)
}

export const instrumentsApi = {
  list:   (params?: { kind?: InstrumentKind; q?: string; limit?: number }) =>
            http.get(`/instruments${buildQuery(params)}`) as Promise<Instrument[]>,
  get:    (id: string) => http.get(`/instruments/${id}`) as Promise<Instrument>,
  create: async (payload: InstrumentCreate): Promise<InstrumentCreateResult> => {
    const { data, status } = await http.postWithStatus('/instruments', payload)
    return { instrument: data as Instrument, existed: status === 200 }
  },
}
```

Add a small `postWithStatus` helper to `http.ts` if it doesn't already expose
the status code (current `http.post` likely returns parsed body only — extend
or wrap).

**`src/api/strategyConfigs.ts`** — typed wrapper for P7.

```ts
import type { components } from './schema'
import { http } from './http'

export type StrategyConfig       = components['schemas']['StrategyConfigRead']
export type StrategyConfigCreate = components['schemas']['StrategyConfigCreate']
export type StrategyConfigUpdate = components['schemas']['StrategyConfigUpdate']
export type StrategyType         = components['schemas']['StrategyType']

export const strategyConfigsApi = {
  list:   ()                                        => http.get('/strategy-configs') as Promise<StrategyConfig[]>,
  get:    (type: StrategyType)                      => http.get(`/strategy-configs/${type}`) as Promise<StrategyConfig>,
  upsert: (payload: StrategyConfigCreate)           => http.post('/strategy-configs', payload) as Promise<StrategyConfig>,
  update: (type: StrategyType, payload: StrategyConfigUpdate) =>
                                                       http.patch(`/strategy-configs/${type}`, payload) as Promise<StrategyConfig>,
  remove: (type: StrategyType)                      => http.delete(`/strategy-configs/${type}`) as Promise<null>,
}
```

Verify exact endpoint shapes against P7's `schema.d.ts` after P7 ships.

### 5.2 Composables

**`useInstruments()`** — mirrors `useAccounts`. State: `instruments`,
`loading`, `error`, `kindFilter`, `query`. Watch both filters; debounce
`query` changes (300 ms); call `refresh()` on watcher fire. Expose
`refresh()` for explicit re-fetch (after create).

**`useStrategyConfigs()`** — `configs`, `loading`, `error`, `refresh()`,
`upsert(payload)` (calls `strategyConfigsApi.upsert`, then `refresh()`).

### 5.3 `CurrencySelect.vue` (shared currency dropdown)

A thin shared wrapper around `<n-select>` that **every currency field in F2**
uses (and every currency field in future F-phases). The point is one preset
list, one set of UX behaviors, no drift between forms.

**Pattern.** Mirrors what `AccountFormModal.vue:30-39, 191-200` already
implements inline: preset list of common currencies + `filterable` for
typeahead + `tag` for accepting any user-typed code as a new selectable
value.

```vue
<script setup lang="ts">
defineProps<{
  modelValue: string | null
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void
}>()

const options = [
  { label: 'USD', value: 'USD' },
  { label: 'EUR', value: 'EUR' },
  { label: 'GBP', value: 'GBP' },
  { label: 'JPY', value: 'JPY' },
  { label: 'CHF', value: 'CHF' },
  { label: 'CAD', value: 'CAD' },
  { label: 'AUD', value: 'AUD' },
  { label: 'HKD', value: 'HKD' },
]

function handleUpdate(value: string | null) {
  emit('update:modelValue', value ? value.toUpperCase() : null)
}
</script>

<template>
  <n-select
    :value="modelValue"
    :options="options"
    :placeholder="placeholder ?? 'Select or type currency code'"
    filterable
    tag
    :disabled="disabled"
    @update:value="handleUpdate"
  />
</template>
```

**Why this exists.** The Account form (`AccountFormModal.vue`) already has
the preset list and the `tag` behavior inline. Extracting to a shared
component:
1. Keeps the preset list in one place — adding a new common currency later
   is one edit.
2. Forces every F2+ currency field to behave identically (dropdown +
   filterable + type-to-add) instead of degrading to a plain text input.

**The `tag` prop is what enables "type to add a new value".** Without
`tag`, `filterable` alone would only filter the existing 8 options. With
`tag`, the user can type e.g. `MXN` and have it become the selected value
even though it's not pre-listed. The typed value is in the dropdown for the
current form interaction only — not persisted into the preset list. See
§2 NOT in scope.

**Auto-uppercase.** `handleUpdate` upper-cases any user-typed value before
emitting, so a tag-typed `mxn` becomes `MXN` and the downstream `^[A-Z]{3}$`
regex validation passes. Preset values are already uppercase.

**Form-level validation.** The `^[A-Z]{3}$` regex still applies via the
parent form's `rules` config; the component itself doesn't enforce it
(the `tag` prop accepts any string by design). If the user types `US`
(only 2 chars), validation fails on submit just like F1.

**Used by.**
- §5.4 `InstrumentForm.vue` — stock `currency`, option `currency`, forex
  `base_currency`, forex `quote_currency`.
- §5.7 `SettingsStrategiesView.vue` — `exposure_currency`.

### 5.4 `InstrumentForm.vue` (create modal)

Single modal with a kind selector (`<n-segmented>` or `<n-radio-group>` at
top: Stock / Option / Forex). Form fields conditional on kind, per
[P6 schemas](./backend-expansion-plan-p6.md#4-schema-shapes-target):

- **stock**: `symbol` (required, max 64), `exchange` (optional, max 64),
  `currency` (required — use `CurrencySelect`).
- **option**: `underlying_symbol` (required), `underlying_exchange`
  (optional), `currency` (required — use `CurrencySelect`), `opt_type`
  (call / put), `strike` (decimal > 0), `expiry` (`<n-date-picker>`),
  `multiplier` (int > 0, default 100), `style` (american / european,
  default american).
- **forex**: `symbol` (e.g., `EURUSD`), `base_currency` + `quote_currency`
  (each via `CurrencySelect`; **auto-filled from `symbol` — see UX note
  below**), `pip_size` (decimal > 0), `contract_size` (optional decimal >
  0). **No `currency` field — backend derives it from `quote_currency`.**

All currency fields use `<CurrencySelect>` instead of a plain input. The
regex `^[A-Z]{3}$` is still declared in the form's `rules` so submit
validation catches anything the dropdown lets through (e.g., user typing
2 letters and tabbing away).

**Forex symbol auto-split.** When `symbol` matches `^[A-Za-z]{6}$` (exactly
6 letters), automatically populate `base_currency` ← first 3 chars
(uppercased) and `quote_currency` ← last 3 chars (uppercased). Concrete
implementation:

```ts
watch(() => model.value.symbol, (s) => {
  if (model.value.kind !== 'forex') return
  if (s && /^[A-Za-z]{6}$/.test(s)) {
    model.value.base_currency = s.slice(0, 3).toUpperCase()
    model.value.quote_currency = s.slice(3, 6).toUpperCase()
  }
})
```

Rules for the auto-split:
- Both `base_currency` and `quote_currency` remain **editable** via their
  `CurrencySelect` — override is allowed for any non-standard pair the
  auto-split doesn't capture.
- Show a small hint below the two fields:
  *"Auto-filled from symbol; edit if needed for non-standard pairs."*
- When `symbol` does NOT match the 6-letter pattern (too short, too long,
  contains non-letters), do **NOT** clear `base_currency`/`quote_currency`
   — the auto-split is opportunistic, not destructive.
- The auto-split runs every time `symbol` changes to a valid 6-letter form;
  if the user types `EURUSD`, then changes to `GBPJPY`, base/quote update
  to GBP/JPY. Re-overriding after that lets the user keep manual edits if
  they re-edit base/quote *after* the symbol settles.

Validation: same approach as F1 (validate-on-submit via
`formRef.value?.validate()`).

Submit handler:

```ts
const { instrument, existed } = await instrumentsApi.create(payload)
if (existed) message.info(`Instrument ${instrument.symbol} already exists — selected`)
else        message.success(`Created ${instrument.symbol}`)
emit('saved', instrument)
```

Props: `:show` (v-model), no `mode` (always create — instruments have no
edit contract). Emits: `@saved` with `Instrument`.

### 5.5 `InstrumentPicker.vue` (reusable typeahead)

```vue
<script setup lang="ts">
defineProps<{
  modelValue: string | null     // selected instrument UUID
  kind?: InstrumentKind          // restrict picker to one kind
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', id: string | null): void
}>()
</script>
```

Internal: `<n-select remote filterable :options :loading>` bound to a local
`useInstruments()` instance with the `kind` filter forwarded. On user input,
debounced (300 ms) fetch. Options rendered with `symbol` + small `kind`
badge + `exchange?` suffix.

**Select-only in F2.** No `allowCreate` prop yet; F3 will add it when
Position-create needs inline creation.

**Manual verification in F2** (since no production consumer):
- Temporarily import & render `<InstrumentPicker v-model="debugId" />` in
  `DashboardView` under a small "(debug, removed in F3)" card. Confirm
  typeahead + selection work. Remove the debug instance before commit if
  you prefer — at minimum the component must compile (`vue-tsc` via
  `npm run build`).
- Alternatively, exercise it on `InstrumentsView` as the search input
  (replaces the plain `<n-input>` filter). This is the cleaner option and
  validates the picker in the same surface that already exists.

### 5.6 `InstrumentsView.vue` (`/instruments`)

Layout (inside `<AuthenticatedLayout>`):

- **Page header** — title "Instruments", right-aligned "+ New instrument"
  button (opens `InstrumentForm` in create mode).
- **Filter strip** — `<n-select>` for kind (All / Stock / Option / Forex),
  bound to `useInstruments().kindFilter`; **`InstrumentPicker`** (or plain
  `<n-input placeholder="Search by symbol">`) bound to
  `useInstruments().query`. *Recommended: use `InstrumentPicker` here as
  the search widget to give it a real consumer in F2.*
- **`<n-data-table>`** — columns: kind badge, symbol, exchange, currency,
  created_at.
- **Row click → expand** showing the extension block for the row's kind:
  - `option`: `opt_type`, `strike`, `expiry`, `multiplier`, `style`
    (rendered as a small key/value grid).
  - `forex`: `base_currency`, `quote_currency`, `pip_size`, `contract_size`.
  - `stock`: nothing extra (base fields already in the row).
- **Empty state** — `<n-empty>` "No instruments yet — create one to get
  started" with a button that also opens the form.
- **No actions column** — backend has no PATCH/DELETE.

On `InstrumentForm @saved`: call `refresh()` and close the modal.

### 5.7 `SettingsStrategiesView.vue` (`/settings/strategies`)

Layout:

- **Page header** — title "Strategy exposure caps", brief helper paragraph:
  "Set a maximum aggregate `max_risk_at_open` per strategy. Manual for MVP —
  broker API integration will enforce these caps at order time."
- **`<n-data-table>`** — one row per known `strategy_type` (5 rows, ordered:
  `wheel`, `iron_condor`, `pmcc`, `spot_stock`, `spot_forex`). Pull the
  enum values from `schema.d.ts` to avoid hand-maintaining the list.
  Columns: strategy label, max_exposure, exposure_currency, notes,
  updated_at, actions.
- **Row data** — merge default (empty cap) rows with the user's existing
  configs returned by `useStrategyConfigs()`. Rows without a saved config
  show "—" in the cap columns and have an "Edit" action that opens an edit
  modal pre-filled with the strategy_type.
- **Inline edit via small modal** — `StrategyConfigForm`-shaped fields:
  `max_exposure` (decimal `<n-input-number>`), `exposure_currency` (via
  `CurrencySelect` — **not** a plain input), `notes` (textarea). Submit
  calls `useStrategyConfigs().upsert(payload)`; success/error toasts as in
  F1.

(If P7 lands with a substantially different API shape than assumed in §1,
adjust the form payload accordingly. The view structure should be
unaffected.)

### 5.8 `AuthenticatedLayout.vue` + `DashboardView.vue` updates

**`AuthenticatedLayout.vue`** — add two nav entries between Accounts and
the right-side email/logout:

```
Dashboard | Accounts | Instruments | Settings
```

`Settings` can be a single link to `/settings/strategies` for F2 (the only
settings page that exists). Promote to a dropdown menu later if more
settings arrive.

**`DashboardView.vue`** — update the placeholder cards. New
`<n-grid :cols="3">`:

| Card | Content | Link |
|---|---|---|
| Your accounts | count from `useAccounts` | `/accounts` |
| Instruments | count from `useInstruments` | `/instruments` |
| Strategy caps | "5 strategies tracked" or count from `useStrategyConfigs` | `/settings/strategies` |
| Positions (Phase F3) | disabled / depth=3 | none |
| Trades (Phase F4) | disabled / depth=3 | none |
| Dashboards (Phase F5) | disabled / depth=3 | none |

## 6. Codegen workflow

Same operational pattern as
[F1 §6](./frontend-implementation-plan-f1.md#6-codegen-workflow).

F2-specific reminders:
- `npm run codegen` must run **once after P6 ships** (already done in P6 —
  see [P6 commit history](./backend-expansion-plan-p6.md)) and **once
  after P7 ships**.
- The git diff after the P7 run should be small (a `StrategyConfigRead`,
  `StrategyConfigCreate`, `StrategyConfigUpdate`, and `StrategyType` enum,
  plus the 3–5 path entries).
- If the CI codegen gate (cross-cutting) lands as part of F2, the first PR
  that changes any backend schema after F2 will be the first time the gate
  trips.

## 7. Testing approach

Same as F0 / F1 — **no automated frontend tests in F2**. Backend pytest is
the regression guard. `npm run build` (`vue-tsc`) typechecks the frontend.

Backend regression remains the hard gate. Must stay green after every chunk
of F2 work.

## 8. Manual verification recipe

Run end-to-end against `uvicorn` + `npm run dev` after the full F2 surface
is built. Prerequisite: backend on `127.0.0.1:8000` with **both P6 and P7
deployed** and migrated; frontend on `localhost:5173`; SSH tunnel
forwarding both; fresh DB.

1. Register `alice@example.com` / `correct horse battery` → land on `/` →
   Dashboard shows 6 cards (Your accounts, Instruments, Strategy caps,
   Positions [F3] disabled, Trades [F4] disabled, Dashboards [F5]
   disabled), all counts = 0.
2. Header nav shows: Dashboard | Accounts | Instruments | Settings.
3. Click "Instruments" → `/instruments`; empty state visible.
4. Click "+ New instrument":
   - Default tab "Stock". Symbol field accepts `aapl`; **`currency` field
     opens a dropdown** with USD/EUR/GBP/JPY/CHF/CAD/AUD/HKD; pick `USD`;
     submit → toast "Created AAPL" (symbol auto-uppercased by backend);
     row appears.
   - Click again, tab to "Option". Fill underlying `AAPL` / exchange
     `NASDAQ` / **currency dropdown → USD** / put / strike `220` / expiry
     `2026-05-28` → submit → toast "Created AAPL" (or "Created option");
     a new option row appears.
   - Click the option row → expands to show opt_type, strike, expiry,
     multiplier=100, style=american.
   - Click again, tab to "Forex". Type `EURUSD` in `symbol` →
     **`base_currency` auto-fills to EUR and `quote_currency` auto-fills
     to USD**; both fields show the auto-fill hint; both remain editable
     dropdowns. Fill `pip_size` `0.0001` → submit → "Created EURUSD";
     row's currency column shows `USD` (derived from quote).
5. **Verify currency dropdown "tag" behavior.** Click "+ New instrument",
   Stock tab. In the `currency` field, type `mxn` (not in the preset
   list) → it appears as a selectable tag entry; select it; the value
   stored is `MXN` (auto-uppercased). Submit with symbol `WALMEX` →
   should succeed (backend accepts any 3-letter currency code matching
   `^[A-Z]{3}$`).
6. **Verify forex auto-split is editable.** Click "+ New instrument",
   Forex tab. Type `EURUSD` (auto-fills EUR/USD). Now change
   `base_currency` dropdown to `GBP` manually — auto-fill should NOT
   re-overwrite as long as you don't re-type the symbol. Change
   `symbol` to `AUDJPY` → base/quote re-fill to AUD/JPY (auto-split
   triggers on symbol change).
7. **Verify forex auto-split is opportunistic, not destructive.** Click
   "+ New instrument", Forex tab. Type a partial symbol like `EUR` (3
   chars) → base/quote stay empty (auto-split doesn't trigger).
   Continue typing `EURUSD` (now 6 chars) → base/quote fill correctly.
   Backspace symbol to `EURUS` (5 chars) → base/quote stay EUR/USD
   (auto-split doesn't clear).
8. Click "+ New instrument" → Stock tab, fill `AAPL` / `NASDAQ` / `USD`
   again → submit → toast "Instrument AAPL already exists — selected"
   (200 from get-or-create); row count unchanged.
9. Filter strip: select kind = Option → only the AAPL put row remains;
   clear → all rows visible.
10. Search input: type `aa` → 2 rows (AAPL stock + AAPL option) due to
    backend prefix search; clear → all rows.
11. Header → Settings → `/settings/strategies`. See 5 rows (wheel,
    iron_condor, pmcc, spot_stock, spot_forex), all caps showing "—".
12. Click Edit on `iron_condor`: set max_exposure `3000`, **open
    `exposure_currency` dropdown → select `USD`**, notes "MVP cap" →
    save → row updates; updated_at populated.
13. Refresh `/settings/strategies` → cap persists.
14. Edit `iron_condor` again, clear notes → save → notes column empty,
    updated_at advances.
15. Header → Dashboard → Strategy caps card link works; Instruments card
    shows count = ≥3; Your accounts card unchanged at 0.
16. Backend log throughout: only expected requests; no 500s, no
    IntegrityErrors.
17. (Cross-user, optional) Register `bob@example.com`, log in as bob,
    navigate to `/instruments` → see same rows (instruments are
    **global**,
    [P6 settled](./backend-expansion-plan.md#6-open-design-decisions)).
    `/settings/strategies` → empty (configs are per-user).
18. (Optional sanity) DB check:
    ```bash
    sqlite3 backend/dev.db "SELECT kind, symbol FROM instruments ORDER BY symbol"
    # Expected: AAPL stock, AAPL option, EURUSD forex, WALMEX stock (from step 5)
    sqlite3 backend/dev.db "SELECT strategy_type, max_exposure FROM strategy_configs WHERE user_id IN (SELECT id FROM users WHERE email='alice@example.com')"
    # Expected: iron_condor | 3000.0000
    ```

## 9. After F2

Once F2 ships, the next iteration is
[F3 — Position CRUD + detail page](./frontend-expansion-plan.md#f3--position-crud--detail-page-with-strategy-meta-tabs--plan-tab),
which consumes backend P8 + P10 + P11. F3 will:

- Add `allowCreate` to `InstrumentPicker` so Position-create can
  inline-create underlying instruments without leaving the form.
- Build `PositionFormModal` using the picker for `primary_instrument_id`,
  and using `CurrencySelect` for any currency-typed fields.
- Build `PositionDetailView` with the Overview / Meta / Plan tab strip;
  Trades tab is a placeholder until F4.
- Add wheel/PMCC strategy-meta sub-forms (rendered conditionally on
  `strategy_type`).
- Add TradePlan revision append form + history table.

If the CI codegen gate wasn't bundled with F2, land it as the first task
of F3.

A small follow-up worth tracking: migrate `AccountFormModal.vue` to use
the new `CurrencySelect` component, eliminating the inline duplicate of
the preset list and `tag` behavior. Not in F2 scope but trivial when
picked up.

---

## Changelog

- **v0.2 (2026-06-15)** — Added **`CurrencySelect.vue` shared component**
  and the requirement that every currency field in F2 use it (closes a
  v0.1 gap where currency fields were spec'd only as `^[A-Z]{3}$`-validated
  text inputs, not dropdowns — diverging from the Account form's existing
  pattern). Added **forex symbol auto-split** to `InstrumentForm`:
  6-letter symbols auto-populate `base_currency` and `quote_currency` while
  both remain editable for non-standard pairs. Renumbered §5.3 → §5.4 etc.
  to insert the new `CurrencySelect` section. Manual verification recipe
  extended with three new steps (dropdown `tag` behavior; auto-split
  override; auto-split opportunism). Tracked `AccountFormModal`
  migration to `CurrencySelect` as a deferred follow-up.
- **v0.1 (2026-05-24)** — Initial F2 plan under the v0.2 expansion-plan
  rescope. Covers P6 (done) + P7 (next) — Instrument browse + reusable
  picker + strategy exposure-caps settings, plus nav + dashboard updates.
  Inline-create on picker explicitly deferred to F3. No new dependencies;
  no internal sub-phases.
