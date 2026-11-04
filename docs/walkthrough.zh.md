# 一次性构建与功能走查

> [English](walkthrough.md) · **中文**

这是当前手动验证指南。使用新建临时环境和合成数据，不启动或修改常规部署。通过只代表实际走过的路径，不代表用户验收。范围看[路线图](plan/roadmap.zh.md)与对应任务卡。

MCP 从 v1.2.0 起提供，v1.1.0 不包含该功能。以下隔离走查使用第 1 节从 checkout 构建的 overlay 验证选定源码，不发布源码或改变运行中的部署；不复用现有客户端配置或真实日志数据。

## 1. 创建隔离环境

前提：Docker 和 Compose、待验候选的 checkout、浏览器；仅远程测试需要 SSH。使用独立终端，从仓库根目录开始。18000 端口须空闲；若占用，修改复制后的映射和隧道为其他空闲端口，不停已有监听服务。

命令把部署模板复制到新建目录，从候选源码构建，并为本轮生成独立项目／镜像名。不使用仓库 `data/` 或根目录 Compose／`.env`。模板本就只绑定 loopback。无需手工 `COOKIE_SECRET`；本地 HTTP 显式设 `COOKIE_SECURE=false`。

```bash
export TJ_SOURCE_DIR="$(pwd)"
export TJ_CHECK_DIR="$(mktemp -d /tmp/tj-check-XXXXXX)"
export TJ_CHECK_ID="$(basename "$TJ_CHECK_DIR" | tr '[:upper:]' '[:lower:]')"
export PUID="$(id -u)"
export PGID="$(id -g)"
export COOKIE_SECURE=false
export DEBUG=false
mkdir "$TJ_CHECK_DIR/data"

sed 's/127.0.0.1:8000:8000/127.0.0.1:18000:8000/' \
  example/docker-compose.yml > "$TJ_CHECK_DIR/compose.yml"

cat > "$TJ_CHECK_DIR/local.yml" <<'YAML'
services:
  migrate:
    build:
      context: $TJ_SOURCE_DIR
      dockerfile: Dockerfile
    image: trading-journal:$TJ_CHECK_ID
  app:
    build:
      context: $TJ_SOURCE_DIR
      dockerfile: Dockerfile
    image: trading-journal:$TJ_CHECK_ID
YAML

tj_check() {
  docker compose --env-file /dev/null -p "$TJ_CHECK_ID" \
    -f "$TJ_CHECK_DIR/compose.yml" -f "$TJ_CHECK_DIR/local.yml" "$@"
}

tj_check config
```

`up` 前检查 `config`：两个数据库挂载都应位于 `$TJ_CHECK_DIR/data`，构建上下文是当前 checkout，宿主绑定仅为 `127.0.0.1:18000`。不相符就先停下，修正临时配置。

```bash
tj_check up -d --build
tj_check ps -a
tj_check logs --tail=30 migrate app
```

预期：`migrate` 成功退出，之后 `app` 变 healthy。迁移日志属于 `migrate`，app 的 `RUN_MIGRATIONS=false` 避免重复迁移。迁移失败应阻止 app 启动。数据库／密钥在临时数据目录创建，属主是选定的宿主 UID/GID。不通过删除已有数据库解决权限问题。

## 2. 浏览器访问与基础设施

本地打开 `http://localhost:18000`。远程开发机从笔记本转发：

```bash
ssh -N -L 18000:127.0.0.1:18000 <user>@<dev-server>
```

合成账户使用独立浏览器 profile／容器。Cookie 按 hostname 而不是端口隔离，其他 `localhost` 应用／测试可能共用 cookie 命名空间。

| 检查 | 预期 |
|---|---|
| `http://localhost:18000/` | 登录／注册 UI |
| `http://localhost:18000/api/health` | JSON `{"status":"ok"}` |
| `http://localhost:18000/docs` | Swagger UI |
| 登录后刷新 `/positions` 深链 | SPA 路由加载，不是 JSON 或 404 |
| `/api/nope` | JSON 404，不是 SPA 外壳 |

## MCP 客户端设置与走查

服务使用同一个 app 和数据库，在精确的 `/api/mcp` 路径提供 MCP。本机客户端连接 `http://localhost:18000/api/mcp`；远程客户端经 HTTPS 反代连接 `https://<journal-host>/api/mcp`。app 端口继续绑定 loopback，不要直接向网络开放 8000／18000。

同机 HTTPS 反代需在 `app` 服务配置 `MCP_ALLOWED_HOSTS` 与 `MCP_ALLOWED_ORIGINS`。保留 localhost／loopback 默认值，并加入准确公网 Host（有端口时也包含）与 Origin。这两个变量都是 JSON 数组。以下内容放在第 1 节临时 `local.yml` 覆盖文件中：

```yaml
services:
  app:
    environment:
      JOURNAL_TIMEZONE: Europe/Amsterdam
      MCP_ALLOWED_HOSTS: '["127.0.0.1","127.0.0.1:*","localhost","localhost:*","[::1]","[::1]:*","journal.example.net"]'
      MCP_ALLOWED_ORIGINS: '["http://127.0.0.1","http://127.0.0.1:*","http://localhost","http://localhost:*","http://[::1]","http://[::1]:*","https://journal.example.net"]'
```

将 `journal.example.net` 替换为实际公网主机名。没有 `Origin` 的正常 MCP 请求允许通过，不要设通配符。反代需终结 TLS，将 `/api/mcp` 原样转发到 `http://127.0.0.1:18000/api/mcp`，不得去除或改写路径；保留 `Host`、`Authorization`、`Accept`、`Content-Type` 及 MCP 头，例如 `MCP-Protocol-Version`、`MCP-Session-Id` 和 `Last-Event-ID`。该端点应关闭响应缓冲。以下是同机 Nginx 示例：

```nginx
location = /api/mcp {
    proxy_pass http://127.0.0.1:18000;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header Origin $http_origin;
    proxy_buffering off;
}
```

在临时网站“设置 → MCP”创建三个凭证：一个只读 `read` 用于只读检查，以及 Codex、Hermes 各自独立的 `entry` 凭证。名称注明客户端。密钥只显示一次；直接粘贴到隐藏输入提示，绝不写入命令、shell 历史、受版本控制文件或聊天。凭证默认 90 天过期。若保留环境，清理前先撤销临时凭证；删除临时数据库也会移除凭证。

临时服务运行期间，在 Bash 终端执行以下命令。它们会静默读取密钥，只将变量放进进程环境。Codex 从新建临时工作目录运行，使用临时 `log_dir`／`sqlite_home`、命令级 MCP 设置、`--ignore-user-config` 与 `--ephemeral`；不修改 `HOME`、`CODEX_HOME` 或现有客户端配置。由于忽略用户配置，如需模型／提供商设置，由你自行用命令级 `-c` 覆盖并通过环境变量提供所需鉴权；不要从现有配置复制设置。MCP 协议预检不需要调用外部模型。

**Codex 使用命令级临时设置做只读查询：**

```bash
export TJ_CODEX_TMP="$(mktemp -d /tmp/tj-codex-XXXXXX)"
mkdir -p "$TJ_CODEX_TMP/cwd" "$TJ_CODEX_TMP/logs" "$TJ_CODEX_TMP/sqlite"
read -r -s -p 'Codex read token: ' TJ_CODEX_TOKEN
printf '\n'
export TJ_CODEX_TOKEN
tj_codex() {
  codex exec --ignore-user-config --ephemeral --skip-git-repo-check \
    -C "$TJ_CODEX_TMP/cwd" \
    -c "log_dir=\"$TJ_CODEX_TMP/logs\"" \
    -c "sqlite_home=\"$TJ_CODEX_TMP/sqlite\"" \
    -c 'mcp_servers.trading_journal.url="http://localhost:18000/api/mcp"' \
    -c 'mcp_servers.trading_journal.bearer_token_env_var="TJ_CODEX_TOKEN"' \
    "$@"
}
tj_codex 'Use get_context and list_accounts only. Do not prepare or commit entries.'
```

Codex 合成录入需换成单独签发的 `entry` 凭证，先做只准备的一次性执行：

```bash
unset TJ_CODEX_TOKEN
read -r -s -p 'Codex entry token: ' TJ_CODEX_TOKEN
printf '\n'
export TJ_CODEX_TOKEN
tj_codex 'Use the paper account named MCP walkthrough and a synthetic USD stock named MCPTEST (create it if absent). Prepare a new spot_stock Position with one buy leg: quantity 1, price USD 1.00, at the exact execution date/time I provide. If I have not supplied the concrete date/time or any required detail, ask and stop. Show the complete preview and returned request_id and draft_id, then stop. Do not call commit_entry.'
```

检查该命令输出的预览。若确认正确，先在终端明确批准，再启动第二次 `exec`；第二次运行只提交刚才显示的草稿：

```bash
read -r -p 'Displayed draft_id: ' TJ_DRAFT_ID
read -r -p 'After reviewing and explicitly approving that preview, type CONFIRM: ' TJ_APPROVAL
if [ "$TJ_APPROVAL" = CONFIRM ]; then
  tj_codex "The owner explicitly confirmed the displayed preview. Call commit_entry only with this exact draft_id: $TJ_DRAFT_ID. Do not prepare or change the batch."
else
  printf '%s\n' 'Not confirmed; no commit requested.'
fi
```

每个 `codex exec` 调用只运行一次。如果它提出澄清问题，就在新的 `tj_codex` 调用中补充完整且明确的信息；收到完整预览前不要批准或提交。首次成功准备会在 `prepare_entry` 后停止并保留 `draft_id`；只有用户明确批准后才执行第二条。提交响应不确定时用同一个 `draft_id` 重试。待提交预览 24 小时过期；不要为重试新建替代草稿。

**Hermes 使用隔离配置目录：**

```bash
export TJ_HERMES_HOME="$(mktemp -d /tmp/tj-hermes-XXXXXX)"
mkdir -p "$TJ_HERMES_HOME"
cat > "$TJ_HERMES_HOME/config.yaml" <<'YAML'
mcp_servers:
  trading_journal:
    url: http://localhost:18000/api/mcp
    headers:
      Authorization: "Bearer ${TJ_HERMES_TOKEN}"
YAML
read -r -s -p 'Hermes read token: ' TJ_HERMES_TOKEN
printf '\n'
export TJ_HERMES_TOKEN HERMES_HOME="$TJ_HERMES_HOME"
hermes chat
```

示例使用独立的 `read` 凭证；录入时，在隐藏提示中输入 Hermes 自己的 `entry` 凭证。Hermes 会展开配置字符串中的 `${VAR}`；YAML 保存的是变量引用而非令牌。`HERMES_HOME` 指向新建临时目录，因此不会改动已有 `~/.hermes/config.yaml`。客户端参数与临时运行目录见 [Hermes MCP 配置指南](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)、[Codex MCP 文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) 和 [Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)。这里的命令是配置说明，不代表已成功连接任一已安装客户端。

两个客户端都应遵循：`read` 凭证只用于查询，服务端会拒绝直接调用写入工具。只有用户明确批准已展示的该草稿才构成确认；原始交易描述或普通后续文字不算批准。录入时，Agent 需先澄清账户、品种／合约、动作、数量、价格、成交时间和期权开／平仓意图，再展示包含费用／默认值、时区解释与现金流的服务器预览；用户必须明确确认该草稿后才可提交。

### 七步用户走查

以下步骤对应 [M-MCP-01 §4.2](plan/milestone-mcp-entry.zh.md#42-用户走查)。只使用本 checkout 隔离环境中新建的数据库和合成记录：

1. 在临时网站创建一个名为 `MCP walkthrough` 的合成 `paper` 账户、Codex 与 Hermes 各自独立的 `entry` 凭证，以及一个 `read` 凭证。每个密钥只通过上方隐藏提示输入。
2. 在 Codex 用第一条一次性命令准备 `spot_stock` Position 和第一笔成交：使用合成 USD 股票（`MCPTEST`，若不存在则创建），`buy` 1 股，价格 USD 1.00，成交日期／时间由你提供明确值。确认只准备草稿时没有创建 Position 或 Trade；检查完整预览、明确批准，然后用准确相同的 `draft_id` 执行第二条命令，并在网站核对记录。缺字段时 Agent 必须先问，不能自行编造。
3. Hermes 用自己的 `entry` 凭证查询该 Position、追加 Trade，并录入更早日期成交。确认 `opened_at` 随最早有效成交变化。
4. 准备一个需要新建缺失期权的多腿录入。确认前检查完整合约规格、默认 multiplier/style、默认费用及每腿现金流。
5. 比较使用服务器默认值的无时区成交时间与显式 IANA 时区时间，核对预览 UTC 时间和网站浏览器本地显示。
6. 重试已提交的同一个 `draft_id`，确认 Trade 数量和返回 ID 不变。撤销一个 entry 凭证，确认后续 MCP 请求被拒绝。
7. 用 `read` 凭证确认上下文／列表查询成功；`prepare_entry` 和 `commit_entry`（包括直接调用工具）都应被拒绝。

任何跳过步骤都记录为未运行。这是走查计划；配置说明和协议预检不代表用户已验收。

完成走查并记录观察后，在网站撤销三个凭证，按第 4 节命令停止本轮 Compose 项目，删除临时 Codex／Hermes 目录并清除环境变量：

```bash
rm -r -- "$TJ_HERMES_HOME" "$TJ_CODEX_TMP"
unset -f tj_codex
unset TJ_HERMES_HOME HERMES_HOME TJ_HERMES_TOKEN TJ_CODEX_TOKEN TJ_CODEX_TMP TJ_DRAFT_ID TJ_APPROVAL
```

如果 Hermes 因本机依赖环境不可用而在连接前退出，记录确切错误并将客户端检查标为未运行。不要在本走查中修复、安装或改动已有 Hermes 安装。

## 3. 代表性功能检查

使用 `walkthrough@example.com` 等合成邮箱。注册会校验普通邮箱格式，但应用不会发送邮件。记录操作和观察，不把未测情况标成通过。

1. **鉴权／主题：** 注册、登录、刷新、登出／重登，切换明暗后刷新。预期 session 与主题持久化。邮箱会校验格式，但不发送邮件。
2. **账户：** 建一个保留用于交易的账户，再建一个编辑／归档。预期归档账户默认隐藏，“Show archived”仍可查看，这不等于取消归档。
3. **期权到期与历史：** 建两只不同 ID 的股票（例如 AAPL、TSLA）；如有需要，创建相同股票代码但不同交易所的记录。为第一只股票创建昨天、今天、明天到期的期权，日期以当前 **UTC 日期** 为基准；为第二只股票也创建期权。在 Instruments 页面，昨天到期的默认隐藏，今天和明天到期的显示。打开 “Show expired options” 后，历史期权应出现，搜索和类型筛选仍生效。underlying 筛选通过 API 与有上下文的 picker 检查，管理页面没有该控件。
4. **旧 API 默认与分页：** 登录后，在浏览器 Network 面板或 `/docs` Swagger 请求 `GET /api/instruments?kind=option`，确认兼容旧客户端的默认值仍包含过期合约。再带 `include_expired=false` 请求，过期项应排除。为同一 underlying 创建或生成超过 50 条过期项和超过 50 条匹配的未过期项。确认 UI 能访问匹配候选第 50 条以后的结果；隐藏过期项时，它们不应占用第一页。`offset=50` 应返回下一页；筛选先于每页 50 条的限制执行。没有匹配的 underlying 时不返回期权。如果手动创建这些记录不实际，可用自动化 fixture，并注明采用了哪种方法。
5. **上下文与内嵌创建：** 用第一只股票作 Primary Instrument 创建 Position。First Trade、两个 Add Trade 入口和每个 Trade 腿应仅显示精确股票 ID 及其期权；其他股票（包括同 symbol 不同 ID）和外汇必须隐藏。PMCC LEAP 仍只显示期权。搜索并选择股票 A 的期权，再把 Primary 切到股票 B：可见搜索词和下一请求都应为空，B 股票及期权可达，A 期权不可见。无搜索再切 B 也检查同样候选。股票与同 underlying 的期权 Primary 互切时，所选合约和腿字段保留，搜索清空。清空 Primary 后恢复通用候选并清空搜索。切换到不同股票后，不兼容的期权腿应清除并提示，数量、价格、日期、费用、备注保留。无论搜索结果是否为空，都使用“为当前 underlying 创建期权”：underlying、币种、交易所预填，underlying 锁定。创建结果若不属于当前上下文不得自动选中。重复自然键创建返回已有合约。显式创建历史期权后，该 picker 自动显示过期项并选中新合约。关闭开关仍保留已选历史合约标签；清空后需重新启用历史显示才能再选。当前表单会话内重新打开 picker 时保留开关；新建 Trade 表单会话恢复默认状态。
6. **普通品种与配置：** 从品种管理创建股票和外汇，再保存／重载策略配置。确认一般 Trade 表单仍可选择股票和外汇。
7. **日期与现金流：** 通过 `/docs` Swagger API 创建开仓日期为 D3 的空 Position；表单要求填写 First Trade，所以空 Position 仅用 API 创建。先添加零费用、D1 执行的买入 10 股 @100，再添加零费用、D2 执行的卖出 10 股 @110（D1 < D2 < D3）。`opened_at` 应变为 D1，现金流为 100。归档 D1 Trade 后，开仓变为 D2；重新录入 D1 成交后，开仓回到 D1。不指定平仓时间关闭，预期 `closed_at=D2`，已实现盈亏冻结为 100。在另一个未平仓 Position 上归档所有成交：保留最后开仓日期，直到新有效成交建立新日期。单独检查早于开仓日期的平仓：返回 422，状态、日期、备注及其他提交字段均不变。再单独提交包含后续无效腿的多腿批次：返回 422，不新增 Trade，也不改变开仓日期。开平仓同一时刻允许。表示相同瞬间的偏移时间戳应比较相等。已平仓 Position 拒绝创建／归档 Trade，且不可重新打开。UI 不提供的边界情况用 API 检查。
8. **备注与多腿：** 同一合约添加两笔不同备注的 Trade，再提交四腿 Trade，包含空、长、多行和类似 HTML 的文本（如 `<b>sample</b>`）。备注应紧跟各自 Trade 行、跨满表格、保留换行并按纯文本展示，不重复显示在分组底部。编辑备注时，Enter 换行，Ctrl/Command+Enter 或 Save 提交，Cancel 撤销；失败时保留输入；清空后保存即移除备注；只读状态会退出编辑。归档与平仓限制仍有效。按附录录入 Iron Condor、指派、行权和到期样例；同次提交的多腿按规则共享分组。
9. **表单与布局：** 在 1280px、390px，以及明／暗主题下检查 Position First Trade、Add Trade 和四腿表单。低于 600px 为单列，更宽时双列。Instrument、Notes 占满一行；标签在字段上方，帮助／错误在下方。触发校验，确认焦点到对应腿／字段，其他输入和增删腿不丢失。检查键盘导航和现金流预览。
10. **平仓／仪表盘／删除／持久化：** 确认已平仓 Position 不可操作 Trade。仪表盘显示平仓结果、月度桶、胜率和账户筛选，各币种分别统计。删除带 Trade／计划的 Position 应拒绝。运行 `tj_check restart app`，刷新确认合成数据仍在。用 `ls -l "$TJ_CHECK_DIR/data"` 核对数据库属主。

Vitest／pytest 自动场景覆盖请求竞态、输入保留、校验、日期边界、所有权、原子性和回滚。其命令结果应另行记录；自动测试不能替代只有人能判断的路径。这是代表性走查，不是完整回归。明确记录每项未测人工步骤；浏览器自动化与实现检查不等于用户验收。

## 4. 记录与清理

任务记录中写明候选身份、实际检查、失败、跳过路径和用户明确验收。详细中文总结／走查证据留在本地 `development-notes/<run-id>/`。自动化完成与人工接受分开。

收集观察后，在同一个测试终端执行：

```bash
tj_check down
docker image rm "trading-journal:$TJ_CHECK_ID"
rm -r -- "$TJ_CHECK_DIR"
unset -f tj_check
unset TJ_SOURCE_DIR TJ_CHECK_DIR TJ_CHECK_ID PUID PGID COOKIE_SECURE DEBUG
```

只删除上方创建的独立测试容器／镜像和目录，关闭 SSH 隧道与合成浏览器 profile。不应停或删任何已有部署／数据目录。

## 排查

| 现象 | 检查 |
|---|---|
| 迁移失败 | `tj_check logs migrate`、临时数据目录属主和所选 UID/GID |
| 连不上 | 空闲宿主端口、对应 SSH 隧道、`tj_check ps -a` |
| 登录态不保持 | HTTP 的 `COOKIE_SECURE=false`、统一 hostname、独立测试浏览器、`/api/users/me` 响应 |
| 提示缺密钥 | 当前 app 不需环境密钥，检查是否用了旧镜像／模板 |
| UI 还是旧的 | 在目标候选 checkout 重跑 `tj_check up -d --build` |
| 出现已知问题 | 按 triage／任务 ID 记录，不悄悄改数据把走查变通过 |

## 附录 — 事件行

准确样例见[原始领域映射](design/data-model.zh.md#452-notion-事件--原子-trade-映射)。

| 事件 | 一起提交的行 |
|---|---|
| Iron Condor 开仓 | 四条期权腿，两侧 credit spread |
| 指派 | 期权零价平仓，加按行权价成交的股票 |
| 行权 | 期权零价平仓，加按行权价成交的股票 |
| 到期 | 一条期权零价平仓 |

Badge 从记录形态推断，不是策略声明，也不是执行真实交易的指令。
