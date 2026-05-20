<script setup lang="ts">
import { computed, h } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { type MenuOption, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { ApiError } from '../api/types'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
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
])

const activeKey = computed(() => (route.name as string | undefined) ?? '')

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
          <span v-if="auth.user" class="app-user-email">{{ auth.user.email }}</span>
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
  font-size: 14px;
  color: var(--n-text-color-2, rgba(0, 0, 0, 0.6));
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
