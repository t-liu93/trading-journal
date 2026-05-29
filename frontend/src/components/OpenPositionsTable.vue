<script setup lang="ts">
import { h } from 'vue'
import { useRouter } from 'vue-router'
import { type DataTableColumns, NButton, NTime, NTooltip } from 'naive-ui'
import { type Instrument } from '../api/instruments'
import { type Position, type StrategyType } from '../api/positions'
import {
  computeDaysOpen,
  computePnlTotal,
  computeRoi,
  formatAmount,
} from '../utils/positionDerived'

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
    title: 'Opened At',
    key: 'opened_at',
    defaultSortOrder: 'descend',
    sorter: (a, b) => new Date(a.opened_at).getTime() - new Date(b.opened_at).getTime(),
    render: (row) =>
      h(NTooltip, null, {
        trigger: () => h(NTime, { time: new Date(row.opened_at).getTime(), type: 'relative' }),
        default: () =>
          h('span', new Date(row.opened_at).toLocaleString()),
      }),
  },
  {
    title: 'Net Cash Flow',
    key: 'net_cash_flow',
    render: (row) => {
      const n = Number(row.net_cash_flow)
      const color = n > 0 ? '#18a058' : n < 0 ? '#d03050' : undefined
      return h('span', { style: { color, fontWeight: 500 } }, formatAmount(n, row.currency))
    },
  },
  {
    title: 'Days Open',
    key: 'days_open',
    render: (row) => computeDaysOpen(row.opened_at, null),
  },
  {
    title: 'ROI',
    key: 'roi',
    render: (row) => {
      const pnlTotal = computePnlTotal(row.net_cash_flow)
      const roi = computeRoi(pnlTotal, row.capital_used)
      if (roi === null) return h('span', { style: { color: 'rgba(0,0,0,0.3)' } }, '—')
      const n = Number(roi)
      const color = n > 0 ? '#18a058' : n < 0 ? '#d03050' : undefined
      return h('span', { style: { color } }, `${roi}%`)
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
  <n-card title="Open positions">
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
      <n-empty description="No open positions" />
    </template>
    <template v-else>
      <n-data-table :columns="columns" :data="positions" :bordered="false" />
    </template>
  </n-card>
</template>
