# 前端 MVP 实施计划 — v0 草案

**语言：** [English](./frontend-implementation-plan.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-18）。`refactoring/rebuild` 分支前端第一刀端到端的执行计划。配套文档：[data-model.md](./data-model.md) 和 [mvp-implementation-plan.md](./mvp-implementation-plan.md)（后端）。写代码前先在这里迭代。

## 1. 目的与方法

后端 tracer bullet（Phase 0–4）交付了 `/health`、`/auth/*`、`/users/me` 和完整 `Account` CRUD 的 JSON 端点。本计划是**前端 tracer bullet** —— 用**最窄**的一刀 UI 在真实浏览器里证明全栈是通的：cookie session、router auth guard、带 credentials 的 fetch、组件库正常工作。

**方法：同样的 tracer-bullet 哲学。** 不要一上来铺所有页面。先证明信号能传 —— *注册 → 登录 → 看到受保护页面 → 登出* —— 之后再横向铺 CRUD 页面。

为什么：把 Vue 3 + Vite + FastAPI cookie session 接到一起，最危险的不是写表单（表单是重复劳动）。**最危险的是接线**：Vite dev-proxy 是否保留 cookie、刷新页面后 Pinia auth state 是否还在、router guard 触发顺序对不对、Naive UI 的 provider 是否挂在正确层级、单一 origin 的约束 dev 和 prod 是否一致。Tracer bullet 把这些集成风险快速暴露出来。

## 2. 范围

### 在范围内（本计划，Phase F0）

- `frontend/` 目录：Vite 项目脚手架 + 依赖 + 工具配置
- Vue 3 + TypeScript + Pinia + Vue Router 4
- Naive UI 作为组件库（含自动导入类型）
- Vite dev-proxy 把 API 路径转给后端（后端**不**开 CORS）
- HTTP 客户端封装（`fetch` + `credentials: 'include'` + 错误归一化）
- Pinia `auth` store：`login` / `register` / `logout` / `fetchMe` / `init`
- 三个页面：`Login`、`Register`、`Dashboard`（受保护占位页）
- Router auth guard（未登录访问受保护页 → `/login`；已登录访问 `/login` → `/`）
- `frontend/README.md` 说明 dev 工作流 + SSH 隧道
- 后端回归 —— Phase 2–4 pytest 套件持续通过；**后端代码不动**

### 明确不在范围（延后）

- **Account CRUD UI** —— Phase F1
- **Position / Trade / TradePlan / StrategyConfig UI** —— Phase F2+
- **策略专属视图**（wheel cycle、IC P&L 图、PMCC roll 历史）—— 更后
- **图表与报表** —— 更后（到时候用 ECharts / Plotly）
- **前端单元测试（Vitest）** —— F0 逻辑量太少，手动验证更划算；留到有值得测的逻辑再说
- **E2E 测试（Playwright）** —— 延后
- **Tailwind CSS** —— Naive UI 的 design tokens 够用；以后要重度定制布局再加
- **`openapi-typescript` 类型 codegen** —— 延后到 F1（F0 用到的少数几个类型手写更快）
- **i18n** —— MVP 单语言英文
- **PWA / service worker** —— 不做
- **暗色主题切换** —— 留到以后；Naive UI 一行 `darkTheme` prop 的事
- **生产 Docker 单容器部署** —— 后端原计划 Phase 5；F0 只跑 dev

## 3. 技术栈总览

| 层 | 选型 |
|---|---|
| 框架 | **Vue 3**（Composition API、`<script setup>`） |
| 构建工具 / dev server | **Vite 5+** |
| 语言 | **TypeScript 5+** |
| 路由 | **Vue Router 4** |
| 状态管理 | **Pinia** |
| 组件库 | **Naive UI** |
| HTTP 客户端 | 原生 `fetch`（薄封装，不用 axios） |
| 类型检查 | `vue-tsc` |
| Lint / formatter | **ESLint** (`@vue/eslint-config-typescript`) + **Prettier**（F0 阶段可省；不强求） |
| 自动导入 | `unplugin-vue-components` + `naive-ui` resolver |

## 4. 目录结构

```
trading-journal/
├── backend/                            # （Phase 4 之后不变）
├── frontend/
│   ├── package.json
│   ├── package-lock.json               # commit 进仓库
│   ├── tsconfig.json
│   ├── tsconfig.node.json              # vite.config.ts 专用
│   ├── vite.config.ts                  # Vue 插件、自动导入、dev-proxy
│   ├── index.html                      # HTML 入口，mount #app
│   ├── env.d.ts                        # ambient types（Vue SFC、自动导入）
│   ├── README.md                       # dev 工作流、SSH 隧道说明
│   └── src/
│       ├── main.ts                     # 启动：app + pinia + router + naive theme
│       ├── App.vue                     # 根：NConfigProvider + provider 栈 + <router-view>
│       ├── api/
│       │   ├── http.ts                 # fetch 封装，非 2xx 抛错，自动解析 JSON
│       │   └── types.ts                # 手写 TS interface（User、FastAPIUsersError）
│       ├── stores/
│       │   └── auth.ts                 # Pinia：user、isAuthenticated、login、logout、fetchMe、init
│       ├── router/
│       │   └── index.ts                # 路由表 + beforeEach guard
│       └── views/
│           ├── LoginView.vue
│           ├── RegisterView.vue
│           └── DashboardView.vue
└── docs/
    └── design/
        └── frontend-implementation-plan.md  (本文档)
```

## 5. 阶段拆分

每个 sub-phase 都有 **目标**、**任务**、**人工验证**、**验收**。按顺序执行。

### F0.1 — 脚手架 + Naive UI hello world

**目标。** Vite 项目能启动，浏览器在 `localhost:5173` 渲染出一个 Naive UI 按钮。证明工具链通了。

**任务。**
1. `mkdir frontend && cd frontend && npm create vite@latest . -- --template vue-ts`
2. 加依赖：
   - runtime：`vue-router`、`pinia`、`naive-ui`、`vfonts`
   - dev：`unplugin-vue-components`（自动导入 Naive UI 组件 + 类型）
3. 配置 `vite.config.ts`：
   - `@vitejs/plugin-vue`
   - `unplugin-vue-components` 配 `NaiveUiResolver`
   - `server.host = '127.0.0.1'`（**不**绑 0.0.0.0 —— 跟后端一样走 SSH 隧道）
   - `server.port = 5173`
4. 写 `src/App.vue`，最小内容：`<n-config-provider :theme="null">` 包一个 `<n-button>Hello</n-button>` 加 `<router-view />` 占位
5. 写 `src/main.ts`：create app、mount

**人工验证。**
```bash
cd frontend
npm install
npm run dev
# 通过 SSH 隧道打开 http://localhost:5173
# 期望：Naive 按钮渲染出来，console 无报错，编辑器类型完整
```

**验收。** 浏览器能看到按钮；`npm run build` 成功（顺便挡住早期类型错误）。

---

### F0.2 — Auth 接线：HTTP client + Pinia store + Vite proxy

**目标。** 在 console 里验证浏览器能通过 Vite proxy 打到后端，且 auth 状态在 Pinia 里活着。

**任务。**
1. **Vite proxy** 配进 `vite.config.ts`。后端所有 route 都挂在 `/api` 前缀下
   （见后端 `main.py`），所以一条规则就够了，SPA 自己的 route（`/accounts`、
   `/login` 等）跟 API path 不会撞：
   ```ts
   server: {
     port: 5173,
     host: 'localhost',
     strictPort: true,
     proxy: {
       '/api': 'http://127.0.0.1:8000',
     }
   }
   ```
2. **`src/api/types.ts`** —— 手写 interface（F0 ≈30 行）：
   ```ts
   export interface User {
     id: string
     email: string
     is_active: boolean
     is_verified: boolean
     is_superuser: boolean
     last_login_at: string | null
     created_at: string
   }
   ```
3. **`src/api/http.ts`** —— 薄封装：
   - `request(method, path, options)` 永远带 `credentials: 'include'`
   - 非 2xx：解析 JSON，抛带 status 和 body 的 `ApiError`
   - 2xx 带 JSON body：返回解析后的 JSON
   - 204：返回 `null`
   - 辅助方法：`getJson`、`postJson`、`postForm`（最后那个给 `/auth/login` 用，因为它要 `application/x-www-form-urlencoded` body）
4. **`src/stores/auth.ts`**（Pinia）：
   - state：`user: User | null`、`initialized: boolean`
   - getter：`isAuthenticated: boolean`
   - actions：`register({email, password})`、`login({email, password})`、`logout()`、`fetchMe()`、`init()`
   - `init()` 调一次 `fetchMe()`，401 静默吞掉（表示"未登录"）
   - `login()` 调 `/auth/login` 之后调 `fetchMe()` 把 `user` 填上

**人工验证（浏览器 console）。**
```js
// 在 http://localhost:5173（Vite dev server），DevTools console：
fetch('/health', {credentials:'include'}).then(r => r.json()).then(console.log)
// 期望：{status: "ok"}  ← 证明 Vite proxy 转给 FastAPI 了
```

```js
// 页面加载完（App.vue 装了 Pinia），console 里：
const auth = pinia.state.value.auth  // 或者临时挂 window 上方便调试
// 确认 auth.user === null，auth.initialized === true
```

**验收。** `/health` 能 proxy 过去；auth store 加载无报错；在 console 调 `auth.login(...)`（用之前 curl 注册过的真实账户）能填 `auth.user`，DevTools "Application" 面板能看到 `http://localhost:5173` 下的 `trading_journal_session` cookie。

---

### F0.3 — Auth 页面 + router guard

**目标。** 完整 UI 流程：注册 → 自动登录 → dashboard → 登出 → 回登录页。刷新不掉登录态。

**任务。**
1. **`src/router/index.ts`**：
   - 路由：`/login` → `LoginView`、`/register` → `RegisterView`、`/` → `DashboardView`（`meta: { requiresAuth: true }`）
   - `beforeEach` guard：
     - `to.meta.requiresAuth && !auth.isAuthenticated` → 跳 `/login`
     - `to.path in ['/login', '/register'] && auth.isAuthenticated` → 跳 `/`
2. **`src/main.ts`** 必须 `await authStore.init()` **再** `router.isReady()`，否则刷新页面时首次导航在 `/users/me` resolve 之前发生，用户会看到 `/login → /` 的闪烁
3. **`src/App.vue`** provider 栈最终形态：
   ```vue
   <n-config-provider :theme="null">
     <n-message-provider>
       <n-dialog-provider>
         <router-view />
       </n-dialog-provider>
     </n-message-provider>
   </n-config-provider>
   ```
   （`useMessage()` / `useDialog()` 这些 composable 需要能找到 provider context。）
4. **`LoginView.vue`** —— `n-form` 装 `email` + `password`，提交调 `auth.login()`，成功 `router.push('/')`，出错用 `useMessage().error(err.message)`
5. **`RegisterView.vue`** —— `n-form` 装 `email` + `password`，注册成功立即调 `auth.login()`（同密码）然后 `router.push('/')`；surface 校验错误（400 → "password too short" 等）
6. **`DashboardView.vue`** —— 最小：
   - `n-page-header` 显示 `auth.user.email`
   - 一张 "Accounts (coming in Phase F1)" 的占位卡片
   - "Logout" 按钮 → `auth.logout()` → `router.push('/login')`

**人工验证。** 全流程点穿，详见 §8。

**验收。** 浏览器里完整流程跑通；在 `/` 刷新不会跳到 `/login` 再跳回来；登出后在 `/login` 刷新不会跳走。

---

### F0.4 — 全套 e2e smoke + 后端回归

**目标。** 确认后端没坏，端到端集成扎实。

**任务。**
1. 后端回归：`cd backend && uv run pytest -q && uv run ruff check . && uv run mypy src` —— 必须维持绿色（Phase 2–4：46 个测试通过；后端代码理论上没动）
2. 前端类型检查：`cd frontend && npm run build`（先跑 `vue-tsc --noEmit` 再 `vite build`，两步都得过）
3. 走一遍 §8 的人工流程
4. 更新 `project_tech_stack` memory：把 "single-container Docker SSR" 改成 "single-container Docker SPA（FastAPI 服务 Vite-built `dist/`）"

**验收。** 检查全绿、人工流程跑通、memory 更新。

## 6. 远程 SSH 开发

你已经在后端用 SSH local-forward。前端也得加一份。

```bash
# 操作机：
ssh -fNL 8000:127.0.0.1:8000 -L 5173:127.0.0.1:5173 user@server
```

之后操作机 `http://localhost:8000`（后端）和 `http://localhost:5173`（Vite dev）都能用。

### Dev 期长跑 Vite

跟 `uvicorn` 一样，长跑、扛 SSH 断连：

```bash
# 服务器 pane 1：
tmux new -s backend
cd backend
uv run uvicorn trading_journal.main:app --host 127.0.0.1 --port 8000 --reload
# Ctrl-b d

# pane 2：
tmux new -s frontend
cd frontend
npm run dev    # 按 vite.config.ts 绑 127.0.0.1:5173
# Ctrl-b d
```

### HMR 走隧道

Vite 的 HMR 用浏览器到 Vite dev server 的 WebSocket。SSH local-forward 默认转 WS upgrade，不用特殊配。如果 HMR 真挂了，退路：`npm run dev -- --hmr.clientPort 5173` 强制 client URL。

### 为什么绑 127.0.0.1

跟后端同一个理由：把端口挡在 LAN 之外，挡在公网路由之外。SSH 隧道是唯一入口。**不要** `npm run dev -- --host 0.0.0.0`，除非你清楚你在暴露什么。

## 7. 测试架构

**F0 不写自动化前端测试。** 理由：

- 逻辑面太小：~5 个 store action、~3 个轻逻辑 view、1 个 router guard
- 手动点穿比写测试还快
- 把 Vitest、Vue Test Utils、jsdom、组件 mock 这套搭起来是 1 天的兔子洞，F0 规模下不划算

**仍然自动化的部分：**

- **后端 pytest**（Phase 2–4：46 个测试） —— **F0 全程必须绿**，作为回归挡板。每个 sub-phase 前后都跑
- **`vue-tsc` 走 `npm run build`** —— TypeScript 在编译期能挡住大部分前端 regression

**什么时候才该加测试**（F0 之后）：

- **Vitest + Vue Test Utils** 在 auth store 和 HTTP wrapper 长出超过 F0 的内容时加
- **Playwright** 在攒到 ≥3 个值得自动化的用户旅程时加（注册、CRUD 一个 account、看带 positions 的 dashboard 等）—— 大概 F2 或 F3
- 值得延后的原因：e2e 配套（容器化浏览器、用 test-only API 灌 DB 等）本身是不小的工程

## 8. 人工验证全套

完整点穿，覆盖 F0。F0.3 之后跑（对着裸 `npm run dev` + uvicorn）。

> 前置：后端在 `127.0.0.1:8000`、SQLite migrate 到 head、SSH 隧道 8000 和 5173 都通。

1. 浏览器 → `http://localhost:5173/` → 期望：立刻跳 `/login`（还没 cookie）
2. 在 `/login` 点 "Register" 链接 → 到 `/register`
3. 填 `alice@example.com` / `correct horse battery` → submit → 期望：跳 `/`，看到 "Welcome, alice@example.com"
4. DevTools → Application → Cookies → `localhost:5173` → 期望：`trading_journal_session=...`，HttpOnly，SameSite=Lax
5. **刷新页面**（F5）→ 期望：还在 `/`，还登录态（不闪 `/login`）
6. 点 "Logout" → 期望：cookie 没了，回 `/login`
7. 直接访问 `/` → 期望：跳回 `/login`
8. 用同一组 credential 再次登录 → 期望：回到 `/`
9. 服务器上查 `access_tokens` 表：
   ```bash
   sqlite3 backend/dev.db "SELECT count(*) FROM access_tokens"
   # 期望：1（第 8 步之后）
   ```
10. 边界情况：
    - 重复注册同邮箱 → 期望：toast 报 "user already exists"
    - 登录密码错 → 期望：toast 报 "bad credentials"
    - 注册时填 `pw`（5 字符）→ 期望：toast 报密码长度

## 9. 本 tracer bullet 之后

F0 出货后，下一波迭代（每一项一节短计划，必要时单独成文）：

1. **F1 — Account CRUD UI。** Account 列表（`n-data-table`）、创建表单（modal 或独立页）、编辑、软删带 archived 过滤开关。引入 `openapi-typescript` 做 codegen，停止手写类型。预计：一个 session 集中干。
2. **F2 — Instrument + Position 骨架。** 依赖后端 Phase 5+（Instrument 和 Position CRUD endpoint，目前未建）。带策略感知的 Position 创建流程。
3. **F3 — Trade 录入。** 原子 trade 录入表单；多腿单 / assignment pair 等场景用 `order_group_id` 的 UX 包装。
4. **F4 — 只读 dashboard 和图表。** 在仓 positions 表、平仓 PnL 历史、按 currency 分桶的组合摘要（参见 [data-model.md §6](./data-model.md#currency-placement)）。
5. **F5（或后端 Phase 5）— 生产构建接线。** 后端 `main.py` 加 `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`，更新 Dockerfile 走 multi-stage build 把 `frontend/dist` 烤进 runtime image。单容器部署在这一刻锁定。

---

## Changelog

- **v0.1（2026-05-18）** —— 初版计划。Phase F0 覆盖 Vite + Vue 3 + Naive UI 脚手架、auth 页面、router/store/proxy 接线。后端不改动。F1+ 延后。
