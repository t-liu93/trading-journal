<script setup lang="ts">
import { computed, h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { type MenuOption, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'
import { ApiError } from '../api/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()
const message = useMessage()

// Horizontal nav rendered through Naive's n-menu so the active item gets the
// library's theming for free. Each `label` returns a RouterLink VNode so
// clicks go through the SPA router (no full reload).
const menuOptions = computed<MenuOption[]>(() => [
  {
    key: 'dashboard',
    label: () => h(RouterLink, { to: { name: 'dashboard' } }, () => 'Dashboard'),
  },
  {
    key: 'accounts',
    label: () => h(RouterLink, { to: { name: 'accounts' } }, () => 'Accounts'),
  },
  {
    key: 'positions',
    label: () => h(RouterLink, { to: { name: 'positions' } }, () => 'Positions'),
  },
  {
    key: 'instruments',
    label: () => h(RouterLink, { to: { name: 'instruments' } }, () => 'Instruments'),
  },
  {
    key: 'settings',
    label: () => h(RouterLink, { to: { name: 'settings-strategies' } }, () => 'Settings'),
  },
])

const activeKey = computed(() => {
  const name = (route.name as string | undefined) ?? ''
  if (name === 'position-detail') return 'positions'
  return name
})

async function handleLogout(): Promise<void> {
  try {
    await auth.logout()
  } catch (err) {
    // Non-401 failure (network / 5xx): the server session may still be valid,
    // so we stay put and surface the error rather than navigating away.
    const msg = err instanceof ApiError ? err.message : 'Logout failed: unexpected error.'
    message.error(msg)
    return
  }
  await router.push({ name: 'login' })
}
</script>

<template>
  <n-layout style="min-height: 100vh;">
    <n-layout-header bordered class="app-header">
      <div class="app-header-row">
        <div class="app-brand">Trading Journal</div>

        <n-menu
          mode="horizontal"
          :value="activeKey"
          :options="menuOptions"
          responsive
          :dropdown-props="{ trigger: 'click' }"
          class="app-nav"
        />

        <div class="app-header-right">
          <n-text v-if="auth.user" :depth="3" class="app-user-email">{{ auth.user.email }}</n-text>
          <n-button
            size="small"
            quaternary
            circle
            :title="theme.isDark ? 'Switch to light mode' : 'Switch to dark mode'"
            aria-label="Toggle dark mode"
            @click="theme.toggle"
          >
            <template #icon>
              <n-icon :size="18">
                <!-- Show the icon for the mode you'd switch TO: sun while dark,
                     moon while light. Inline feather SVGs (currentColor) — no
                     icon-library dependency for two glyphs. -->
                <svg
                  v-if="theme.isDark"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <circle cx="12" cy="12" r="5" />
                  <line x1="12" y1="1" x2="12" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="23" />
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                  <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                  <line x1="1" y1="12" x2="3" y2="12" />
                  <line x1="21" y1="12" x2="23" y2="12" />
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                  <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              </n-icon>
            </template>
          </n-button>
          <n-button size="small" @click="handleLogout">Logout</n-button>
        </div>
      </div>
    </n-layout-header>

    <n-layout-content content-style="padding: 2rem; max-width: 1100px; margin: 0 auto;">
      <slot />
    </n-layout-content>
  </n-layout>
</template>

<style scoped>
.app-header {
  padding: 0 1rem;
}
.app-header-row {
  display: flex;
  align-items: center;
  /* Single row, always. The three groups never wrap — instead the nav
     (flex: 1 1 auto + min-width: 0) shrinks, and n-menu's `responsive` prop
     collapses it to a "..." dropdown when there isn't room. The email hides
     below 640px (see media query) to free up space on phones. */
  flex-wrap: nowrap;
  column-gap: 1.5rem;
  height: 64px;
}
.app-brand {
  flex: 0 0 auto;
  font-size: 18px;
  font-weight: 500;
  white-space: nowrap;
}
.app-nav {
  flex: 1 1 auto;
  min-width: 0;
}
.app-header-right {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.app-user-email {
  /* inline-block so max-width / ellipsis take effect; colour comes from n-text's
     `depth` so it adapts to light/dark instead of being hardcoded. */
  display: inline-block;
  vertical-align: middle;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

/* On narrow viewports, hide the email — it's the least-essential piece of
   the header. The user can still see it on the dashboard / accounts page. */
@media (max-width: 640px) {
  .app-user-email {
    display: none;
  }
}
</style>
