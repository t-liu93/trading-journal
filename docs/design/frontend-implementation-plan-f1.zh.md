# 前端 Phase F1 — Account CRUD UI

**语言：** [English](./frontend-implementation-plan-f1.md) | 中文

> 状态：**DRAFT v0.1**（2026-05-19）。配套文档：[frontend-implementation-plan.md](./frontend-implementation-plan.md)（F0 基础脚手架）和 [data-model.md](./data-model.md)。写代码前先在这里迭代。

## 1. 目的

F0 证明了 auth + router + cookie 接线是通的。F1 在那个脚手架上**首次铺真正承载数据的页面**：基于 Phase 4 后端 endpoint 的完整 Account CRUD UI。

除了直接的用户价值，F1 更重要的是**为后面每一个实体（Position、Trade、TradePlan、……）奠定可复用 pattern**：

- 从 `/openapi.json` 生成 API 类型（不再手写 interface）
- 资源 API client 模块模式（`src/api/<resource>.ts`）
- View + composable 分离（`AccountsView` + `useAccounts`）
- Modal 形式的 create/edit 共用表单
- 危险操作走 confirm dialog
- Skeleton 加载 + 空状态 + toast 反馈
- 软删 + archived 过滤

这些一次做对，F2（Position）基本就是套同一个食谱。

## 2. 范围

### 在范围内（本计划）

- **`openapi-typescript` codegen** 接入；`src/api/schema.d.ts` 提交 git；删掉手写的 `User` 类型改用生成的
- **`src/api/accounts.ts`** —— 5 个后端 endpoint 的 typed 封装
- **`useAccounts()` composable** —— 页面级 state + actions
- **`AuthenticatedLayout.vue`** 组件 —— header + nav + content slot；Dashboard 和 Accounts 共用
- **`AccountsView.vue`** —— `n-data-table` 列表 + skeleton + 空状态 + "Show archived" toggle + "+ New account" 按钮
- **`AccountFormModal.vue`** —— 共用 modal，create 和 edit 两种模式，带完整的 Naive UI 表单校验
- **删除（归档）二次确认** 通过 `useDialog().warning()`
- **更新的 `DashboardView`** —— 一张 "Your accounts" 卡片链接到 `/accounts`；加占位卡 "Positions (F2)"、"Trades (F3)"，让路线图在 UI 里可见
- **README 更新** —— codegen 工作流写进去
- **后端回归** —— Phase 2–4 pytest 维持 46/46

### 明确不在范围（延后）

- **Accounts 的 Pinia store** —— F1 状态留在 composable 里，等真有 ≥2 个组件需要共享时再升级到 store
- **批量操作**（多选删 / 多选归档）
- **搜索 / 过滤**（archived toggle 之外）
- **排序定制** —— 默认 `created_at` 倒序，不做表头点击排序
- **分页** —— 单用户实际 ≤10 个账户，需要时再加
- **Account 详情页**（独立 route 展示这个 account 下的 positions）—— F2 范围
- **硬删** —— MVP 只有软删
- **前端单元测试**（Vitest）—— 等到 ≥1 个非平凡的纯函数出现再加
- **`openapi-fetch` typed client** —— `openapi-typescript` 类型 + 现有 `http.ts` 够用
- **Tailwind / 自定义 theme** —— Naive UI 默认还能扛

## 3. 技术新增

| 层 | 改动 |
|---|---|
| Dev 依赖 | **`openapi-typescript`**（零运行时开销，只生成一个 `.d.ts`） |
| npm scripts | `codegen` script，拉 `/openapi.json` 写 `src/api/schema.d.ts` |

无新增运行时依赖。无构建配置改动。

## 4. F1 之后的目录结构

```
frontend/src/
├── api/
│   ├── schema.d.ts              ← 新增：openapi-typescript 自动生成，commit 进 git
│   ├── types.ts                 ← 瘦身：只保留 ApiError + auth payload 类型
│   ├── http.ts                  ← 不变
│   └── accounts.ts              ← 新增：typed list/get/create/update/delete 助手
├── composables/                 ← 新增目录
│   └── useAccounts.ts           ← 新增：响应式 list、loading、includeArchived；refresh()
├── components/
│   ├── AuthenticatedLayout.vue  ← 新增：header（app 名 + email + logout）+ nav + <slot />
│   └── AccountFormModal.vue     ← 新增：n-modal 里的 create+edit 共用表单
├── router/
│   └── index.ts                 ← 改：加 /accounts route（requiresAuth）
├── stores/
│   └── auth.ts                  ← 不变
└── views/
    ├── LoginView.vue            ← 不变
    ├── RegisterView.vue         ← 不变
    ├── DashboardView.vue        ← 改：用 AuthenticatedLayout；卡片现在链接到 /accounts
    └── AccountsView.vue         ← 新增：组织 table + modal + dialog
```

## 5. 阶段拆分

按顺序执行。每个 sub-phase 有 **目标**、**任务**、**人工验证**、**验收**。N 没过完别开 N+1。

### F1.1 — `openapi-typescript` codegen

**目标。** API 类型单一来源：后端 Pydantic → `/openapi.json` → `schema.d.ts` → TS import。不再手写维护 `User` interface。

**任务。**
1. `npm install -D openapi-typescript`
2. `package.json` 加 scripts：
   ```json
   {
     "scripts": {
       "codegen": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/schema.d.ts"
     }
   }
   ```
3. uvicorn 跑着，跑一次 `npm run codegen`，产出 `src/api/schema.d.ts`
4. **删掉** `src/api/types.ts` 里手写的 `User` interface，换成：
   ```ts
   import type { components } from './schema'
   export type User = components['schemas']['UserRead']
   ```
5. `src/api/types.ts` 保留：`ApiError` 类、`ApiErrorDetail`、`RegisterPayload`、`LoginPayload`（这些是 app 形态，不是 API 形态）
6. 在 `frontend/README.md` 写 codegen 工作流：
   - 什么时候要 regen（后端 schema 改动后）
   - `schema.d.ts` 是要 commit 进 git 的
   - regen 时后端必须本地跑着

**人工验证。**
```bash
cd frontend
npm install
# 后端在 :8000 跑着，然后：
npm run codegen
# → 写出 src/api/schema.d.ts；git diff 看到变化
npm run build
# → vue-tsc + vite 跟新生成的类型都通过
```

**验收。** `src/api/schema.d.ts` 存在且已 commit；项目里不再有任何手写的 model interface；`npm run build` 通过。

---

### F1.2 — Account API client

**目标。** 每个后端 endpoint 一个 typed 函数，跟 view 代码隔离。

**任务。**

1. 新建 `src/api/accounts.ts`：
   ```ts
   import type { components } from './schema'
   import { http } from './http'

   export type Account       = components['schemas']['AccountRead']
   export type AccountCreate = components['schemas']['AccountCreate']
   export type AccountUpdate = components['schemas']['AccountUpdate']

   export const accountsApi = {
     list:   (includeArchived = false) => http.get(`/accounts?include_archived=${includeArchived}`) as Promise<Account[]>,
     get:    (id: string)              => http.get(`/accounts/${id}`)                              as Promise<Account>,
     create: (payload: AccountCreate)  => http.post('/accounts', payload)                          as Promise<Account>,
     update: (id: string, payload: AccountUpdate) => http.patch(`/accounts/${id}`, payload)         as Promise<Account>,
     remove: (id: string)              => http.delete(`/accounts/${id}`)                           as Promise<null>,
   }
   ```
2. （还没有 view 消费 —— 留到 F1.3+。）

**人工验证。** 单独无法验证，留到 F1.3。

**验收。** 文件编译通过；类型签名跟后端对得上。

---

### F1.3 — `AuthenticatedLayout` + `useAccounts` composable + `AccountsView` 骨架

**目标。** 共用 layout 抽出来。`/accounts` route 渲染一张带 skeleton + 空状态的空表格。还**没有** create/edit/delete。

**任务。**

1. **`components/AuthenticatedLayout.vue`**：
   - `<n-layout>` 包 `<n-layout-header bordered>`
   - Header：app 标题（左）、nav（`Dashboard | Accounts`）、用户 email + Logout 按钮（右）
   - Logout 复用现在 `DashboardView` 里的同一段
   - Content 用 `<slot />`
2. **`composables/useAccounts.ts`**：
   ```ts
   export function useAccounts() {
     const accounts        = ref<Account[]>([])
     const loading         = ref(false)
     const error           = ref<string | null>(null)
     const includeArchived = ref(false)

     async function refresh() {
       loading.value = true
       error.value = null
       try {
         accounts.value = await accountsApi.list(includeArchived.value)
       } catch (err) {
         error.value = err instanceof ApiError ? err.message : 'Failed to load accounts.'
       } finally {
         loading.value = false
       }
     }

     // toggle 翻动时自动刷新
     watch(includeArchived, refresh)

     return { accounts, loading, error, includeArchived, refresh }
   }
   ```
3. **`views/AccountsView.vue`**（第一刀，还没 modal）：
   - 包在 `<AuthenticatedLayout>` 里
   - 页面 header：标题 + 右对齐的 `<n-switch>` "Show archived" + `<n-button>` "+ New account"（这个 sub-phase 先 disabled）
   - `<n-data-table>` 列：Name、Broker、Type、Currency、Notes、Created、Actions（占位）
   - 加载：`<n-data-table :loading="loading">`（自带 skeleton）
   - 空状态：`<n-empty>` "No accounts yet — create one to get started" 加一个也 disabled 的 `<n-button>`
   - Archived 行：用 `depth="3"`（灰字）+ Name 列加小 `<n-tag size="small">archived</n-tag>`
4. **`router/index.ts`** 加：
   ```ts
   {
     path: '/accounts',
     name: 'accounts',
     component: () => import('../views/AccountsView.vue'),
     meta: { requiresAuth: true },
   }
   ```
5. **`views/DashboardView.vue`**：重构用 `<AuthenticatedLayout>`。把 "coming in F1" 占位换成 `<n-card>` "Your accounts" + 一个 `<RouterLink to="/accounts">` "Manage accounts →"。再加两张占位卡："Positions (F2)" 和 "Trades (F3)"，让接下来的路线图在 UI 里看得见。

**人工验证。**

- 登录，通过新加的 header nav 进 `/accounts`
- 空 DB → 看到 `<n-empty>` "No accounts yet"
- 用 curl 加一个 account（或者等 F1.4），刷新 → 行出现
- 翻 "Show archived" → 表格重新拉取（Network tab 看到 `GET /accounts?include_archived=true`）
- `/` 还是 Dashboard，新的 "Your accounts" 卡片链接到 `/accounts`

**验收。** 上面这些都过；build 通过；console 无报错。

---

### F1.4 — `AccountFormModal`（create + edit）

**目标。** 点 "+ New account" 或行内 edit → modal 弹出 → 表单 → 提交 → 列表刷新。

**任务。**

1. **`components/AccountFormModal.vue`** props：
   - `:show`（boolean，`v-model:show` 双向）
   - `:mode` —— `'create' | 'edit'`
   - `:initial` —— edit 模式下的部分 `Account`（create 模式忽略）
   - Emit：`@saved` 带回结果 `Account`（parent 自己决定怎么用 —— 一般是 `refresh()` + close）
2. 表单字段（全 Naive UI）：
   - `name` —— `<n-input>`；rule：required，max 255
   - `broker` —— `<n-input>`；rule：required，max 255
   - `account_type` —— `<n-select>` 选项 `cash | margin | paper`；rule：required
   - `base_currency` —— `<n-select>` 带常用选项（USD、EUR、GBP、JPY、CHF、CAD、AUD、HKD）**加** `filterable` 允许手打稀有代码；rule：required + regex `^[A-Z]{3}$`
   - `notes` —— `<n-input type="textarea">`；optional
3. Submit handler：组 payload（用户留默认的字段不带），调 `accountsApi.create` 或 `accountsApi.update`，成功 `useMessage().success(...)` + `emit('saved', result)` + 关 modal
4. Error handler：`ApiError` → `useMessage().error(err.message)`；其它 re-throw
5. 校验时机：只在 submit 时校验（不一边打字一边唠叨）—— Naive UI 的 `formRef.value?.validate()` 返回 promise
6. 接进 `AccountsView`：
   - "+ New account" 按钮 → 用 create 模式开 modal
   - 行 Actions 列 → "Edit" 按钮（只在非 archived 行）→ 用 edit 模式开 modal，`:initial="row"`
   - `@saved` → 调 `refresh()`，关 modal

**人工验证。**

- 点 "+ New account" → modal 打开，所有字段空
- 啥都不填提交 → 字段级红字错误出现
- 填合法值 → modal 关闭，成功 toast，行出现在表格里
- 点行的 "Edit" → modal 打开预填值，currency 下拉显示现有值
- 改 `notes`，保存 → 行更新，成功 toast
- 试 `base_currency = usd` → 校验错误，根本不发请求
- 用后端会拒绝的值（比如手动在 DevTools 里加 `?` —— 表单走不到，但 DevTools 能改）→ ApiError 通过 toast 展示

**验收。** create 工作、edit 工作、submit 时触发校验、成功/失败 toast 出来、列表自动刷新。

---

### F1.5 — 删除（归档）确认流程

**目标。** 行的 "Archive" 按钮弹确认 dialog；确认后软删 + 刷新 + toast。

**任务。**

1. `AccountsView` 的 Actions 列加 "Archive" 按钮（紧挨 "Edit"，只在非 archived 行显示）
2. 点击 handler：
   ```ts
   const dialog = useDialog()

   function handleArchive(row: Account) {
     dialog.warning({
       title: 'Archive this account?',
       content: `"${row.name}" will be hidden from your default list. You can recover it any time by toggling "Show archived".`,
       positiveText: 'Archive',
       negativeText: 'Cancel',
       onPositiveClick: async () => {
         try {
           await accountsApi.remove(row.id)
           message.success(`Archived "${row.name}"`)
           await refresh()
         } catch (err) {
           if (err instanceof ApiError) message.error(err.message)
           else throw err
         }
       },
     })
   }
   ```
3. 文案用 "Archive" 不用 "Delete" —— 强调可恢复

**人工验证。**

- 点行的 "Archive" → dialog 弹出，显示账户名 + 可恢复提示
- 点 "Cancel" → 啥也不发生
- 点 "Archive"（positive）→ 行从列表消失，toast "Archived X"
- 翻 "Show archived" → archived 行回来了，灰字、带 `[archived]` tag、没有 Edit/Archive 按钮

**验收。** 全流程通；archived 状态在 F1 里只能通过 toggle 看到（**F1 不做 unarchive UI** —— 见 §9）。

---

### F1.6 — Dashboard 收尾 + nav

**目标。** Dashboard 现在感觉像个真正的 home，不是占位。

**任务。**

1. `DashboardView.vue` 在 F1.3 之后已经用上 `AuthenticatedLayout`。打磨内容：
   - `<n-h1>Welcome, {{ auth.user.email }}</n-h1>`
   - `<n-grid :cols="3" x-gap="16">`：
     - Card 1："Your accounts" —— 从 `useAccounts()` 拿真实数量（mount 时调 `refresh()`），"Manage accounts →" 链接
     - Card 2："Positions (Phase F2)" —— disabled / `depth=3` 样式，没链接
     - Card 3："Trades (Phase F3)" —— 同上 disabled 样式
2. Header nav（在 `AuthenticatedLayout` 里）当前 route 高亮 —— Naive UI `<n-menu :value="route.name">` 或纯 CSS

**人工验证。**

- 登录后进 `/` → 看到 Welcome + 三张卡
- "Your accounts" 卡片显示真实数量（跟 `sqlite3 dev.db "SELECT count(*) FROM accounts WHERE archived_at IS NULL"` 对得上）
- 点 "Manage accounts →" → 跳 `/accounts`
- Header nav：点 "Dashboard" 或 "Accounts" 正确导航；当前 item 视觉上有区别

**验收。** Dashboard 功能上有意义；nav 工作。

---

### F1.7 — 回归 + smoke + memory 更新

**目标。** 合并前确认 baseline 干净。

**任务。**

1. 后端：`uv run pytest -q && uv run ruff check . && uv run mypy src` —— 必须维持绿色（46/46，ruff clean，mypy strict clean）
2. 前端：`npm run build` —— 必须通过
3. 走一遍 §8 的人工 recipe
4. （可选）更新 `project_overview` memory，标记 F1 完成

**验收。** 全绿；人工 recipe 通过；可以 commit。

## 6. Codegen 工作流

F1.1 引入的 `openapi-typescript` 接入的操作手册。

### 什么时候要 regen

- 后端**任何**改请求/响应形状的改动后（新 endpoint、新字段、字段改名、类型改、枚举加值）
- 后端依赖升级影响 Pydantic v2 → vX 行为（罕见）

### 怎么 regen

```bash
# 后端必须跑在 :8000
cd frontend
npm run codegen
git diff src/api/schema.d.ts   # 检查改了什么
npm run build                  # 确认下游没坏
```

### 什么要 commit

- `src/api/schema.d.ts` **是 commit 的**，当作"自动生成但纳入版本管理"（这样新 clone 不用先跑后端就能编译）
- 不要手改 —— 重跑 `codegen` 而不是手改

### 可选后续（F1 之后）

- **CI 检查**：一个 job 重跑 codegen + `git diff --exit-code`，抓"后端改了但忘记 regen"
- **pre-commit hook**：同样的想法，本地执行

## 7. 测试策略

跟 F0 一样 —— **F1 不写前端自动化测试**。加测试的合理时机：

- `useAccounts()` 有值得隔离的逻辑（比如乐观更新、请求取消）
- 超过 2-3 个 view 共享组件行为

目前：后端 pytest + `vue-tsc` + 人工 click-through 足够。

**后端回归是硬门槛** —— Phase 2–4 的 46 个测试 F1 全程必须绿。

## 8. 人工验证 recipe

F1.5 之后跑（对着裸 `uvicorn` + `npm run dev`）。

> 前置：后端在 `127.0.0.1:8000`，前端在 `localhost:5173`，SSH 隧道两个都通，DB 已重置。

1. 注册 `alice@example.com` / `correct horse battery` → 落地 `/`
2. Dashboard 显示三张卡：`Your accounts (0)`、`Positions (F2)`、`Trades (F3)`
3. 点 "Manage accounts →" → 到 `/accounts`，看到 `<n-empty>` "No accounts yet"
4. 点 "+ New account"：
   - Modal 打开
   - 啥都不填提交 → 5 个字段错误出现
   - 填 `name=IBKR Margin, broker=IBKR, account_type=margin, base_currency=USD, notes=primary`
   - 提交 → modal 关闭、成功 toast、行出现
5. Header nav：点 "Dashboard" → "Your accounts (1)"；点 "Accounts" → 列表还在
6. 行的 "Edit" → modal 预填值；把 `notes` 改成 `edited`；提交 → 行更新
7. "Archive" → dialog → "Archive" → 行从列表消失，toast "Archived IBKR Margin"
8. 翻 "Show archived" → 行回来了，灰字带 `[archived]` tag，Actions 列没有 Edit/Archive
9. 翻回去 → 又空了
10. 后端 log 全程：只有预期的请求，没 500，没 IntegrityError
11. DB sanity：
    ```bash
    sqlite3 backend/dev.db "SELECT name, archived_at FROM accounts"
    # 期望：IBKR Margin | 2026-...
    ```
12. 刷新 `/accounts` (F5) → 还在 `/accounts`，还登录
13. Logout → cookie 清掉；`/accounts` → guard 跳 `/login`
14. （跨用户）注册 `bob@example.com`，作为 bob 登录，去 `/accounts` → 看到空列表（Alice 的 archived 账户 bob 看不到）

## 9. F1 之后

F1 出货后，下一波迭代：

1. **F1.5 follow-up：Unarchive 按钮。** F1 不做，但需要时加起来很简单 —— Actions 列在 archived 行加 "Unarchive" 按钮，调一个未来的 `PATCH /accounts/{id}` 设 `{archived_at: null}`（注意：后端现在只通过 `DELETE` 软删，没办法清 archived_at —— 要加要么 `POST /accounts/{id}/unarchive` 新 route，要么扩 PATCH 接受 archived_at 字段）
2. **F2 —— Instrument + Position UI。** 依赖后端 Phase 5+（那些 endpoint 现在不存在）。带策略感知的 position 创建流程。
3. **F3 —— Trade 录入。** 多腿表单、`order_group_id` UX。
4. **F4 —— 只读 dashboard 和图表。** 按 currency 分桶聚合 PnL（参见 [data-model.md §6](./data-model.md#currency-placement)）。
5. **F5 / 后端 Phase 5 —— 生产构建接线。** 单容器 Docker。
6. **前端测试。** Vitest 用于 `useAccounts` 和 API client 长出非平凡逻辑时；Playwright 用于攒到 ≥3 个用户旅程 e2e。

---

## Changelog

- **v0.1（2026-05-19）** —— F1 初版计划。Codegen + Account CRUD UI + 共用 layout。后端不动。
