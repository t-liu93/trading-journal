<script setup lang="ts">
import { onMounted, h, ref } from 'vue'
import { usePosition, type Trade } from '../composables/usePosition'
import { instrumentsApi, type Instrument } from '../api/instruments'
import { type DataTableColumns } from 'naive-ui'

const props = defineProps<{ positionId: string }>()

const { trades, loading, refresh } = usePosition(ref(props.positionId))
const instrumentMap = ref<Record<string, Instrument>>({})

onMounted(async () => {
  await refresh()
  const ids = [...new Set(trades.value.map((t) => t.instrument_id))]
  const map: Record<string, Instrument> = {}
  for (const id of ids) {
    try { map[id] = await instrumentsApi.get(id) } catch { /* skip */ }
  }
  instrumentMap.value = map
})

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatNum(val: string | null): string {
  if (!val) return '—'
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(Number(val))
}

function actionColor(action: string): string {
  if (['sell', 'sto', 'stc'].includes(action)) return '#18a058'
  return '#d03050'
}

const columns: DataTableColumns<Trade> = [
  { title: 'Executed At', key: 'executed_at', render: (row) => formatDateTime(row.executed_at) },
  {
    title: 'Action',
    key: 'action',
    render: (row) => h('span', { style: { color: actionColor(row.action), fontWeight: 500 } }, row.action.toUpperCase()),
  },
  {
    title: 'Instrument',
    key: 'instrument_id',
    render: (row) => instrumentMap.value[row.instrument_id]?.symbol ?? row.instrument_id,
  },
  { title: 'Quantity', key: 'quantity', render: (row) => formatNum(row.quantity) },
  { title: 'Price', key: 'price', render: (row) => formatNum(row.price) },
  {
    title: 'Cash Flow',
    key: 'cash_flow',
    render: (row) => {
      const val = Number(row.cash_flow)
      const color = val > 0 ? '#18a058' : val < 0 ? '#d03050' : undefined
      return h('span', { style: { color, fontWeight: 500 } }, formatNum(row.cash_flow))
    },
  },
]
</script>

<template>
  <div>
    <n-alert type="info" style="margin-bottom: 1rem;">
      Trade entry — including multi-leg flows — will land in F4. For now, trades created via the API or the Position-create flow appear here read-only.
    </n-alert>

    <n-spin :show="loading">
      <template v-if="trades.length === 0">
        <n-empty description="No trades yet on this position." />
      </template>
      <template v-else>
        <n-data-table :columns="columns" :data="trades" :bordered="false" size="small" />
      </template>
    </n-spin>
  </div>
</template>
