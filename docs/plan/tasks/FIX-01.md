# FIX-01 · Position opening-date consistency

> **English** · [中文](FIX-01.zh.md)

## Identity and current evidence

- Queue state: `proposed` in the [roadmap](../roadmap.md). Design is a draft for confirmation; implementation has not started.
- Dependencies: agree the lifecycle and empty-set policy below; use the existing migrated test fixtures.
- Goal: archive-and-replace correction or backfilling an earlier Trade must not leave an open Position's holding period anchored to an obsolete first fill.
- Source issue: [triage FIX-01](../../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护), including the reported 2026-06-02 INTC incident.
- Current code: [Position schema](../../../backend/src/trading_journal/schemas/position.py) does not allow patching `opened_at`; [Trade API](../../../backend/src/trading_journal/api/trades.py) allows notes-only PATCH and does not update Position dates after create/archive. [Close handling](../../../backend/src/trading_journal/api/positions.py) derives close time and freezes P&L. [Holding days](../../../frontend/src/utils/positionDerived.ts) subtracts the recorded dates directly.

These are inspected implementation facts, not a freshly executed reproduction. The original incident predates this card.

## Proposed contract

1. After a successful Trade create or archive on an open Position, derive `opened_at` from MIN(`executed_at`) of its non-archived Trades. Apply the date update in the same transaction, after the changed Trade set is visible. A failed batch must change neither Trades nor dates.
2. If no active Trades remain, preserve the last recorded `opened_at` rather than inventing a fill or setting NULL. The next successful fill replaces that fallback with the active minimum. A newly created empty Position keeps its supplied timestamp until a fill exists.
3. On open→closed, recompute the opening date when active fills exist before deriving close time/freezing P&L. Keep the current default close-time rule and explicit-close-time support. Reject a resulting `closed_at < opened_at` with 422 and no partial state/P&L changes, including the empty-set case.
4. Compare timestamps consistently in UTC; do not broaden this into a repository-wide date refactor. Notes-only edits must not change dates.
5. Preserve ownership, archive exclusion, closed Trade locks, notes-only PATCH, append-only plans and existing financial formulas. Do not add an `opened_at` patch API or automatic reopening.

**Design confirmation needed:** accept the empty-set fallback, 422 date-order validation, and the boundary around already-closed history. This proposal is not a frozen contract.

## Scope, files and steps

Potential implementation files, to verify before editing:

- `backend/src/trading_journal/services/positions.py`: reusable earliest-active-fill/date logic.
- `backend/src/trading_journal/api/trades.py`: transactional create/archive integration.
- `backend/src/trading_journal/api/positions.py`: close-date consistency and atomic validation.
- `backend/tests/test_trades.py`, `backend/tests/test_positions.py`: meaningful API regressions.
- `docs/development.md` and Chinese mirror, triage and roadmap: record the behavior actually delivered.

First reproduce with synthetic data, then implement the agreed rules, run regressions and inspect the position list/detail plus holding days. Existing reads already expose the dates; no schema migration or API field addition is expected. Verify that assumption against the final design; regenerate types if OpenAPI changes.

Out of scope: changing Trade monetary data via PATCH, relaxing closed locks, automatic closing, one-transaction Position+first-Trade creation, generic frontend test tooling, live database edits, automatic backfill of old closed records, and unrequested UI redesign. Existing invalid closed history needs a separately agreed audited correction path; this task must not silently rewrite it.

## Acceptance and independent reviewer focus

- [ ] Earlier fill creation moves opening time earlier; archiving the earliest active fill moves it to the next minimum.
- [ ] Archive all → preserve timestamp; replacement fill → use its date.
- [ ] Multi-leg batches use the earliest active timestamp regardless of input order; one invalid leg leaves Trades and Position dates unchanged.
- [ ] Archived fills never determine the new dates or frozen P&L.
- [ ] Close derives ordered dates and correct P&L; invalid explicit close time rejects atomically. Cover an empty Position and differing UTC offsets.
- [ ] Notes-only PATCH does not change dates; another user's records and closed Trade writes retain existing errors.
- [ ] Fresh Position list/detail responses and the UI show the corrected holding period after refresh.
- [ ] Existing realized P&L and audit rows are retained; no live-data or historical closed-record rewriting.

Checks planned: backend Ruff, strict mypy and full pytest; frontend build if frontend changes; generated-type inspection if the contract changes. Reviewer independently inspects flush/transaction ordering, UTC comparison, rollback, empty sets and close locks using the original contract and actual candidate diff.

## Manual check and execution record

Use the [disposable walkthrough environment](../../walkthrough.md), create a synthetic stock Position with two distinct fill dates, archive the earlier fill, refresh the detail/list, add an even earlier replacement and close. Verify ordered dates, unchanged expected cash-flow totals and nonnegative days held. Test the invalid explicit-close path via the authenticated API on disposable data.

Implementation: not started. Automated checks: not run for this proposed fix. Independent review: not requested/performed. Owner acceptance: pending. Candidate/diff and local execution reports: none yet. No application behavior changes are delivered by writing this card.
