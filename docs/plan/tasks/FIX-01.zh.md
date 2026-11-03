# FIX-01 · Position 开仓日期一致性

> [English](FIX-01.md) · **中文**

## 身份与当前证据

- 队列状态：在[路线图](../roadmap.zh.md)中为 `proposed`。设计是待确认草案，尚未开始实现。
- 依赖：确认下方生命周期与空集策略，使用现有迁移测试 fixture。
- 目标：归档后重新录入纠错、补录更早 Trade 时，未平仓 Position 的持仓周期不再锚定过时首笔成交。
- 来源：[triage FIX-01](../../triage/improvements.md#fix-01--开仓日期不随后续成交变化维护)，含 2026-06-02 INTC 事故报告。
- 当前代码：[Position schema](../../../backend/src/trading_journal/schemas/position.py) 不允许 PATCH `opened_at`；[Trade API](../../../backend/src/trading_journal/api/trades.py) 的 PATCH 只改 notes，创建／归档后不维护 Position 日期；[平仓处理](../../../backend/src/trading_journal/api/positions.py) 推导平仓时间并冻结 P&L；[持仓天数](../../../frontend/src/utils/positionDerived.ts) 直接做日期相减。

这些是检查到的实现事实，不代表本轮已经执行复现。原始事故早于本任务卡。

## 提议契约

1. 未平仓 Position 成功新增／归档 Trade 后，从未归档 Trade 的 MIN(`executed_at`) 推导 `opened_at`。变更后的成交集合可见后，在同一事务更新日期；批量失败不得改变 Trade 或日期。
2. 没有有效 Trade 时保留上次 `opened_at`，不编造成交、不置 NULL。下一笔成功成交把该回退值替换为有效最小值。新建空 Position 在首笔成交前保留传入时间。
3. open→closed 时，有有效成交则先重算开仓时间，再推导平仓时间／冻结 P&L。保留现有默认平仓规则和显式平仓时间支持。最终 `closed_at < opened_at` 时返回 422，不部分修改状态／P&L，空集也覆盖。
4. 统一以 UTC 比较，不扩展为全库日期重构。仅修改 notes 不改变日期。
5. 保留归属校验、归档排除、已平仓 Trade 写锁、notes-only PATCH、只追加计划和财务公式。不新增 `opened_at` PATCH 或自动重新开仓。

**需确认的设计：** 空集回退、422 日期顺序校验、对已平仓历史的范围边界。本提案不是冻结契约。

## 范围、文件与步骤

潜在实现文件，编辑前再次核对：

- `backend/src/trading_journal/services/positions.py`：可复用的最早有效成交／日期逻辑。
- `backend/src/trading_journal/api/trades.py`：创建／归档的事务集成。
- `backend/src/trading_journal/api/positions.py`：平仓日期一致性和原子校验。
- `backend/tests/test_trades.py`、`backend/tests/test_positions.py`：有意义的 API 回归。
- `docs/development.md` 及中文镜像、triage、路线图：记录实际交付行为。

先以合成数据复现，再实现已确认规则，运行回归并检查仓位列表／详情和持仓天数。现有读取已暴露日期，预计不需要 schema 迁移或新增 API 字段；按最终设计核实，OpenAPI 变化时重新生成类型。

范围外：PATCH 修改 Trade 金额、放宽平仓写锁、自动平仓、Position＋首笔 Trade 单事务、通用前端测试工具、改真实数据库、自动回填已平仓旧记录、未请求的 UI 重做。既有错误平仓历史需单独确认的审计纠错路径，本任务不得悄悄改写。

## 验收与独立评审重点

- [ ] 新增更早成交时开仓时间前移；归档最早有效成交后取下一个最小值。
- [ ] 全部归档保留时间，重录后使用新成交时间。
- [ ] 多腿取有效最早时间，与输入顺序无关；一个无效腿使 Trade 和 Position 日期均不变。
- [ ] 归档成交不影响新日期或冻结 P&L。
- [ ] 平仓产生有序日期和正确 P&L，错误显式平仓时间原子拒绝；覆盖空仓位和不同 UTC offset。
- [ ] Notes-only PATCH 不改日期，访问他人记录与已平仓 Trade 写入保留现有错误。
- [ ] 新的列表／详情响应及刷新后的 UI 显示正确持仓周期。
- [ ] 保留已实现盈亏和审计行，不修改真实数据或改写已平仓历史。

计划检查：后端 Ruff、strict mypy、完整 pytest；改前端才跑前端构建，契约变化时检查生成类型。Reviewer 依据原始契约和实际候选 diff，独立核验 flush／事务顺序、UTC 比较、回滚、空集与平仓锁。

## 手动检查与执行记录

使用[一次性走查环境](../../walkthrough.zh.md)，创建合成股票 Position 和不同日期的两笔成交，归档较早一笔，刷新详情／列表，添加更早替代成交并平仓。验证日期顺序、预期现金流总额不变和持仓天数非负。通过已登录的 API 在一次性数据上验证错误显式平仓路径。

实现：未开始。针对本修复的自动检查：未运行。独立评审：未要求／未进行。用户验收：待进行。候选／diff 和本地执行报告：尚无。编写本卡不交付应用行为变化。
