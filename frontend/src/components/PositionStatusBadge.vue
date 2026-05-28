<script setup lang="ts">
import type { PositionStatus } from '../api/positions'
defineProps<{ status: PositionStatus }>()
</script>

<template>
  <n-tag :type="status === 'open' ? 'success' : 'default'" size="small">
    {{ status === 'open' ? 'Open' : 'Closed' }}
  </n-tag>
</template>
