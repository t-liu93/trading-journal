# Trading Journal —— 手工 Build 与功能验收 walkthrough

**Language:** [English](./walkthrough.md) | 中文

> 手把手指南：**build Docker 镜像、跑单容器、从笔记本经 SSH 隧道访问、逐一验证每个
> V1 功能**。这是 F6.C 的验收走查（见
> [v1-implementation-plan-f6.zh.md](./design/v1-implementation-plan-f6.zh.md)）。
>
> 假设的环境：你在**远程服务器上通过 SSH 开发**；容器跑在那台服务器上；你从
> **笔记本浏览器经 `localhost` 测试**。

---

## 0. 前置

**dev 服务器**上：
- Docker + Compose 插件（`docker compose version`）。
- 已 checkout 本仓库；当前在 `refactoring/rebuild`。

**笔记本**上：
- 能 SSH 到 dev 服务器的客户端。
- 一个浏览器。

---

## 1. Build 并跑容器（在 dev 服务器上）

```bash
# 示例 compose 在 ./example 下。从那里跑容器，让它相对的 ./data bind mount 和
# .env 紧挨着 compose 文件。
cd /path/to/trading-journal/example

# 1. 先建 data 目录、属主是你。这是头号坑：
#    容器以你的 UID（1000）运行、把 app.db 写进 ./data。
#    若让 Docker 自动建 ./data，它会归 root，迁移会失败。
mkdir -p data

# 2. 造一个真实的 .env（它被 gitignore）。模板在仓库根目录。
cp ../.env.example .env
#    生成一个真实 secret，填进 .env 的 COOKIE_SECRET=...
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
#    编辑 .env：把 COOKIE_SECRET 设成上面那个值。COOKIE_SECURE 保持 false
#    （现在是 SSH 隧道上的纯 HTTP，还不是 HTTPS）。

# 3. 示例 compose 拉取 ghcr.io/t-liu93/trading-journal:latest。要跑你自己的本地
#    build 做验收，先 build 出这个 tag（context = 仓库根）：
docker build -t ghcr.io/t-liu93/trading-journal:latest ..
#    然后后台起容器。想直接用已发布镜像就跳过上面的 build。
docker compose up -d

# 4. 确认起来且健康（healthcheck 给它 ~10-15s）。
docker compose ps
#    STATUS 应显示 "Up ... (healthy)"。
docker compose logs --tail=20 app
#    应看到先跑 "alembic upgrade head"，然后 uvicorn 监听 :8000。
```

如果你服务器上的 `PUID`/`PGID` 不是 1000，先在 `.env` 里设（`PUID=$(id -u)`、
`PGID=$(id -g)`）再 `up`。

**安全提示（SSH 开发推荐）：** 默认 Compose 把 `8000:8000` 发布在服务器的 `0.0.0.0`
（所有网卡）。要让它私有、**只**能经你的 SSH 隧道访问，把 `example/docker-compose.yml` 的端口
行改成只绑 loopback：

```yaml
    ports:
      - "127.0.0.1:8000:8000"
```

---

## 2. 从笔记本经 SSH 隧道访问

容器监听的是**服务器**的 `localhost:8000`。把笔记本的 `localhost:8000` 转发过去。在
**笔记本终端**：

```bash
ssh -N -L 8000:localhost:8000 <user>@<dev-server>
# -N：不执行远程命令，只转发。让它一直开着。
```

或在笔记本 `~/.ssh/config` 里固化：

```
Host devbox
    HostName <dev-server>
    User <user>
    LocalForward 8000 localhost:8000
```

……然后 `ssh devbox`。（VS Code Remote-SSH 会自动转发端口 —— 看 **PORTS** 面板 ——
所以你可能根本不用手动开。）

现在在笔记本打开 **http://localhost:8000**。

**为什么用 `localhost` 而不是服务器 IP：** cookie 按确切的 hostname 存储，
`COOKIE_SECURE=false` 的 cookie 在 `localhost` 上行为一致（和 dev 在 :5173 用的
hostname 一致）。浏览器也把 `localhost` 当作 secure context。用服务器裸 IP 也能通，但
容易撞上「登录了但 session 莫名消失」的 cookie 坑 —— 走隧道、用 `localhost`。

---

## 3. 基础设施冒烟检查（先于功能）

隧道开着，在笔记本浏览器：

| 检查 | URL / 操作 | 预期 |
|---|---|---|
| SPA 加载 | `http://localhost:8000` | 出现 app UI（登录页），不是 JSON |
| API 活着 | `http://localhost:8000/api/health` | `{"status":"ok"}` |
| API 文档 | `http://localhost:8000/docs` | Swagger UI |
| **深链刷新** | 进 `http://localhost:8000/positions`，再按**刷新** | 仍是 SPA —— **不是** 404。（证明 catch-all fallback 生效。） |
| 未知 API 404 | `http://localhost:8000/api/nope` | JSON `{"detail":"Not Found"}`，不是 SPA 外壳 |

回到**服务器**，确认数据属主 + 持久化：

```bash
ls -l data/                       # app.db 在，属主是你（不是 root）
docker compose restart app        # 重启一下
# 刷新浏览器 -> 数据还在（DB 跨重启存活）
```

以上全过，说明镜像和单容器接线正确。进入功能验收。

---

## 4. 功能走查（验收脚本）

在笔记本浏览器按顺序做。每步列出操作与**预期结果**。（用一次性测试数据 —— 这是你的真实
DB。）

1. **鉴权。** 注册一个新账号 → 登录态。登出 → 回到登录页。再登录。
   *预期：* session 跨刷新保持（cookie 经隧道工作正常）。

2. **Accounts（F1）。** 创建账户；编辑；归档。
   *预期：* 每次操作后列表更新；归档的从默认视图消失。

3. **Instruments（F2 + F3）。** 打开 `/instruments`。用表单创建一个 **stock**、一个
   **option**、一个 **forex** instrument。然后在 Position 创建流程里，用
   **InstrumentPicker 内嵌创建**（`allowCreate`）：输入一个全新 symbol，不离开表单就
   创建；期权确认**两步式**流程（先选标的，再填 strike/expiry/type/multiplier）。
   *预期：* 重复项静默命中已有 instrument（get-or-create）。

4. **Strategy config。** 进 `/settings/strategies`；给某策略设曝光上限。
   *预期：* 值保存并能重新加载。

5. **Position（F3）。** 创建一个 position（用 picker）。打开详情页，走遍四个 tab：
   - **Overview** —— 编辑手填字段（`capital_used`、`max_risk_at_open`…）；派生值
     （`days_open`、`pnl_total`、ROI、result）只读展示。
   - **Meta** —— `wheel` 仓位填 funding/loan/interest；`pmcc` 仓位选 LEAP；其他类型
     显示空状态。
   - **Plan** —— 追加一条 TradePlan revision；历史表增长。
   - **Trades** —— 目前是只读面板（下一步变 live）。

6. **Trade 录入（F4）。** 在 Trades tab 加 trade：
   - 一条**单条** trade（如股票买入）。*预期：* 出现；每行 `cash_flow` 显示。
   - 对[§4.5.2 速查表](#附录--多腿事件--录入行)里每个事件做一次 **Custom multi-leg**
     提交 —— 开 iron condor（4 腿）、assignment（2）、exercise（2）、expire（1）——
     一次提交的所有腿共享同一个 `order_group_id`。
   *预期：* 各腿按 `order_group_id` 分组渲染，并打上正确的 **pattern badge**
   （IC-open / Assignment / Exercise / Expiration）。

7. **Dashboard（F5）。** 打开 `/dashboard`。
   *预期：* 分币种 PnL 卡、开仓表、平仓表、**按月已实现 PnL 图**、胜率仪表 —— 都反映
   你刚录入的数据。

8. **删除路径。** 删一个挂了 trade/plan 的 position → 被拦、给出清晰的 409 提示。软删
   一条 trade，再用 `?include_archived=true` 查看。*预期：* 与描述一致。

八步全过，F6.A + 人工验收即完成。

---

## 5. 收尾与排查

```bash
docker compose down        # 停止 + 删除容器；./data 保留
docker compose up -d       # 再起来；数据还在
```

| 症状 | 可能原因 / 解法 |
|---|---|
| `up` 失败：写不了 `/data/app.db` / permission denied | `./data` 归 root 了。`sudo chown -R $(id -u):$(id -g) data`（或删掉它、以你自己 `mkdir -p data` 再 `up`）。 |
| `up` 时报 `COOKIE_SECRET` 错 | `.env` 没设。生成一个（步骤 1.2）填进去。 |
| 笔记本 `localhost:8000` 连接被拒 | SSH 隧道没开，或容器没起/不健康。重查 `ssh -N -L …` 和 `docker compose ps`。 |
| 登录后 session 老掉 | 你在用服务器 IP，而非经隧道的 `localhost`。改用 `localhost`。 |
| 服务器上 8000 端口被占 | 有别的东西占了。改 ports 映射的宿主侧（如 `8001:8000`），转发 `8001`。 |
| 改了代码但前端还是旧的 | 重新 build：`docker build -t ghcr.io/t-liu93/trading-journal:latest .. && docker compose up -d`（SPA 在 build 时烤进镜像）。 |

日志：`docker compose logs -f app`。

---

## 附录 —— 多腿事件 → 录入行

每个合成事件的确切腿形态定义在
[data-model.zh.md §4.5.2](./design/data-model.zh.md#452-notion-event--atomic-trade-mapping)
（Notion 事件 ↔ 原子 trade 映射）。步骤 6 的速查：

| 事件 | 同一 `order_group_id` 内的行 |
|---|---|
| 开 iron condor | 4 条期权腿（卖 + 买，两个翼） |
| assignment（指派） | 2 条（期权按 0 平 + 股票按 strike 成交） |
| exercise（行权） | 2 条（期权按 0 平 + 股票按 strike 成交） |
| expire（到期） | 1 条（期权按价 0 平） |

把一个事件的所有行作为一次多腿提交录入，让它们共享一个 `order_group_id`，Trades tab
才能识别出 pattern。
