<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ winRate: string | null }>()

const pct = computed(() =>
  props.winRate == null ? null : Number(props.winRate) * 100,
)
</script>

<template>
  <n-card size="small">
    <n-statistic label="Win rate">
      <span v-if="pct == null">&mdash;</span>
      <span v-else :class="pct >= 50 ? 'text-success' : 'text-warning'">
        {{ pct.toFixed(1) }}%
      </span>
    </n-statistic>
  </n-card>
</template>

<style scoped>
.text-success {
  color: var(--n-success-color, #18a058);
}
.text-warning {
  color: var(--n-warning-color, #f0a020);
}
</style>
