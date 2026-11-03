# FIX-01 · Position 开仓日期一致性

> [English](FIX-01.md) · **中文**

## 身份与权威契约

- 队列状态：在[路线图](../roadmap.zh.md)中为 `implemented`，用户于 2026-11-03 确认 M-OPT-01 设计，随后授权编排实现应用。
- 目标：归档后重录纠错、补录更早成交时，不让未平仓 Position 的持仓周期锚定过时首笔成交。
- 完整契约、依赖、准确文件清单、验收、评审重点、检查和执行证据集中在 [M-OPT-01 T2](../milestone-option-entry.zh.md#t2)，同时参照其中共享决策 D07／D08 和里程碑走查。
- 本文件保留 FIX-01 稳定入口，不另行维护竞争的实现或验收清单。
- 当前执行授权包括 M-OPT-01 实现、独立评审、修复及一次性环境验证；不授权 Git 写入、发布或生产部署。

## 事故与当前证据

[原始事故记录](../../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护)记载 2026-06-02 的 INTC Wheel Position，曾手动将开仓日期设为非归档成交最早时间，并删除归档孤儿 Trade；当时已实现盈亏已经正确排除归档成交。这是历史证据，不是建议复制的数据库修复步骤。

原始基线体现的未修复行为：[Position schema](../../../backend/src/trading_journal/schemas/position.py)不允许 PATCH `opened_at`；[Trade API](../../../backend/src/trading_journal/api/trades.py)只允许修改 notes，创建／归档后不维护 Position 日期；[平仓处理](../../../backend/src/trading_journal/api/positions.py)推导平仓日期并冻结盈亏；[持仓天数](../../../frontend/src/utils/positionDerived.ts)直接相减。源码检查不代表重新执行了复现。

## 设计历史与边界

原独立草案确认后整合到 M-OPT-01。已确定的契约在有效成交空集时保留开仓日期，下笔成交替换回退值，同事务维护日期，并以 422 拒绝倒置的平仓日期。M-OPT-01 同时明确已平仓记录显式修改平仓日期的校验、UTC 处理和界面刷新；实现细节以该契约为准。

保留已平仓 Trade 写锁、冻结盈亏和审计历史。已平仓历史纠错、自动回填、重新开仓和 Position＋首批 Trade 服务端单事务仍在范围外。本文档变更不修改真实数据库。

## 执行状态

M-OPT-01 T2 快照的实现、自动检查与独立评审已通过；用户功能验收仍待进行。后续在里程碑卡和路线图同步各维度状态，不在这里重复维护记录。
