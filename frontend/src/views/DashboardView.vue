<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import { useAccounts } from '../composables/useAccounts'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const { accounts, loading, error, refresh } = useAccounts()

onMounted(refresh)
</script>

<template>
  <AuthenticatedLayout>
    <n-h1 style="margin-top: 0;">
      Welcome<span v-if="auth.user">, {{ auth.user.email }}</span>
    </n-h1>

    <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <n-grid-item span="3 m:1">
        <n-card title="Your accounts" hoverable>
          <n-skeleton v-if="loading" text :repeat="2" />
          <template v-else>
            <p class="metric" :class="{ 'metric-error': error }">
              {{ error ? '?' : accounts.length }}
            </p>
            <n-text v-if="error" depth="3" style="font-size: 0.85rem; color: var(--n-color-error, #d03050);">
              Couldn't load accounts: {{ error }}
            </n-text>
            <n-text v-else depth="3" style="font-size: 0.85rem;">active accounts</n-text>
            <div style="margin-top: 0.75rem;">
              <RouterLink :to="{ name: 'accounts' }" class="card-link">
                Manage accounts →
              </RouterLink>
            </div>
          </template>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Positions (Phase F2)" class="card-disabled">
          <n-text depth="3">Coming in Phase F2.</n-text>
          <div style="margin-top: 0.75rem;">
            <n-text depth="3" style="font-size: 0.85rem;">
              Wheel, iron condor, PMCC, spot — all your in-flight strategies will live here.
            </n-text>
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Trades (Phase F3)" class="card-disabled">
          <n-text depth="3">Coming in Phase F3.</n-text>
          <div style="margin-top: 0.75rem;">
            <n-text depth="3" style="font-size: 0.85rem;">
              Atomic broker fills, multi-leg entries, assignment / exercise pairs.
            </n-text>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>
  </AuthenticatedLayout>
</template>

<style scoped>
.metric {
  font-size: 2.25rem;
  font-weight: 500;
  margin: 0;
  line-height: 1.1;
}
.metric-error {
  color: var(--n-color-error, #d03050);
}
.card-link {
  color: var(--n-color-primary, #18a058);
  text-decoration: none;
  font-weight: 500;
}
.card-link:hover {
  text-decoration: underline;
}
.card-disabled {
  opacity: 0.55;
}
.card-disabled :deep(.n-card-header__main) {
  color: var(--n-text-color-3, rgba(0, 0, 0, 0.38));
}
</style>
