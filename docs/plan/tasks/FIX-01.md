# FIX-01 · Position opening-date consistency

> **English** · [中文](FIX-01.zh.md)

## Identity and authoritative contract

- Queue state: `in-progress` in the [roadmap](../roadmap.md); the owner confirmed the M-OPT-01 design and subsequently authorized orchestrated application implementation on 2026-11-03.
- Goal: archive-and-replace correction or earlier-fill backfill must not anchor an open Position's holding period to an obsolete first fill.
- The full contract, dependencies, exact implementation files, acceptance, reviewer focus, checks and execution evidence now live in [M-OPT-01 T2](../milestone-option-entry.md#t2), together with shared decisions D07/D08 and the milestone walkthrough.
- This file remains the stable FIX-01 entry point. Do not maintain a competing implementation or acceptance checklist here.
- Current execution authorization covers M-OPT-01 implementation, independent review, repair and disposable verification. Git writes, publication and production deployment are not authorized.

## Incident and current evidence

The [original incident record](../../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护) reports the 2026-06-02 INTC Wheel Position. Its opening date was manually set to the earliest non-archived fill and an archived orphan Trade was removed. Realized P&L already excluded archived fills. This is historical evidence, not a recommended database repair procedure.

Current source establishes the unfixed behavior: [Position schema](../../../backend/src/trading_journal/schemas/position.py) rejects `opened_at` PATCH; [Trade API](../../../backend/src/trading_journal/api/trades.py) supports notes-only PATCH without maintaining Position dates on create/archive; [close handling](../../../backend/src/trading_journal/api/positions.py) derives a closing date and freezes P&L; [holding-day display](../../../frontend/src/utils/positionDerived.ts) subtracts recorded dates. Source inspection is not a freshly executed reproduction.

## Design history and boundaries

The original standalone proposal was consolidated into M-OPT-01 after confirmation. The agreed contract preserves the last opening date for an empty active-fill set, replaces it when a new fill arrives, maintains dates transactionally and rejects reversed close dates with 422. M-OPT-01 also specifies validation of explicit amendments to an already-closed record's closing date, UTC handling and UI refresh. Refer to that contract for implementation details.

Closed-Trade locks, frozen P&L and retained audit history remain. Historical closed-record correction, automatic backfill, reopening and Position+first-Trade server atomicity remain outside this task. No real database is modified by this documentation change.

## Execution status

Implementation in progress; application checks and independent review pending; owner feature acceptance pending. Update the milestone card and roadmap as these dimensions change, rather than duplicating their records here.
