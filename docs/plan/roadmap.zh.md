# 当前路线图

> [English](roadmap.md) · **中文**

## 基线与调度

实现基线于 2026-11-02 建立，调度及文档验收于 2026-11-03 更新。既有 P/F 计划作为历史参考，不再作为活动清单。实现基线来自源码、迁移与 workflow 检查，不代表重新执行全部应用测试或完成用户运行验收。

已实现：账户／品种／策略配置、Position 与 Trade 流程、策略元数据、只追加计划、分币种仪表盘与账户筛选、明暗切换、生成 API 类型、单容器 Docker、先迁移后启动的 Compose、数据库 session 和自动持久化 token 签名密钥。

当前验证设施：后端 Ruff／strict mypy／pytest、经过迁移的隔离测试数据库、codegen 一致性、前端 Vitest／Vue Test Utils／jsdom 行为测试与类型／构建、有条件镜像构建。发布质量／镜像运行闸门仍由 REL-01 跟踪。支持 SQLite，PostgreSQL 等价性尚未证明。

**当前范围（2026-11-03）：** [M-OPT-01：期权选择与交易录入改进](milestone-option-entry.zh.md) 的 T1–T6 已实现，自动检查和独立评审通过；T7 阶段 B 应用文档／集成检查通过、独立评审中，用户功能验收待进行。设计文档阶段 A 及 DOC-01 已接受，免额外人工逐页审阅；不重复其验收。用户另行授权本轮实现、独立评审／修复和隔离验证，不授权 Git 写入、版本／标签发布或生产部署。

M-OPT-01 集中维护共享决策、完整任务卡和验收记录，涵盖过期期权显示／历史／分页、主标的过滤与上下文创建、FIX-01、UI-01／UI-02 及 QA-01 的有限切片。`ready` 表示契约已确认，不构成编码授权。

当前候选与分项证据见里程碑第 5.2 节；每步实现、自动检查、独立评审与用户验收分别记录。

## 工作队列

优先级仅建议顺序，不构成授权。P1 为数据正确性，P2 为流程／质量，P3 为需求澄清或可选扩展。队列状态在此维护，链接任务卡承载详细契约和证据。

| ID | 优先级 | 状态 | 范围／下一步 |
|---|---|---|---|
| DOC-01 | P2 | accepted | 2026-11-03 接受文档交付，免额外人工审阅；原针对性检查通过，不声称独立评审或运行走查 |
| [INS-01](milestone-option-entry.zh.md#t3) | P2 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| [INS-02](milestone-option-entry.zh.md#t4) | P2 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| [FIX-01](tasks/FIX-01.zh.md) | P1 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| [UI-01](milestone-option-entry.zh.md#t5) | P2 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| [UI-02](milestone-option-entry.zh.md#t6) | P2 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| UI-03 | P2 | needs-design | 按策略输入建议资金／风险／收益，定义公式、单位与手动覆盖 |
| UI-04 | P2 | needs-design | 多腿录入预填，尤其 Iron Condor；模板不改变记录意图 |
| UI-05 | P3 | needs-clarification | 筛选需求已澄清并归入 INS-01／INS-02，其他类型／显示反馈继续待澄清 |
| [QA-01](milestone-option-entry.zh.md#t1) | P2 | implemented | 本轮切片实现、自动检查与独立评审通过；用户功能验收待进行 |
| REL-01 | P2 | proposed | Tag 发布绑定准确源码的质量检查与镜像运行验证，需单独设计 |
| [MOPT-DOC](milestone-option-entry.zh.md#t7) | P2 | accepted | 阶段 A 设计文档已接受；阶段 B 应用集成 in-review；用户功能验收待进行 |

原始报告及 2026-06-02 事故保留在 [triage](../triage/improvements.md)。M-OPT-01 之外的工作实现前需有边界清晰的任务卡，不把队列当成已批准的实现批次。本里程碑明确延后 Position＋首批 Trade 单事务和已平仓记录的审计纠错路径。

## 延后产品方向

外部品种查询、行情／未实现盈亏、FX 换算、券商／CSV 导入、OAuth／MFA／审计扩展、Position 归档、Account 取消归档、标签／Greeks、i18n 和移动端仍未排期。规划前定义用户需求、数据源和验收。暗色模式和 codegen CI 已实现，不再列为延后项。

## 状态与验收

队列状态：`proposed`、`needs-design`、`needs-clarification`、`ready`、`in-progress`、`in-review`、`implemented`、`accepted`、`blocked`。`ready` 表示契约已确认，执行仍遵循用户指定范围。阻塞时记录原因和所需决策。

每轮实现分别记录实现、自动检查、独立评审、用户验收及候选身份和跳过项。实现完成、检查通过的任务仍可能等待评审或用户走查，不根据历史测试数量倒推旧验收。

同次更新任务与简洁队列，不再同步历史宏观计划状态。见[开发流程](../development.zh.md)和[任务模板](task-template.zh.md)。任务 ID 保持稳定，UI-01～UI-05 对应最初五项前端请求。

## 文档整理记录

DOC-01 是文档／元信息工作，不代表修复任何队列 bug 或交付功能。2026-11-02 完成文档地图、精简代理规则、开发指南、路线图、任务模板、FIX-01 草案、保留原问题的 triage、历史说明、README 入口和隔离走查。本地链接／锚点、双语结构／命令、Shell 语法、历史内容保留、空白、符号链接与忽略边界检查通过。实际解析走查 Compose，核对了独立挂载、源码上下文、loopback 绑定、HTTP cookie 和先迁移后启动依赖。没有构建或启动容器，未运行应用测试／构建或独立评审。2026-11-03 用户接受文档交付、免除额外人工逐页审阅，并要求收尾状态、提交和推送。这是带该省略项的文档接受，不代表运行走查或应用功能验收。
