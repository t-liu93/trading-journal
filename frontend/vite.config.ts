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
    // Bind localhost only — the operator's laptop reaches us via SSH local-forward.
    // Never bind 0.0.0.0 unless you intend to expose the dev server to the LAN.
    host: '127.0.0.1',
    port: 5173,
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
