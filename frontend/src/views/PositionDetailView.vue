<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import PositionFormModal from '../components/PositionFormModal.vue'
import PositionStatusBadge from '../components/PositionStatusBadge.vue'
import WheelMetaForm from '../components/WheelMetaForm.vue'
import PmccMetaForm from '../components/PmccMetaForm.vue'
import TradePlanList from '../components/TradePlanList.vue'
import TradePlanForm from '../components/TradePlanForm.vue'
import PositionTradesTab from '../components/PositionTradesTab.vue'
import TradeEntryModal from '../components/TradeEntryModal.vue'
import { usePosition } from '../composables/usePosition'
import { instrumentsApi, type Instrument } from '../api/instruments'
import { ApiError } from '../api/types'
import {
  computeDaysOpen,
  computePnlTotal,
  computeRoi,
  computeAnnualizedRoi,
  computeResult,
  formatAmount,
} from '../utils/positionDerived'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const positionId = computed(() => route.params.id as string)
const { position, loading, error, refresh, close, remove } = usePosition(positionId)

const instrument = ref<Instrument | null>(null)
const showEditModal = ref(false)
const showAddTradeModal = ref(false)
const activeTab = ref((route.query.tab as string) || 'overview')
const tradePlanListRef = ref<InstanceType<typeof TradePlanList> | null>(null)
const planLoaded = ref(false)
const planStartExpanded = ref(false)
const tradesTabRef = ref<InstanceType<typeof PositionTradesTab> | null>(null)

function handlePlanLoaded(isEmpty: boolean) {
  planStartExpanded.value = isEmpty
  planLoaded.value = true
}

const symbol = computed(() => instrument.value?.symbol ?? '—')

function prettifyStrategy(s: string): string {
  const map: Record<string, string> = {
    wheel: 'Wheel',
    iron_condor: 'Iron Condor',
    pmcc: 'PMCC',
    spot_stock: 'Spot Stock',
    spot_forex: 'Spot Forex',
  }
  return map[s] ?? s
}

const daysOpen = computed(() => {
  if (!position.value) return 0
  return computeDaysOpen(position.value.opened_at, position.value.closed_at)
})

const pnlTotal = computed(() => {
  if (!position.value) return 0
  return computePnlTotal(position.value.net_cash_flow)
})

const roi = computed(() => {
  if (!position.value) return null
  return computeRoi(pnlTotal.value, position.value.capital_used)
})

const annualizedRoi = computed(() => {
  if (!position.value) return null
  return computeAnnualizedRoi(pnlTotal.value, position.value.capital_used, daysOpen.value)
})

const result = computed(() => {
  if (!position.value || position.value.status !== 'closed') return null
  return computeResult(position.value.pnl_realized)
})

const resultColor = computed(() => {
  if (result.value === 'Win') return 'success'
  if (result.value === 'Loss') return 'error'
  if (result.value === 'Breakeven') return 'warning'
  return 'default'
})

function handleTabChange(tab: string) {
  activeTab.value = tab
  router.replace({ query: { tab } })
}

async function handleClosePosition() {
  try {
    await close()
    message.success('Position closed')
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to close position')
  }
}

async function handleDeletePosition() {
  try {
    await remove()
    message.success('Position deleted')
    router.push('/positions')
  } catch (err) {
    message.error(err instanceof ApiError ? err.message : 'Failed to delete position')
  }
}

function handleEditSaved() {
  showEditModal.value = false
  void refresh()
}

function handlePlanSaved() {
  tradePlanListRef.value?.refresh()
}

function handleTradeSaved() {
  showAddTradeModal.value = false
  void refresh()
  // Refresh trades tab if it's mounted
  if (tradesTabRef.value) {
    void tradesTabRef.value.refresh()
  }
}

function handleTradesTabSaved() {
  void refresh()
}

async function refreshWithInstrument() {
  await refresh()
  if (position.value) {
    try {
      instrument.value = await instrumentsApi.get(position.value.primary_instrument_id)
    } catch { instrument.value = null }
  }
}

watch(positionId, () => {
  planLoaded.value = false
  planStartExpanded.value = false
  void refreshWithInstrument()
})

onMounted(() => { void refreshWithInstrument() })
</script>

<template>
  <AuthenticatedLayout>
    <n-spin :show="loading">
      <n-alert v-if="error" type="error" style="margin-bottom: 1rem;">
        {{ error }}
        <n-button size="small" @click="refreshWithInstrument" style="margin-left: 0.5rem;">Retry</n-button>
      </n-alert>

      <template v-if="position">
        <!-- Header card -->
        <n-card style="margin-bottom: 1rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
                <span style="font-size: 1.5rem; font-weight: 600;">{{ symbol }}</span>
                <n-tag size="small">{{ prettifyStrategy(position.strategy_type) }}</n-tag>
                <PositionStatusBadge :status="position.status" />
              </div>
              <n-text depth="3" style="font-size: 0.9rem;">
                Opened {{ new Date(position.opened_at).toLocaleString() }}
                <template v-if="position.closed_at">
                  &middot; Closed {{ new Date(position.closed_at).toLocaleString() }}
                </template>
                &middot; {{ position.currency }}
              </n-text>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <n-button secondary :disabled="position.status !== 'open'" @click="showAddTradeModal = true">+ Add trade</n-button>
              <n-button @click="showEditModal = true">Edit</n-button>
              <n-popconfirm
                v-if="position.status === 'open'"
                @positive-click="handleClosePosition"
              >
                <template #trigger>
                  <n-button type="warning">Close</n-button>
                </template>
                Close this position? pnl_realized will be frozen as SUM(trade.cash_flow). This cannot be undone.
              </n-popconfirm>
              <n-popconfirm @positive-click="handleDeletePosition">
                <template #trigger>
                  <n-button type="error">Delete</n-button>
                </template>
                Delete this position? Only allowed when no trades are attached.
              </n-popconfirm>
            </div>
          </div>
        </n-card>

        <!-- Tabs -->
        <n-tabs v-model:value="activeTab" type="line" @update:value="handleTabChange">
          <!-- Overview tab -->
          <n-tab-pane name="overview" tab="Overview">
            <n-grid :cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive>
              <n-grid-item span="2 m:1">
                <n-card title="Manual Fields" size="small">
                  <n-descriptions label-placement="left" :column="1" bordered size="small">
                    <n-descriptions-item label="Capital Used">
                      {{ position.capital_used !== null ? formatAmount(position.capital_used, position.currency) : '—' }}
                    </n-descriptions-item>
                    <n-descriptions-item label="Max Risk at Open">
                      {{ position.max_risk_at_open !== null ? formatAmount(position.max_risk_at_open, position.currency) : '—' }}
                    </n-descriptions-item>
                    <n-descriptions-item label="Max Reward at Open">
                      {{ position.max_reward_at_open !== null ? formatAmount(position.max_reward_at_open, position.currency) : '—' }}
                    </n-descriptions-item>
                    <n-descriptions-item label="Notes">
                      {{ position.notes || '—' }}
                    </n-descriptions-item>
                  </n-descriptions>
                  <div style="margin-top: 0.75rem;">
                    <n-button text type="primary" @click="showEditModal = true">Edit</n-button>
                  </div>
                </n-card>
              </n-grid-item>

              <n-grid-item span="2 m:1">
                <n-card title="Derived Computations" size="small">
                  <n-descriptions label-placement="left" :column="1" bordered size="small">
                    <n-descriptions-item :label="position.status === 'open' ? 'Days Open' : 'Days Held'">
                      {{ daysOpen }}
                    </n-descriptions-item>
                    <n-descriptions-item label="Net Cash Flow">
                      {{ formatAmount(position.net_cash_flow, position.currency) }}
                    </n-descriptions-item>
                    <n-descriptions-item :label="position.status === 'closed' ? 'Realized P/L' : 'P/L Total'">
                      {{ formatAmount(pnlTotal, position.currency) }}
                    </n-descriptions-item>
                    <n-descriptions-item label="ROI on Capital">
                      {{ roi !== null ? `${roi}%` : '—' }}
                    </n-descriptions-item>
                    <n-descriptions-item label="Annualized ROI on Capital">
                      {{ annualizedRoi !== null ? `${annualizedRoi}%` : '—' }}
                    </n-descriptions-item>
                    <n-descriptions-item v-if="result" label="Result">
                      <n-tag :type="resultColor" size="small">{{ result }}</n-tag>
                    </n-descriptions-item>
                  </n-descriptions>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-tab-pane>

          <!-- Meta tab -->
          <n-tab-pane name="meta" tab="Meta">
            <template v-if="position.strategy_type === 'wheel'">
              <WheelMetaForm :position-id="positionId" :key="'wm-' + positionId" />
            </template>
            <template v-else-if="position.strategy_type === 'pmcc'">
              <PmccMetaForm :position-id="positionId" :key="'pm-' + positionId" />
            </template>
            <template v-else>
              <n-empty :description="`No metadata for ${prettifyStrategy(position.strategy_type)} positions in V1.`" />
            </template>
          </n-tab-pane>

          <!-- Plan tab -->
          <n-tab-pane name="plan" tab="Plan">
            <TradePlanList ref="tradePlanListRef" :position-id="positionId" :key="'tp-' + positionId" @loaded="handlePlanLoaded" />
            <div style="margin-top: 1rem;">
              <TradePlanForm v-if="planLoaded" :position-id="positionId" @saved="handlePlanSaved" :key="'tpf-' + positionId" :start-expanded="planStartExpanded" />
            </div>
          </n-tab-pane>

          <!-- Trades tab -->
          <n-tab-pane name="trades" tab="Trades">
            <PositionTradesTab
              ref="tradesTabRef"
              :position-id="positionId"
              :account-id="position.account_id"
              :currency="position.currency"
              :readonly="position.status !== 'open'"
              :key="'tr-' + positionId"
              @trade-saved="handleTradesTabSaved"
            />
          </n-tab-pane>
        </n-tabs>

        <PositionFormModal
          v-model:show="showEditModal"
          mode="edit"
          :position-id="positionId"
          :initial="position"
          @saved="handleEditSaved"
        />

        <!-- Standalone TradeEntryModal for "+ Add trade" -->
        <TradeEntryModal
          v-model:show="showAddTradeModal"
          :position-id="positionId"
          :account-id="position.account_id"
          :currency="position.currency"
          @saved="handleTradeSaved"
        />
      </template>

      <template v-else-if="!loading && !error">
        <n-empty description="Position not found" />
      </template>
    </n-spin>
  </AuthenticatedLayout>
</template>
