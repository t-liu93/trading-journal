<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import { useAccounts } from '../composables/useAccounts'
import { useInstruments } from '../composables/useInstruments'
import { useStrategyConfigs } from '../composables/useStrategyConfigs'
import { usePositions } from '../composables/usePositions'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const { accounts, loading: accountsLoading, error: accountsError, refresh: refreshAccounts } = useAccounts()
const { instruments, loading: instrumentsLoading, error: instrumentsError, refresh: refreshInstruments } = useInstruments()
const { configs, loading: configsLoading, error: configsError, refresh: refreshConfigs } = useStrategyConfigs()
const { positions, loading: positionsLoading, error: positionsError, refresh: refreshPositions } = usePositions()

onMounted(async () => {
  await Promise.all([refreshAccounts(), refreshInstruments(), refreshConfigs(), refreshPositions()])
})
</script>

<template>
  <AuthenticatedLayout>
    <n-h1 style="margin-top: 0;">
      Welcome<span v-if="auth.user">, {{ auth.user.email }}</span>
    </n-h1>

    <n-grid :cols="3" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
      <n-grid-item span="3 m:1">
        <n-card title="Your accounts" hoverable>
          <n-skeleton v-if="accountsLoading" text :repeat="2" />
          <template v-else>
            <p class="metric" :class="{ 'metric-error': accountsError }">
              {{ accountsError ? '?' : accounts.length }}
            </p>
            <n-text v-if="accountsError" depth="3" style="font-size: 0.85rem; color: var(--n-color-error, #d03050);">
              Couldn't load accounts: {{ accountsError }}
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
        <n-card title="Positions" hoverable>
          <n-skeleton v-if="positionsLoading" text :repeat="2" />
          <template v-else>
            <p class="metric" :class="{ 'metric-error': positionsError }">
              {{ positionsError ? '?' : positions.length }}
            </p>
            <n-text v-if="positionsError" depth="3" style="font-size: 0.85rem; color: var(--n-color-error, #d03050);">
              Couldn't load positions: {{ positionsError }}
            </n-text>
            <n-text v-else depth="3" style="font-size: 0.85rem;">open positions</n-text>
            <div style="margin-top: 0.75rem;">
              <RouterLink :to="{ name: 'positions' }" class="card-link">
                Browse positions →
              </RouterLink>
            </div>
          </template>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Instruments" hoverable>
          <n-skeleton v-if="instrumentsLoading" text :repeat="2" />
          <template v-else>
            <p class="metric" :class="{ 'metric-error': instrumentsError }">
              {{ instrumentsError ? '?' : instruments.length }}
            </p>
            <n-text v-if="instrumentsError" depth="3" style="font-size: 0.85rem; color: var(--n-color-error, #d03050);">
              Couldn't load instruments: {{ instrumentsError }}
            </n-text>
            <n-text v-else depth="3" style="font-size: 0.85rem;">instruments in catalog</n-text>
            <div style="margin-top: 0.75rem;">
              <RouterLink :to="{ name: 'instruments' }" class="card-link">
                Browse instruments →
              </RouterLink>
            </div>
          </template>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Strategy caps" hoverable>
          <n-skeleton v-if="configsLoading" text :repeat="2" />
          <template v-else>
            <p class="metric" :class="{ 'metric-error': configsError }">
              {{ configsError ? '?' : configs.length }}
            </p>
            <n-text v-if="configsError" depth="3" style="font-size: 0.85rem; color: var(--n-color-error, #d03050);">
              Couldn't load configs: {{ configsError }}
            </n-text>
            <n-text v-else depth="3" style="font-size: 0.85rem;">{{ configs.length }} of 5 strategies configured</n-text>
            <div style="margin-top: 0.75rem;">
              <RouterLink :to="{ name: 'settings-strategies' }" class="card-link">
                Manage strategy caps →
              </RouterLink>
            </div>
          </template>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Trades (Phase F4)" class="card-disabled">
          <n-text depth="3">Coming in Phase F4.</n-text>
          <div style="margin-top: 0.75rem;">
            <n-text depth="3" style="font-size: 0.85rem;">
              Atomic broker fills, multi-leg entries, assignment / exercise pairs.
            </n-text>
          </div>
        </n-card>
      </n-grid-item>

      <n-grid-item span="3 m:1">
        <n-card title="Dashboards (Phase F5)" class="card-disabled">
          <n-text depth="3">Coming in Phase F5.</n-text>
          <div style="margin-top: 0.75rem;">
            <n-text depth="3" style="font-size: 0.85rem;">
              PnL dashboards, charts, and analytics.
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
