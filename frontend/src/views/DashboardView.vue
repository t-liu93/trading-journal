<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import PerCurrencyCard from '../components/PerCurrencyCard.vue'
import DashboardWinRateGauge from '../components/DashboardWinRateGauge.vue'
import MonthlyPnlChart from '../components/MonthlyPnlChart.vue'
import OpenPositionsTable from '../components/OpenPositionsTable.vue'
import ClosedPositionsTable from '../components/ClosedPositionsTable.vue'
import { useDashboard } from '../composables/useDashboard'
import { usePositions } from '../composables/usePositions'
import { type Instrument, instrumentsApi } from '../api/instruments'

const { summary, loading: summaryLoading, error: summaryError, refresh: refreshSummary } = useDashboard()
const { positions, loading: positionsLoading, error: positionsError, refresh: refreshPositions } = usePositions({ status: '' })
const instrumentMap = ref<Record<string, Instrument>>({})
const instrumentsError = ref<string | null>(null)

const localError = ref<string | null>(null)

// Surface the first error from either summary or positions
watch([summaryError, positionsError], ([sErr, pErr]) => {
  localError.value = sErr ?? pErr ?? null
})

function dismissError() {
  localError.value = null
}

const openPositions = computed(() => positions.value.filter(p => p.status === 'open'))
const closedPositions = computed(() => positions.value.filter(p => p.status === 'closed'))

const loading = computed(() => summaryLoading.value || positionsLoading.value)

async function loadInstruments() {
  try {
    const list = await instrumentsApi.list({ limit: 200 })
    const map: Record<string, Instrument> = {}
    for (const inst of list) map[inst.id] = inst
    instrumentMap.value = map
    instrumentsError.value = null
  } catch {
    instrumentsError.value = 'Failed to load instrument names'
  }
}

onMounted(async () => {
  await Promise.all([refreshSummary(), refreshPositions(), loadInstruments()])
})
</script>

<template>
  <AuthenticatedLayout>
    <n-page-header title="Dashboard" />

    <n-alert
      v-if="localError"
      type="error"
      :title="localError"
      closable
      style="margin-bottom: 1rem;"
      @close="dismissError"
    />

    <n-spin :show="loading">
      <!-- Summary strip -->
      <n-grid v-if="summary" :cols="6" :x-gap="12" :y-gap="12">
        <n-gi>
          <DashboardWinRateGauge :winRate="summary.closed.win_rate" />
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="Open positions" :value="summary.open.count" />
          </n-card>
        </n-gi>
        <n-gi>
          <n-card size="small">
            <n-statistic label="Closed positions" :value="summary.closed.count" />
          </n-card>
        </n-gi>
      </n-grid>

      <!-- Per-currency cards -->
      <n-grid v-if="summary" :cols="4" :x-gap="12" :y-gap="12" style="margin-top: 16px">
        <n-gi v-for="row in summary.closed.per_currency_pnl" :key="`closed-${row.currency}`">
          <PerCurrencyCard label="Realized P/L (closed)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
        <n-gi v-for="row in summary.open.per_currency_net_cash_flow" :key="`open-${row.currency}`">
          <PerCurrencyCard label="Net Cash Flow (open)" :currency="row.currency" :amount="row.amount" />
        </n-gi>
      </n-grid>

      <!-- Chart -->
      <div style="margin-top: 24px">
        <MonthlyPnlChart v-if="summary" :rows="summary.closed.monthly_pnl" />
      </div>

      <!-- Tables — shared data source from parent -->
      <n-grid :cols="1" :y-gap="16" style="margin-top: 24px">
        <n-gi>
          <OpenPositionsTable
            :positions="openPositions"
            :instrument-map="instrumentMap"
            :instruments-error="instrumentsError"
            :positions-error="positionsError"
          />
        </n-gi>
        <n-gi>
          <ClosedPositionsTable
            :positions="closedPositions"
            :instrument-map="instrumentMap"
            :instruments-error="instrumentsError"
            :positions-error="positionsError"
          />
        </n-gi>
      </n-grid>
    </n-spin>
  </AuthenticatedLayout>
</template>
