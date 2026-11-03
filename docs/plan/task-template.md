# Task-card template

> **English** · [中文](task-template.zh.md)

Use this contract for a standalone task or as an atomic section within one milestone document. Replace placeholders before marking a task ready. The [roadmap](roadmap.md) owns scheduling; this card owns detailed scope and acceptance. A proposed card is not implementation authorization.

## Identity and prerequisites

- ID/title:
- Queue state: link to the roadmap row.
- Design: draft / agreed, with the actual confirmation recorded.
- Depends on:
- Goal: the user-visible problem and resulting behavior.
- Current evidence: relevant source, tests and original issue, separating inspected facts from assumptions.

## Scope and contract

- Inputs, outputs and API/data/UI behavior; compatibility and failure behavior.
- In scope:
- Out of scope:
- Files: exact paths and intended create/modify/delete actions; include necessary regression tests. Escalate material scope changes, not routine implementation choices.
- Migration/data handling: targets, defaults, rollback/reconciliation and disposable verification data; explicitly say when none is needed.
- Implementation steps: ordered, independently checkable actions. Include frontend/backend integration in the same outcome when necessary.

## Acceptance and reviewer checklist

- [ ] Concrete observable outcome:
- [ ] Negative/boundary cases:
- [ ] Relevant checks and expected results:
- [ ] No unrelated behavior, ownership or history regression:
- [ ] Required generated types/docs synchronized:

Reviewer focus: realistic correctness, security, data and compatibility risks tied to this task. State what demonstrates a blocking finding; keep optional improvements separate. Specify independent checks rather than asking the reviewer to trust an implementation report.

## Candidate and evidence

- Candidate: base/head SHAs, or reproducible diff/snapshot including relevant untracked files.
- Implementation: not started / complete / partial, with scope.
- Automated checks: not run / passed / failed, with actual commands and omissions.
- Independent review: not requested / pending / passed / findings; identify the reviewed candidate.
- Owner acceptance: pending / accepted / accepted with explicit omissions; record actual confirmation and untested paths.
- Local evidence: run directory/report identifiers; no links from stable guidance to ignored files required for understanding the contract.

Keep detailed logs and reports in ignored `development-notes/<run-id>/`. Keep only concise evidence outcomes here. A passed review covers its recorded candidate; later edits need verification of the changed scope.

## Manual walkthrough and cleanup

Record a disposable environment, synthetic inputs, exact startup/actions, expected observations and cleanup of only this task's resources. Describe prerequisites and checks to skip only with a recorded exception. Do not run the steps against production.

## Decisions and completion

Record material decisions, unresolved questions and explicit exceptions. Synchronize the roadmap after implementation/check/review/human-acceptance changes; do not mark all four complete from a single successful build. Use the [development guide](../development.md) and invoked skill for execution/authorization rules rather than duplicating them here.
