<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { ApiError } from '../api/types'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

async function handleLogout(): Promise<void> {
  try {
    await auth.logout()
  } catch (err) {
    // A 401 means the session was already gone — silent. Anything else surfaces.
    if (!(err instanceof ApiError && err.status === 401)) {
      const msg = err instanceof ApiError ? err.message : 'Logout failed: unexpected error.'
      message.error(msg)
    }
  }
  await router.push({ name: 'login' })
}
</script>

<template>
  <n-layout style="min-height: 100vh;">
    <n-layout-header bordered style="padding: 0 1.5rem;">
      <n-space justify="space-between" align="center" style="height: 64px;">
        <n-h2 style="margin: 0; font-size: 18px;">Trading Journal</n-h2>
        <n-space align="center" :size="12">
          <n-text v-if="auth.user" depth="2">{{ auth.user.email }}</n-text>
          <n-button size="small" @click="handleLogout">Logout</n-button>
        </n-space>
      </n-space>
    </n-layout-header>

    <n-layout-content content-style="padding: 2rem; max-width: 960px; margin: 0 auto;">
      <n-h1>Welcome{{ auth.user ? `, ${auth.user.email}` : '' }}</n-h1>
      <n-card title="Accounts (coming in Phase F1)">
        <n-text depth="3">
          Account list, create / edit / archive will live here in the next phase.
          The backend endpoints are already in place (see
          <n-text code>GET /accounts</n-text>); the UI just isn't wired yet.
        </n-text>
      </n-card>
    </n-layout-content>
  </n-layout>
</template>
