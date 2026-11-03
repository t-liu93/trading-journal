# 一次性构建与功能走查

> [English](walkthrough.md) · **中文**

这是当前手动验证指南。使用新建临时环境和合成数据，不启动或修改常规部署。通过只代表实际走过的路径，不代表验收所有延后功能。范围看[路线图](plan/roadmap.zh.md)与对应任务卡。

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

使用 `walkthrough@example.test` 等合成邮箱，记录操作和观察，不把未测情况标成通过。

1. **鉴权／主题：** 注册、登录、刷新、登出／重登，切换明暗后刷新。预期 session 与主题按各自规则持久化。
2. **账户：** 建一个保留用于交易的账户，再建一个编辑／归档。预期归档账户默认隐藏，“Show archived”仍可查看，这不等于取消归档。
3. **品种／配置：** 创建股票、期权和外汇样例，检查内嵌创建和重复 get-or-create。确认到期／行权价／类型能区分期权合约。保存／重载策略配置。
4. **仓位／首笔成交：** 创建股票 Position，包含必需 First Trade。零费用、买 10、价格 100，预期现金流 −1000。访问 Overview、Meta、Plan、Trades，资金占用设为 1000。另建合成 wheel／PMCC 检查元数据；追加两版计划并确认均保留。
5. **成交操作：** 较晚时间零费用卖 10、价格 110，预期 +1100、总现金流 100。另一个未平仓 Position 中改 notes、归档 Trade、切换归档可见性；归档行保留但不计入统计。遇到 [triage](triage/improvements.md) 中已知备注布局／日期问题应记录，本指南不声称已修复。
6. **多腿：** 按附录录入合成 Iron Condor、指派、行权和到期例子。同次多腿提交共享订单分组，pattern badge 匹配支持的形态；单行事件不必有 group ID。
7. **平仓／仪表盘：** 对步骤 5 的股票 Position 平仓，两笔成交均有效。预期冻结已实现 P&L 为 100，默认平仓时间取最后成交。确认已平仓 Trade 操作不可用。仪表盘显示平仓结果、月度桶、胜率和账户筛选，币种分别统计。
8. **删除／持久化：** 删除带 Trade／计划的 Position 应拒绝。在测试终端运行 `tj_check restart app`，刷新确认合成数据仍在。用 `ls -l "$TJ_CHECK_DIR/data"` 核对数据库属主。

这是代表性走查，不是完整回归。各任务还需补自己的边界并在验收前验证；独立评审与自动检查分别记录。

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
