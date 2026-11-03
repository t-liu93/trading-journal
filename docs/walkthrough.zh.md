# 一次性构建与功能走查

> [English](walkthrough.md) · **中文**

这是当前手动验证指南。使用新建临时环境和合成数据，不启动或修改常规部署。通过只代表实际走过的路径，不代表用户验收。范围看[路线图](plan/roadmap.zh.md)与对应任务卡。

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

## 3. 代表性功能检查

使用 `walkthrough@example.com` 等合成邮箱。注册会校验普通邮箱格式，但应用不会发送邮件。记录操作和观察，不把未测情况标成通过。

1. **鉴权／主题：** 注册、登录、刷新、登出／重登，切换明暗后刷新。预期 session 与主题持久化。邮箱会校验格式，但不发送邮件。
2. **账户：** 建一个保留用于交易的账户，再建一个编辑／归档。预期归档账户默认隐藏，“Show archived”仍可查看，这不等于取消归档。
3. **期权到期与历史：** 建两只不同 ID 的股票（例如 AAPL、TSLA）；如有需要，创建相同股票代码但不同交易所的记录。为第一只股票创建昨天、今天、明天到期的期权，日期以当前 **UTC 日期** 为基准；为第二只股票也创建期权。在 Instruments 页面，昨天到期的默认隐藏，今天和明天到期的显示。打开 “Show expired options” 后，历史期权应出现，搜索和类型筛选仍生效。underlying 筛选通过 API 与有上下文的 picker 检查，管理页面没有该控件。
4. **旧 API 默认与分页：** 登录后，在浏览器 Network 面板或 `/docs` Swagger 请求 `GET /api/instruments?kind=option`，确认兼容旧客户端的默认值仍包含过期合约。再带 `include_expired=false` 请求，过期项应排除。为同一 underlying 创建或生成超过 50 条过期项和超过 50 条匹配的未过期项。确认 UI 能访问匹配候选第 50 条以后的结果；隐藏过期项时，它们不应占用第一页。`offset=50` 应返回下一页；筛选先于每页 50 条的限制执行。没有匹配的 underlying 时不返回期权。如果手动创建这些记录不实际，可用自动化 fixture，并注明采用了哪种方法。
5. **上下文与内嵌创建：** 用第一只股票作 Primary Instrument 创建 Position。First Trade、两个 Add Trade 入口、新增腿和 PMCC LEAP 应仅显示该 underlying 的期权；一般 Trade 表单仍保留股票／外汇选择。主标的切换到另一只股票后，不兼容的期权腿应清除并提示，数量、价格、日期、费用、备注保留。改为同 underlying 的期权主标的，兼容腿应保留。无论搜索结果是否为空，都使用“为当前 underlying 创建期权”：underlying、币种、交易所预填，underlying 锁定。重复自然键创建返回已有合约。显式创建历史期权后，该 picker 自动显示过期项并选中新合约。关闭开关仍保留已选历史合约标签；清空后需重新启用历史显示才能再选。当前表单会话内重新打开 picker 时保留开关；新建 Trade 表单会话恢复默认状态。
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
