import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Auto-import Naive UI components on use. Generates `src/components.d.ts`
    // so editors get full type info without explicit `import { NButton } ...`.
    Components({
      resolvers: [NaiveUiResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  server: {
    // Bind `localhost` (resolves to 127.0.0.1) — `localhost` is what the README
    // and SSH tunnel docs use, and what Vite prints in its startup banner.
    // Cookies are keyed on the literal hostname (`localhost` ≠ `127.0.0.1` for
    // cookie storage), so keeping ONE host name everywhere prevents the "I
    // logged in but my session keeps disappearing" trap.
    host: 'localhost',
    port: 5173,
    // Fail loudly if port 5173 is already taken (e.g., a leaked previous Vite
    // process). Without this, Vite silently picks the next free port (5174,
    // 5176, …) — but the SSH tunnel and any browser bookmarks still point at
    // 5173, so the user ends up looking at stale code without realising it.
    strictPort: true,
    // Reverse-proxy API paths to the FastAPI backend (default uvicorn dev port).
    // The browser sees a single origin (localhost:5173), so the backend stays
    // CORS-free in both dev and prod. See docs/design/frontend-implementation-plan.md §5.
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/users': 'http://127.0.0.1:8000',
      '/accounts': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
