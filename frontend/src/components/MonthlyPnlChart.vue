<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { MonthCurrencyAmount } from '../api/dashboard'

use([BarChart, GridComponent, LegendComponent, TitleComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ rows: MonthCurrencyAmount[] }>()

function buildChartOption(rows: MonthCurrencyAmount[]) {
  // Collect unique months (x-axis categories) and currencies (series)
  const monthsSet = new Set<string>()
  const currenciesSet = new Set<string>()
  for (const r of rows) {
    monthsSet.add(r.month)
    currenciesSet.add(r.currency)
  }
  const months = [...monthsSet].sort()
  const currencies = [...currenciesSet].sort()

  // Index by (month, currency) → amount
  const byKey = new Map<string, number>()
  for (const r of rows) {
    byKey.set(`${r.month}|${r.currency}`, Number(r.amount))
  }

  // Build series
  const series = currencies.map(c => ({
    name: c,
    type: 'bar' as const,
    stack: 'pnl',
    emphasis: { focus: 'series' as const },
    data: months.map(m => byKey.get(`${m}|${c}`) ?? 0),
  }))

  return {
    title: { text: 'Monthly realized P/L' },
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    legend: { data: currencies },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category' as const, data: months },
    yAxis: { type: 'value' as const },
    series,
  }
}

const option = computed(() => buildChartOption(props.rows))
</script>

<template>
  <n-card>
    <div v-if="rows.length === 0" class="empty">
      <n-empty description="No closed positions yet — chart will populate after the first close." />
    </div>
    <v-chart v-else :option="option" autoresize style="height: 360px" />
  </n-card>
</template>

<style scoped>
.empty {
  padding: 2rem 0;
  text-align: center;
}
</style>
