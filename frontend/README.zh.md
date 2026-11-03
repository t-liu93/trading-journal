# 前端

> [English](README.md) · **中文**

Vue 3 + TypeScript + Vite + Naive UI SPA。当前 CI／Docker 使用 Node 22，使用锁文件并保留 `.npmrc`。后端的一次性 HTTP 环境看[开发指南](../docs/development.zh.md)。

## 命令

在 `frontend/` 运行 `npm ci`，再用 `npm run dev` 启动 `http://localhost:5173`。Vite 使用严格端口，把 `/api` 代理到 `127.0.0.1:8000`。端口占用时核对进程归属，不杀无关进程；浏览器 hostname 保持一致。

`npm run build` 运行 vue-tsc 和 Vite。`npm run preview` 只供检查构建产物，涉及 API 的验证使用后端或[完整走查](../docs/walkthrough.zh.md)。

## API 类型与验证

`src/api/schema.d.ts` 是已提交的生成产物。后端运行在 8000 后执行 `npm run codegen`，检查 `git diff -- src/api/schema.d.ts`，再跑 `npm run build`。任何 OpenAPI 变化都重新生成，包括影响输出的描述变化，不手改生成类型。

尚无前端单元／E2E 脚本，[QA-01](../docs/plan/roadmap.zh.md) 追踪有意义的覆盖。构建通过不证明浏览器行为；任务交互使用合成数据，手工／自动证据分开。替换一次性数据库后 session 失效，只清测试浏览器 cookie 并重登，不删除真实记录。

当前范围以[路线图](../docs/plan/roadmap.zh.md)和任务卡为准，P/F 设计计划是历史记录。
