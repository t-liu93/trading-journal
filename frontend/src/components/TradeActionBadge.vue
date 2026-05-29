<script setup lang="ts">
import type { TradeAction } from '../api/trades'

const props = defineProps<{ action: TradeAction }>()

const colorMap: Record<TradeAction, string> = {
  buy: '#d03050',
  bto: '#d03050',
  btc: '#d03050',
  sell: '#18a058',
  sto: '#18a058',
  stc: '#18a058',
}
</script>

<template>
  <n-tag size="small" :style="{ color: colorMap[props.action], fontWeight: 500 }" :bordered="false">
    {{ props.action.toUpperCase() }}
  </n-tag>
</template>
