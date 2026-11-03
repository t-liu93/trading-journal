import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// Keep test transforms independent of vite.config.ts: its component auto-import
// plugin writes the generated src/components.d.ts file.
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.spec.ts'],
    clearMocks: true,
    restoreMocks: true,
  },
})
