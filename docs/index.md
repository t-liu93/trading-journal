# Documentation map

> **English** · [中文](index.zh.md)

## Current guidance

| Document | Responsibility |
|---|---|
| [Project README](../README.md) | Product overview and normal deployment |
| [Current roadmap](plan/roadmap.md) | Current scheduling, progress, and task contracts |
| [M-MCP-01 milestone](plan/milestone-mcp-entry.md) | Agent-entry contract, implementation/check/review/owner-acceptance status |
| [M-OPT-01 milestone](plan/milestone-option-entry.md) | Agreed option-selection/trade-entry design, task cards, and current implementation/check/review/owner-acceptance status |
| [v1.2.0 release notes](release-notes/v1.2.0.md) | MCP changes, migrations, client setup and validation scope |
| [Development guide](development.md) | Architecture, domain rules, commands, checks, review, and acceptance |
| [Task-card template](plan/task-template.md) | A self-contained contract for one reviewable step |
| [Walkthrough](walkthrough.md) | Disposable full-stack verification and owner actions |
| [Triage](triage/improvements.md) | Original symptoms and requests; Chinese-only |
| [Agent rules](../AGENTS.md) | Stable collaboration and authorization boundaries |

Read the roadmap and relevant task card before implementation. A proposed task does not start implementation or authorize deployment.

## Domain and historical references

- [Data model](design/data-model.md): original entities and reasoning. Current ORM models, migrations, API schemas and tests establish implemented behavior; task cards define intended changes.
- [Design archive index](design/README.md): historical P/F plans. Paths are preserved for existing links; their status labels, commands and test counts are historical.
- [Release notes](release-notes/): release-specific history. Follow today's README and walkthrough for setup rather than rewriting archived release instructions.
- Temporary implementation/review/walkthrough evidence belongs in local ignored `development-notes/<run-id>/`. Existing `review-notes/` remains local history. Do not move execution reports into tracked documentation.

## Maintenance

Progress lives in the roadmap/task card, stable working rules in the development guide, and original issue evidence in triage. Put each future milestone's shared decisions, atomic task sections and concise acceptance record in one EN/ZH document pair, rather than separate design/implementation/acceptance copies. Update both languages together.
