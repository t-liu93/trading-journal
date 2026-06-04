<script setup lang="ts">
import { h } from 'vue'
import { useRouter } from 'vue-router'
import { type DataTableColumns, NButton, NText, NTime, NTag, NTooltip } from 'naive-ui'
import { type Instrument } from '../api/instruments'
import { type Position, type StrategyType } from '../api/positions'
import { computeResult, formatAmount, type PositionResult } from '../utils/positionDerived'

const props = defineProps<{
  positions: Position[]
  instrumentMap: Record<string, Instrument>
  instrumentsError: string | null
  positionsError: string | null
}>()

const router = useRouter()

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

function resultTagType(r: PositionResult | null): 'success' | 'error' | 'default' {
  if (r === 'Win') return 'success'
  if (r === 'Loss') return 'error'
  return 'default'
}

const columns: DataTableColumns<Position> = [
  {
    title: 'Symbol',
    key: 'symbol',
    render: (row) => props.instrumentMap[row.primary_instrument_id]?.symbol ?? '—',
  },
  {
    title: 'Strategy',
    key: 'strategy_type',
    render: (row) => h('span', prettifyStrategy(row.strategy_type)),
  },
  {
    title: 'Closed At',
    key: 'closed_at',
    defaultSortOrder: 'descend',
    sorter: (a, b) => {
      const ta = a.closed_at ? new Date(a.closed_at).getTime() : 0
      const tb = b.closed_at ? new Date(b.closed_at).getTime() : 0
      return ta - tb
    },
    render: (row) => {
      if (!row.closed_at) return '—'
      const ts = new Date(row.closed_at).getTime()
      return h(NTooltip, null, {
        trigger: () => h(NTime, { time: ts, type: 'relative' }),
        default: () => h('span', new Date(row.closed_at as string).toLocaleString()),
      })
    },
  },
  {
    title: 'Realized P/L',
    key: 'pnl_realized',
    render: (row) => {
      const val = row.pnl_realized
      if (val === null) return h(NText, { depth: 3 }, () => '—')
      const n = Number(val)
      const color = n > 0 ? '#18a058' : n < 0 ? '#d03050' : undefined
      return h('span', { style: { color, fontWeight: 500 } }, formatAmount(n, row.currency))
    },
  },
  {
    title: 'Result',
    key: 'result',
    render: (row) => {
      const r = computeResult(row.pnl_realized)
      return h(NTag, { size: 'small', type: resultTagType(r) }, () => r ?? '—')
    },
  },
  {
    title: 'Currency',
    key: 'currency',
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
]
</script>

<template>
  <n-card title="Closed positions">
    <template #header-extra>
      <n-text depth="3" style="font-size: 0.85rem;">
        {{ positions.length }} position{{ positions.length !== 1 ? 's' : '' }}
      </n-text>
    </template>

    <n-alert v-if="positionsError" type="error" style="margin-bottom: 0.75rem;">
      Failed to load positions: {{ positionsError }}
    </n-alert>

    <n-alert v-else-if="instrumentsError" type="warning" style="margin-bottom: 0.75rem;">
      {{ instrumentsError }} — Symbol column may show incomplete data.
    </n-alert>

    <template v-if="positionsError">
      <!-- error alert already shown above; suppress table + empty -->
    </template>
    <template v-else-if="positions.length === 0">
      <n-empty description="No closed positions yet" />
    </template>
    <template v-else>
      <n-data-table :columns="columns" :data="positions" :bordered="false" />
    </template>
  </n-card>
</template>
