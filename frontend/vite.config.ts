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
    // Backend API proxy is added in F0.2.
  },
})
