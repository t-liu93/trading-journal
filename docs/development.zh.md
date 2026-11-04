# 开发指南

> [English](development.md) · **中文**

## 架构与当前契约

后端位于 `backend/src/trading_journal/`：`models/` 放 ORM 持久化，`schemas/` 放 API 校验／序列化，`services/` 放可复用业务逻辑，`api/` 负责 HTTP 编排，`auth/` 负责鉴权。前端 `frontend/src/` 分开组织 API 客户端、composable、store、view、component、utility 和路由。

后端采用 FastAPI、异步 SQLAlchemy 2、Alembic、FastAPI Users、Pydantic Settings 和 uv；前端采用 Vue 3/TypeScript、Vite、Pinia、Vue Router、Naive UI 和 ECharts。SQLite 是默认数据库；PostgreSQL 可移植性是目标，没有当前已验证部署记录。业务路由用 `/api/*`，健康检查为 `/api/health`，OpenAPI 为 `/openapi.json`。生产环境在 API／文档路由之外提供 SPA；Vite 把 `/api` 代理到 `127.0.0.1:8000`。`npm run codegen` 默认读取该 OpenAPI 地址，也可通过 `OPENAPI_URL` 指定其他后端。

除非任务明确修改，否则保留以下契约：

- 权威财务值使用后端 `Decimal` 和现有 SQL `Numeric` 精度。Trade 现金流为 `sign(action) × price × quantity × multiplier − commission − fees`。前端预览、持仓天数、ROI 和年化 ROI 仅展示，不同币种分开。
- 按登录用户校验所有权，Trade 经 Position 判断归属，访问他人资源返回 404。Instrument 是按自然键 get-or-create 的共享参考数据。
- Trade DELETE 是归档，统计排除归档行。PATCH 只接受 notes；未平仓仓位中其他字段纠错需归档后重新录入。已平仓仓位拒绝 Trade 写入，不能重新打开；没有支持的取消归档端点。
- 期权按当前 UTC 日期过期（`expiry < today`）。产品列表与选择器默认隐藏过期合约；Instrument API 为兼容旧客户端默认 `include_expired=true`。全部筛选先于排序／分页执行。`option_underlying_id` 仍只限制期权行；`related_underlying_id` 仅返回精确股票 ID 及其期权行。Instruments 管理页和选择器每次显示 50 条，并多请求一条判断是否有下一页；API 接受任意非负 `offset` 和 1–200 的 `limit`。已选历史 Instrument 仍按 ID 解析。过期开关在当前表单／picker 会话内保留；新 Trade 表单会话恢复默认隐藏状态。Primary Instrument 解析到股票时，Trade 腿候选仅包括该股票及其期权；外汇或未选择 Primary 时保留通用候选。管理页和 Primary Instrument 选择器不加关联范围。上下文创建期权会继承并锁定 underlying，匹配关系按 underlying ID 判断。切换 Primary 会清空 picker 搜索并使旧请求失效，即使新旧 Primary 解析到同一股票也一样。没有股票上下文的一般 Trade 表单仍可录入股票与外汇。
- 未平仓 Position 的 `opened_at` 是有效成交最早时间（`MIN(executed_at)`）。成功创建或归档 Trade 后刷新日期；若全部成交归档，保留上次开仓日期，直到有新有效成交。新建空 Position 在首笔成交前保留输入日期。新成交时间在持久化与排序前统一为 UTC；旧的 naive 时间解释为 UTC，不回填历史数据。 Position／Trade API 客户端先将无时区响应明确为 UTC，再用于浏览器本地显示与日期计算；已有显式偏移保持不变。日期时间选择器使用浏览器本地时间。
- 平仓冻结已实现盈亏。平仓时，有效成交会重新计算 `opened_at`；未指定平仓时间则取最后一笔有效成交，空集合使用当前 UTC 时间。开平仓同一时刻允许；平仓早于开仓时原子拒绝，包括修改已平仓 Position 的时间。其他字段编辑不会自动修复或拒绝历史无效日期。
- 多腿 Trade 写入保持原子性。Position 与首笔 Trade 当前由前端两次请求完成，含部分失败恢复，不是后端同事务。
- Trade 备注以纯文本放在对应成交行紧邻的下一行，保留换行并自动折行。由对应 Trade 的操作编辑备注；Ctrl/Command+Enter 或 Save 提交，Cancel 撤销。成交表单标签在输入框上方，帮助／错误在下方；600px 以上双列、以下单列；Instrument 与 Notes 跨整行。此布局范围限于受影响表单。
- TradePlan 只追加，保留修订唯一约束和重试。任何 Trade（包括归档历史）或计划修订都阻止删除 Position。
- 已发布 schema 变化新增 Alembic 迁移。测试将迁移后的模板复制为每个测试独立的数据库。
- 自动持久化的 `app_config` 密钥用于 token 签名，session 使用数据库不透明 token，无需运维提供 `COOKIE_SECRET`。
- MCP 以 Streamable HTTP 挂载在同一 app 的精确 `/api/mcp` 路径，使用 Bearer 凭证。共八个工具：`get_context`、`list_accounts`、`search_instruments`、`list_positions`、`get_position`、`list_trades`、`prepare_entry`、`commit_entry`。`read` 凭证可调用前六个；`entry` 可调用全部八个。每个客户端使用独立凭证，默认 90 天过期，明文只在“设置 → MCP”创建时返回一次。
- MCP 录入使用不可变预览草稿，待提交草稿 24 小时过期。同一凭证、`request_id` 和未改变的请求重试会返回同一草稿；修改内容会冲突。提交重试只使用原 `draft_id`，并返回已保存结果。MCP 路径的新 Position 与首批 Trade 原子提交；网站仍是两次请求并带部分失败恢复，不要把网站录入说成原子操作。
- MCP 查询和写入执行所有权检查，Trade 通过 Position 校验归属；其他用户的记录不可访问。录入保留现有账户可用性、币种分离、有效成交日期和已平仓 Position 的 Trade 写入锁。Instrument 搜索默认包含过期期权，以支持补录。它不提供平仓／重新开仓／归档／纠错工具。
- `JOURNAL_TIMEZONE` 默认 `UTC`，且必须是已安装的 IANA 时区。MCP 无时区偏移的录入时间使用单腿时区或该默认值；显式偏移会保留，DST 重复／不存在的本地时间要求显式偏移。持久化仍为 UTC。`MCP_ALLOWED_HOSTS` 与 `MCP_ALLOWED_ORIGINS` 为 JSON 数组；应用默认覆盖 localhost／loopback。没有 `Origin` 的请求允许通过。HTTPS 反代需允许准确外部 Host（有端口时包含端口）和 Origin，并原样代理 `/api/mcp`，保留 `Authorization`、`Host` 和 MCP 协议头。app 发布端口继续绑定 loopback。

[M-MCP-01 里程碑](plan/milestone-mcp-entry.zh.md) 记录完整契约以及实现、检查、评审、用户验收的独立状态。SDK 协议检查不代表真实 Codex/Hermes 客户端验收。网站 Cookie 鉴权、REST 时间解释和 Position／首笔 Trade 两请求恢复流程保持不变。

## 命令与环境

当前 CI／Docker 使用 Python 3.12、Node 22。变更版本时核对依赖清单、锁文件、`Dockerfile` 和 `.github/workflows/ci.yml`。

| 目录 | 命令 | 用途 |
|---|---|---|
| `backend/` | `uv sync --frozen` | 锁定的开发依赖 |
| `backend/` | `uv run ruff check .` | Lint |
| `backend/` | `uv run mypy --strict src` | 类型检查 |
| `backend/` | `uv run pytest` | 隔离后端测试 |
| `backend/` | `uv run alembic upgrade head` | 迁移配置指定数据库，先检查目标 |
| `backend/` | `COOKIE_SECURE=false uv run uvicorn trading_journal.main:app --reload` | 本地 HTTP 后端 |
| `backend/` | `JOURNAL_TIMEZONE=Europe/Amsterdam uv run uvicorn trading_journal.main:app --reload` | MCP 默认录入时区示例（本地 HTTP 还需搭配隔离数据库和 `COOKIE_SECURE=false`） |
| `frontend/` | `npm ci` | 锁定依赖，保留 `.npmrc` |
| `frontend/` | `npm run dev` | Vite，`http://localhost:5173` |
| `frontend/` | `npm run build` | 类型检查与生产构建 |
| `frontend/` | `OPENAPI_URL=http://127.0.0.1:<port>/openapi.json npm run codegen` | 从指定后端生成已提交类型，默认端口为 8000 |
| `frontend/` | `npm run test` / `npm run test:watch` | Vitest 单次运行／监视模式 |

一次性 Compose 验证以及期权／日期／备注集成走查看[走查指南](walkthrough.zh.md)。模板在 `example/`；被忽略的根目录 Compose 是本地工作副本，可能指向真实记录，不覆盖或复用来验证。Compose 先跑 `migrate` 再跑 `app`，迁移失败阻止启动。

需要热重载时，在 `backend/` 运行：

```bash
uv sync --frozen
export TJ_DEV_DIR="$(mktemp -d /tmp/tj-dev-XXXXXX)"
export DATABASE_URL="sqlite+aiosqlite:///$TJ_DEV_DIR/dev.db"
export COOKIE_SECURE=false
uv run alembic upgrade head
uv run uvicorn trading_journal.main:app --reload
```

另一个终端在 `frontend/` 运行 `npm ci` 和 `npm run dev`，统一用 `localhost`。选择空闲端口，Vite／codegen 默认后端为 8000。只停自己启动的进程，之后删除本轮创建的临时目录。不通过重置已有数据库解决 session 问题。

## 任务、验证与验收

阅读[路线图](plan/roadmap.zh.md)及按[任务模板](plan/task-template.zh.md)编写的契约。每步交付小而可评审的用户结果，必要时同时覆盖前后端集成。进入 `ready` 前解决实质决策，草案不授权实现。未来每个里程碑的共享决策、原子任务与简洁验收放在一个文档对中。

分别记录实现、自动检查、独立评审、用户验收四个维度，同次更新任务记录和简洁路线图行。`implemented` 不等于 `accepted`，明确记录跳过路径和已批准例外。历史 P/F 计划不再承担状态追踪。

| 改动 | 相关验证 |
|---|---|
| 后端 | Ruff、strict mypy、相关 pytest；共享领域／鉴权／迁移跑完整套件；有意义的回归测试 |
| 财务／生命周期 | Decimal 结果、所有权、归档、回滚、时间戳、空集；合成数据 |
| 前端 | `npm run test`、`npm run build` 及受影响交互；Vitest/Vue Test Utils 覆盖非平凡组件与请求上下文行为 |
| OpenAPI | 重新生成 `schema.d.ts`、检查 diff、构建前端；描述也可能影响输出 |
| 容器／启动 | 真构建镜像，一次性数据验证相关迁移／启动／SPA |
| 文件移动／删除 | 核对 import、链接、Docker COPY 来源、打包和 CI 引用 |
| 文档 | 链接／锚点、双语一致性、命令与配置、空白及改动范围 |

当前 CI 提供后端 lint／类型／测试、codegen 一致性、前端单元测试／构建和有条件 Docker 构建。`npm run test` 单次运行 Vitest，`npm run test:watch` 启动监视模式。Tag 发布不依赖完整质量检查／镜像运行冒烟测试，[REL-01](plan/roadmap.zh.md) 追踪缺口。不声称未运行的测试、未发生的独立评审或未经确认的用户验收。

版本使用 `vX.Y.Z` Git 标签。准确源码提交通过 CI 后，标签触发 `.github/workflows/release.yml` 发布 `linux/amd64` 和 `linux/arm64` 的 GHCR 镜像；再使用成对发布说明创建 GitHub Release，并核对 workflow 及仓库 manifest。Git 推送、标签／版本发布和生产部署分别需要适用授权。发版不会替换运行中的 app，自动发布门禁仍由 REL-01 跟踪。

## 独立评审与本地交接

普通工作保持单代理，明确请求后才启动委派编排。被调用的已安装技能提供有边界的流程、返工上限、角色设置和运行记录要求，不复制其他项目互相冲突的变体。评审是测试的补充。

- 首轮 reviewer：全新上下文，原始任务／设计、完整候选 diff／快照、准确边界和中性说明。不传实施／返工报告、过程聊天、预设结论或辩护。允许读取相关源码／规则并独立检查。
- 复审 reviewer：还可接收上一轮评审报告和修复增量，仍需独立对照原始契约检查累计候选。Fixer 可读实施与评审报告。
- 只阻塞验收违例、可复现缺陷或实际安全／数据／兼容风险，给出位置、证据、触发条件、后果和修正要求。可选偏好不启动返工循环。
- 记录实际候选：已提交则记 base/head SHA，未提交则保存含相关未跟踪文件的可复现 diff／快照。不为制造边界而擅自提交；评审后再变更代码，旧结论对受影响部分不自动有效。

详细执行证据放在本地、被忽略的 `development-notes/<run-id>/`。交付中文 `summary.md` 和 `walkthrough.md`，覆盖范围、候选、检查／结果、限制、准确启动方式／操作／预期及清理。保留被调用技能要求的额外报告。已有 `review-notes/` 保留为本地历史。小型纯文档工作可在聊天报告；稳定计划只留简洁决策／状态／验收。

数据库、配置、容器和合成账户保持隔离，记录资源并只清理本轮创建的部分，不停已有部署或改真实交易记录来验证。

Git 授权针对动作：实现或委派本身不授权 commit、push、发布／tag 或改写历史。授权后，由 orchestrator 操作共用工作区的 Git，不并发提交／rebase。每任务一个提交，只合并本任务未发布的 fixup，保留其他任务及已发布历史。
