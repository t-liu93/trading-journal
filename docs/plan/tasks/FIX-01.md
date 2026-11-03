# FIX-01 · Position opening-date consistency

> **English** · [中文](FIX-01.zh.md)

## Identity and authoritative contract

- Queue state: `accepted` in the [roadmap](../roadmap.md); the owner confirmed the M-OPT-01 design and subsequently authorized orchestrated application implementation on 2026-11-03.
- Goal: archive-and-replace correction or earlier-fill backfill must not anchor an open Position's holding period to an obsolete first fill.
- The full contract, dependencies, exact implementation files, acceptance, reviewer focus, checks and execution evidence now live in [M-OPT-01 T2](../milestone-option-entry.md#t2), together with shared decisions D07/D08 and the milestone walkthrough.
- This file remains the stable FIX-01 entry point. Do not maintain a competing implementation or acceptance checklist here.
- The implementation grant covered M-OPT-01 implementation, independent review, repair and disposable verification. After owner acceptance, a separate explicit grant covers milestone commits, push and v1.1.0 publication. Production deployment is a separate action.

## Incident and current evidence

The [original incident record](../../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护) reports the 2026-06-02 INTC Wheel Position. Its opening date was manually set to the earliest non-archived fill and an archived orphan Trade was removed. Realized P&L already excluded archived fills. This is historical evidence, not a recommended database repair procedure.

The current [Position date service](../../../backend/src/trading_journal/services/positions.py) aggregates the earliest active fill, and the [Trade API](../../../backend/src/trading_journal/api/trades.py) maintains opening dates in the same transaction as creation/archival. [Close handling](../../../backend/src/trading_journal/api/positions.py) validates final date ordering before applying fields and freezing P&L. The [Position schema](../../../backend/src/trading_journal/schemas/position.py) still rejects `opened_at` PATCH and Trade PATCH remains notes-only; there is no historical backfill. Technical candidates and separate acceptance dimensions are in M-OPT-01 T2/section 5.2.

## Design history and boundaries

The original standalone proposal was consolidated into M-OPT-01 after confirmation. The agreed contract preserves the last opening date for an empty active-fill set, replaces it when a new fill arrives, maintains dates transactionally and rejects reversed close dates with 422. M-OPT-01 also specifies validation of explicit amendments to an already-closed record's closing date, UTC handling and UI refresh. Refer to that contract for implementation details.

Closed-Trade locks, frozen P&L and retained audit history remain. Historical closed-record correction, automatic backfill, reopening and Position+first-Trade server atomicity remain outside this task. No real database is modified by this documentation change.

## Execution status

Implementation, automated checks and independent review passed for the M-OPT-01 T2 snapshot; owner step 5 is accepted. The later timezone-display correction passed frontend tests/build and real-browser checks without separate independent review. Update the milestone card and roadmap as these dimensions change, rather than duplicating their records here.
