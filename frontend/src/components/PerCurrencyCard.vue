<script setup lang="ts">
import { formatAmount } from '../utils/positionDerived'

defineProps<{
  label: string
  currency: string
  amount: string
}>()
</script>

<template>
  <n-card size="small">
    <n-statistic :label="label">
      <span :class="Number(amount) > 0 ? 'text-success' : Number(amount) < 0 ? 'text-error' : ''">
        {{ formatAmount(amount, currency) }}
      </span>
    </n-statistic>
  </n-card>
</template>

<style scoped>
.text-success {
  color: var(--n-success-color, #18a058);
}
.text-error {
  color: var(--n-error-color, #d03050);
}
</style>
