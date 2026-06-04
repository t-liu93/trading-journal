import { defineStore } from 'pinia'
import { darkTheme, type GlobalTheme } from 'naive-ui'

export type ThemeMode = 'light' | 'dark'

// localStorage key for the user's persisted choice. Namespaced (`tj-`) so it
// won't collide with anything else served from the same origin.
const STORAGE_KEY = 'tj-theme'

function initialMode(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'light' || stored === 'dark') return stored
  // First visit (nothing stored): honour the OS-level colour preference so the
  // app opens dark for users who already run their system dark.
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/**
 * App-wide light/dark theme state.
 *
 * `naiveTheme` is what `<n-config-provider :theme>` consumes: `null` selects
 * Naive UI's built-in light theme, `darkTheme` its built-in dark one. The choice
 * is persisted to localStorage so it survives reloads, and seeded from the OS
 * preference on first visit.
 */
export const useThemeStore = defineStore('theme', {
  state: () => ({ mode: initialMode() as ThemeMode }),
  getters: {
    isDark: (state): boolean => state.mode === 'dark',
    naiveTheme: (state): GlobalTheme | null => (state.mode === 'dark' ? darkTheme : null),
  },
  actions: {
    setMode(mode: ThemeMode): void {
      this.mode = mode
      localStorage.setItem(STORAGE_KEY, mode)
    },
    toggle(): void {
      this.setMode(this.mode === 'dark' ? 'light' : 'dark')
    },
  },
})
