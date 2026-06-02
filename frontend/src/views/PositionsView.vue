<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { type DataTableColumns, NButton, NTime } from 'naive-ui'
import AuthenticatedLayout from '../components/AuthenticatedLayout.vue'
import PositionFormModal from '../components/PositionFormModal.vue'
import PositionStatusBadge from '../components/PositionStatusBadge.vue'
import { usePositions } from '../composables/usePositions'
import { useAccounts } from '../composables/useAccounts'
import { type Instrument, instrumentsApi } from '../api/instruments'
import { type Position, type StrategyType } from '../api/positions'
import { formatAmount } from '../utils/positionDerived'

const router = useRouter()
const { positions, loading, error, statusFilter, strategyTypeFilter, refresh } = usePositions()
const { accounts, refresh: refreshAccounts } = useAccounts()

const instrumentMap = ref<Record<string, Instrument>>({})
const showCreateModal = ref(false)

const accountName = computed<Record<string, string>>(() =>
  Object.fromEntries(accounts.value.map(a => [a.id, a.name])),
)
const accountFilterOptions = computed(() =>
  accounts.value.map(a => ({ label: a.name, value: a.id })),
)

const statusOptions = [
  { label: 'All', value: '' },
  { label: 'Open', value: 'open' },
  { label: 'Closed', value: 'closed' },
]

const strategyOptions = [
  { label: 'All', value: '' },
  { label: 'Wheel', value: 'wheel' },
  { label: 'Iron Condor', value: 'iron_condor' },
  { label: 'PMCC', value: 'pmcc' },
  { label: 'Spot Stock', value: 'spot_stock' },
  { label: 'Spot Forex', value: 'spot_forex' },
]

function prettifyStrategy(s: StrategyType): string {
  const map: Record<StrategyType, string> = {
    wheel: 'Wheel',
    iron_condor: 'Iron Condor',
    pmcc: 'PMCC',
    spot_stock: 'Spot Stock',
    spot_forex: 'Spot Forex',
  }
  return map[s] ?? s
}

const columns = computed<DataTableColumns<Position>>(() => [
  {
    title: 'Symbol',
    key: 'symbol',
    render: (row) => instrumentMap.value[row.primary_instrument_id]?.symbol ?? '—',
  },
  {
    title: 'Account',
    key: 'account_id',
    render: (row) => accountName.value[row.account_id] ?? '—',
    // Built-in client-side column filter (single account at a time).
    filter: (value, row) => row.account_id === value,
    filterOptions: accountFilterOptions.value,
    filterMultiple: false,
  },
  {
    title: 'Strategy',
    key: 'strategy_type',
    render: (row) => h('span', prettifyStrategy(row.strategy_type)),
  },
  {
    title: 'Opened At',
    key: 'opened_at',
    render: (row) =>
      h(NTime, { time: new Date(row.opened_at).getTime(), format: 'yyyy-MM-dd HH:mm' }),
  },
  {
    title: () => {
      if (statusFilter.value === 'open') return 'Net Cash Flow'
      if (statusFilter.value === 'closed') return 'Realized P/L'
      return 'Cash Flow'
    },
    key: 'cash_flow',
    render: (row) => {
      const label = row.status === 'open' ? 'Net Cash Flow' : 'Realized P/L'
      const val = row.status === 'closed' ? row.pnl_realized : row.net_cash_flow
      const n = Number(val)
      const color = n > 0 ? '#18a058' : n < 0 ? '#d03050' : undefined
      return h('div', [
        h('div', { style: { fontSize: '0.75rem', color: 'rgba(0,0,0,0.45)' } }, label),
        h('span', { style: { color, fontWeight: 500 } }, formatAmount(n, row.currency)),
      ])
    },
    sorter: (a, b) => Number(a.net_cash_flow) - Number(b.net_cash_flow),
  },
  {
    title: 'Currency',
    key: 'currency',
  },
  {
    title: 'Status',
    key: 'status',
    render: (row) => h(PositionStatusBadge, { status: row.status }),
  },
  {
    title: 'Actions',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/positions/${row.id}`) },
        () => 'Open',
      ),
  },
])

async function loadInstruments() {
  try {
    const list = await instrumentsApi.list({ limit: 200 })
    const map: Record<string, Instrument> = {}
    for (const inst of list) map[inst.id] = inst
    instrumentMap.value = map
  } catch { /* ignore */ }
}

onMounted(async () => {
  await Promise.all([refresh(), refreshAccounts(), loadInstruments()])
})

function handleSaved(position?: Position) {
  if (position) {
    void refresh().then(() => {
      router.push(`/positions/${position.id}`)
    })
  } else {
    void refresh()
  }
}
</script>

<template>
  <AuthenticatedLayout>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
      <n-h2 style="margin: 0;">Positions</n-h2>
      <n-button type="primary" @click="showCreateModal = true">+ New Position</n-button>
    </div>

    <div style="display: flex; gap: 1rem; margin-bottom: 1rem;">
      <n-select
        v-model:value="statusFilter"
        :options="statusOptions"
        style="width: 160px;"
      />
      <n-select
        v-model:value="strategyTypeFilter"
        :options="strategyOptions"
        style="width: 200px;"
      />
    </div>

    <n-alert v-if="error" type="error" style="margin-bottom: 1rem;">
      {{ error }}
      <n-button size="small" @click="refresh" style="margin-left: 0.5rem;">Retry</n-button>
    </n-alert>

    <n-spin :show="loading">
      <template v-if="!loading && positions.length === 0">
        <n-empty description="No positions yet">
          <template #extra>
            <n-button type="primary" @click="showCreateModal = true">+ New Position</n-button>
          </template>
        </n-empty>
      </template>
      <template v-else>
        <n-data-table :columns="columns" :data="positions" :bordered="false" />
      </template>
    </n-spin>

    <PositionFormModal
      v-model:show="showCreateModal"
      mode="create"
      @saved="handleSaved"
    />
  </AuthenticatedLayout>
</template>
